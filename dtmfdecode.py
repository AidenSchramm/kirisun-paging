#!/usr/bin/python3 -u

import time
import signal
import sys
import subprocess
import os
from multiprocessing import Pool, Process, Manager
import threading
from threading import Thread
import csv
from csv import DictReader
import concurrent.futures
from threading import current_thread
from colorama import Fore, Back, Style

import pexpect
from monkeyrunner import MonkeyRunner, MonkeyDevice

import RPi.GPIO as GPIO
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)


class Trunk:
    def __init__(self, index, gpio_pin):
        self.channel = index
        self.pin = gpio_pin
        GPIO.setup(self.pin, GPIO.IN)        
        self.dtmf = subprocess.Popen("parec --latency-msec 5 --format=s16le --channels=1 --rate=22050 -d "
                                     "alsa_input.Trunk_" + self.channel + ".mono-fallback | multimon-ng -t raw -a DTMF -", 
                                     stdout=subprocess.PIPE, stderr=open('/dev/null','a'), shell=True)
        os.set_blocking(self.dtmf.stdout.fileno(), False)
        self.number = ''
        self.extra = ''
        self.digit  = ''
        self.time_start = 0
        self.time_stop  = 0
        self.time_delay = 0
        self.delay = False
        self.active = False
        self.busy = False
        self.valid = False
        self.data = ""
        self.line = ""

    def poll(self):
        if (self.valid):
            garbage = self.dtmf.stdout.readline()
            self.data = ''
            self.line = ''
            self.dtmf.poll()
        else:
            self.data = self.dtmf.stdout.readline()
            self.line = self.data.decode('utf-8')
            self.dtmf.poll()

    def gpio(self):
        return GPIO.input(self.pin)

class Radio:
    def __init__(self, index, serial):
        self.channel = index
        self.id = serial
        self.adb = "adb -s " + self.id + " "
        self.ptt_off_command = self.adb + "shell sendevent /dev/input/event1 1 60 0; " + self.adb + "shell sendevent /dev/input/event1 0 0 0"
        self.ptt_on_command  = self.adb + "shell sendevent /dev/input/event1 1 60 1; " + self.adb + "shell sendevent /dev/input/event1 0 0 0"
        self.logcat = subprocess.Popen(self.adb + "logcat | awk '/AudioALSA/'", stdout=subprocess.PIPE, shell=True)
        os.set_blocking(self.logcat.stdout.fileno(), False)
        self.drop_time = 0
        self.active = False
        self.monkey = MonkeyRunner.waitForConnection(5, self.id)
        self.init = True
        self.group = 1
        self.set_group(self.group)
        self.blank = False
        self.data = ""
        self.line = ""
        self.ptt = False
        self.sfx = False
        self.interrupt = False
        
        self.TID_list = []

        while len(self.TID_list) < 3:
            self.ptt_on()
            self.TID_list = self.monkey.shell("dumpsys media.audio_flinger | grep TID").splitlines()
            print(self.TID_list)
            self.ptt_off()

        self.voice_out_TID = str(self.TID_list[0]).strip().split()[1]
        self.sfx_out_TID = str(self.TID_list[1]).strip().split()[1]
        self.voice_in_TID = str(self.TID_list[2]).strip().split()[1]
            
        print(self.voice_out_TID)
        print(self.sfx_out_TID)
        print(self.voice_in_TID)


        self.lock = threading.Lock()

        print(Fore.GREEN + "###################################" + Fore.RESET)
        print(Fore.GREEN + "##             READY             ##" + Fore.RESET)
        print(Fore.GREEN + "###################################" + Fore.RESET)
        
    def play_sfx(self):
        print(Fore.GREEN + "Radio_" + self.channel + ": " + Fore.RESET + "Playing incoming call SFX")
        try:
            os.system("pacat -d alsa_output.Radio_" + self.channel + ".analog-stereo call.wav --volume=65000")
        except:
            print(Fore.GREEN + "Radio_" + self.channel + ": " + Fore.RESET + "Failed to play SFX")
        

    def ptt_off(self):
        os.system(self.ptt_off_command)
        self.ptt = False

    def ptt_on(self):
        os.system(self.ptt_on_command)
        self.ptt = True

    def poll(self):
        self.data = self.logcat.stdout.readline()
        self.line = self.data.decode('utf-8')
        self.logcat.poll()

    def patch(self, trunk):
        print(Fore.GREEN + "Radio_" + self.channel + ": " + Fore.RESET + "Patch audio")
        self.mic_id = subprocess.check_output("pactl load-module module-loopback source=alsa_input.Trunk_" + trunk.channel + ".mono-fallback sink=alsa_output.Radio_" + self.channel + ".analog-stereo", shell=True).decode('utf-8').strip()
        self.speaker_id = subprocess.check_output("pactl load-module module-loopback source=alsa_input.Radio_" + self.channel + ".mono-fallback sink=alsa_output.Trunk_" + trunk.channel + ".analog-stereo", shell=True).decode('utf-8').strip()
        #print(self.mic_id)
        #print(self.speaker_id)

    def unpatch(self):
        print(Fore.GREEN + "Radio_" + self.channel + ": " + Fore.RESET + "Unpatch audio")
        try:
            os.system("pactl unload-module " + self.mic_id)
            os.system("pactl unload-module " + self.speaker_id)
            self.mic_id = None
            self.speaker_id = None
        except AttributeError:
            print(Fore.GREEN + "Radio_" + self.channel + ": " + Fore.RESET + "Nothing to unpatch")
        except TypeError:
            print(Fore.GREEN + "Radio_" + self.channel + ": " + Fore.RESET + "Nothing to unpatch")


    def mute(self, trunk):
        print(Fore.GREEN + "Radio_" + self.channel + ": " + Fore.RESET + "Mute audio out")
        os.system("pactl set-sink-mute " + "alsa_output.Trunk_" + trunk.channel + ".analog-stereo" + " 1")

    def unmute(self, trunk):
        print(Fore.GREEN + "Radio_" + self.channel + ": " + Fore.RESET + "Unmute audio out")
        os.system("pactl set-sink-mute " + "alsa_output.Trunk_" + trunk.channel + ".analog-stereo" + " 0")

    def press_menu(self, target):
        target.press('KEYCODE_MENU', MonkeyDevice.DOWN_AND_UP)
    
    def press_select(self, target):
        target.press('KEYCODE_DPAD_CENTER', MonkeyDevice.DOWN_AND_UP)

    def press_down(self, target):
        target.press('KEYCODE_DPAD_DOWN', MonkeyDevice.DOWN_AND_UP)

    def press_up(self, target): 
        target.press('KEYCODE_DPAD_UP', MonkeyDevice.DOWN_AND_UP)

    def press_back(self, target):
        target.press('KEYCODE_BACK', MonkeyDevice.DOWN_AND_UP)

    def set_group(self, index):
        original = self.group
        p = self.monkey
        
        time.sleep(1)

        for x in range(5):
            self.press_back(p)

        self.press_menu(p)
        time.sleep(0.2)
        self.press_down(p)
        time.sleep(0.2)
        self.press_down(p)
        time.sleep(0.2)
        self.press_select(p)
        
        if self.init:
            for x in range(50):
                self.press_up(p)
            self.press_select(p)
            self.press_select(p)
            self.init = False

        if index < self.group:
            distance = self.group - index
            for x in range(distance):
                self.press_up(p)
            self.press_select(p)
            self.press_select(p)
        if index > self.group:
            distance = index - self.group
            for x in range(distance):
                self.press_down(p)
            self.press_select(p)
            self.press_select(p)
        
        self.group = index
        time.sleep(2)
        for x in range(3):
            self.press_back(p)
        print(Fore.GREEN + "Radio_" + self.channel + ": " + Fore.RESET + "Changed from group #" + str(original) + " to group #" + str(index))
        


def router(trunk, radios, channels):
    while True:
        found = False
        try:
            if trunk.gpio():
                trunk.busy = True
            else:
                trunk.busy = False

            if (not trunk.busy):
                trunk.valid = False
                trunk.number = ''

            trunk.poll()

            if (not trunk.active):
                if ("DTMF:" in trunk.line):
                    trunk.digit = trunk.line.split()[1]
                    trunk.number += trunk.digit
                    #print(trunk.number)
                
                if len(trunk.number) == 7:
                    trunk.valid = True
                    
                    for row in channels:
                        if (row['Phone'] == trunk.number) and (row['Enabled'] == "yes"):
                            found = True
                            trunk.active = True
                            trunk.delay = True
                            print(Fore.RED + "Trunk_" + trunk.channel + ": " + Fore.RESET + trunk.number + " - Group: " + row['Group Name'])
                            trunk.number = ''
                            
                            for item in radios:
                                if (not item.lock.locked()):
                                    radio = item
                                    use = True
                            if (not use):
                                print(Fore.RED + "Trunk_" + trunk.channel + ": " + Fore.RESET + "No available radios, bailing out..")
                                break
                            
                            print(Fore.RED + "Trunk_" + trunk.channel + ": " + Fore.RESET + "Radio_" + radio.channel + " is not locked, using")
                            lock = radio.lock.acquire()

                            trunk.time_delay = time.time() + 7.5

                            trunk.time_start = time.time() + 7.5
                            trunk.time_stop = time.time() + 37
                        
                            print(Fore.RED + "Trunk_" + trunk.channel + ": " + Fore.RESET + "Keying radio in 7 seconds")
                            radio.ptt_off()
                            radio.sfx = True
                            radio.active = True
                            radio.set_group(int(row['Channel']))
                            radio.drop_time = trunk.time_start + 0.5
                            
                            break
                    if (not found):
                        print(Fore.RED + "Trunk_" + trunk.channel + ": " + Fore.RESET + trunk.number + " is not a valid pager number, ignoring...")
                        trunk.number = ''
                    found = False
            else:
                if trunk.active:
                    radio.poll()
                
                if (trunk.delay) and (radio.sfx) and ((trunk.time_delay - 5) < time.time()):
                    radio.ptt_off()
                    radio.ptt_on()
                    radio.play_sfx()

                    radio.sfx = False

                if (trunk.delay) and (trunk.time_delay < time.time()):
                    #radio.ptt_on()
                    
                    print(Fore.RED + "Trunk_" + trunk.channel + ": " + Fore.RESET + "// Using: Radio_" + radio.channel + " //")
                    radio.patch(trunk)

                    trunk.delay = False
                    
                
                "AudioALSAStreamOut: close(), flags 2"
                
                if ((radio.voice_in_TID + " D AudioALSAStreamIn: close()") in radio.line) and (not radio.interrupt) and (radio.drop_time < time.time()) and (trunk.active) and (trunk.time_start < time.time()):
                    radio.interrupt = True
                    print(Fore.GREEN + "Radio_" + radio.channel + ": " + Fore.RESET + "***Interrupted***")
                    #radio.ptt_off()
                
                if ((radio.voice_out_TID + " D AudioALSAStreamOut: close()") in radio.line) and (radio.interrupt) and (trunk.active) and (trunk.time_start < time.time()):
                    print(Fore.GREEN + "Radio_" + radio.channel + ": " + Fore.RESET + "***PTT dropped: re-keying radio***")
                    radio.ptt_off()
                    radio.ptt_on()
                    radio.interrupt = False                
                    
                if (trunk.active) and ((time.time() > trunk.time_stop) or (not trunk.busy)):
                    print(Fore.RED + "Trunk_" + trunk.channel + ": " + Fore.RESET + "unkeying radio...")
                    #radio.mute(trunk)
                    radio.unpatch()
                    radio.ptt_off()
                    print(Fore.RED + "Trunk_" + trunk.channel + ": " + Fore.RESET + "[[PAGE DONE]]")

                    radio.set_group(1)
                    trunk.number = ''
                    
                    trunk.time_start = 0
                    trunk.time_stop = 99999999999999999
                    trunk.active = False
                    trunk.valid = False
                    trunk.delay = False
                    radio.active = False
                    radio.interrupt = False
                    radio.sfx = False

                    radio.lock.release()
                    radio = None

                    

        except KeyboardInterrupt:
            os.kill(trunk.dtmf.pid, 9)
            
            radio.ptt_off()
            radio.unpatch()
            os.kill(radio.logcat.pid, 9)
            
            GPIO.cleanup()
            exit()


if __name__ == "__main__":
    radio_2_id = "AUUKAANBKNFE89DM"
    radio_1_id = "SK7SPJ8PY9OJZ5EU"
#    radio_3_id = "5LU85TKNNR59RCWS"

    trunk_1 = Trunk("1", 17) 
    trunk_2 = Trunk("2", 27)
    trunk_3 = Trunk("3", 22)
    trunk_4 = Trunk("4", 23)
    trunk_5 = Trunk("5", 24)
    trunk_6 = Trunk("6", 25)
    trunks = [trunk_1, trunk_2, trunk_3, trunk_4, trunk_5, trunk_6]
    
    radio_1 = Radio("1", radio_1_id)
    radio_2 = Radio("2", radio_2_id)
#    radio_3 = Radio("3", radio_3_id)
    radios = [radio_1, radio_2]

    for radio in radios:
        radio.ptt_off()
    

    for radio in radios:
        try:
            os.system("pactl set-sink-volume alsa_output.Radio_" + radio.channel + ".analog-stereo 80%")
            os.system("pactl set-source-volume alsa_input.Radio_" + radio.channel + ".mono-fallback 80%")
        except:
            print("Oh no radio")

    for trunk in trunks:
        try:
            os.system("pactl set-sink-volume alsa_output.Trunk_" + trunk.channel + ".analog-stereo 100%")
            os.system("pactl set-source-volume alsa_input.Trunk_" + trunk.channel + ".mono-fallback 80%")
        except:
            print("Oh no trunk")


    with open('groups.csv', newline='') as csvfile:
        dict_reader = DictReader(csvfile)
        channels = list(dict_reader)
    
    threads = []

    try:
        for trunk in trunks:
            threads.append(Thread(target=router, args=(trunk, radios, channels), daemon=True))
        
        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()
        
    except:
        print("Exiting...")
        for trunk in trunks:
            try:
                os.kill(trunk.dtmf.pid, 9)
            except ProcessLookupError:
                print(Fore.RED + "Trunk_" + trunk.channel + ": " + Fore.RESET + "Already dead")

        for radio in radios:
            try:
                radio.ptt_off()
                radio.unpatch()
                os.kill(radio.logcat.pid, 9)
            except ProcessLookupError:
                print(Fore.GREEN + "Radio_" + radio.channel + ": " + Fore.RESET + "Already dead")
    

        GPIO.cleanup()
        exit()
