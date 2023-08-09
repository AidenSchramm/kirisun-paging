#!/usr/bin/python

import time
import signal
import sys
import subprocess
import os
from multiprocessing import Pool, Process, Manager
import threading

import pexpect
from monkeyrunner import MonkeyRunner, MonkeyDevice

import RPi.GPIO as GPIO
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)



radio_1_id = "SK7SPJ8PY9OJZ5EU"

class Trunk:
    def __init__(self, index, gpio_pin):
        self.channel = index
        self.pin = gpio_pin
        self.state = False
        GPIO.setup(self.pin, GPIO.IN)

        
        self.dtmf = subprocess.Popen("parec --latency-msec 5 --format=s16le --channels=1 --rate=22050 -d alsa_input.Trunk_" + self.channel + ".mono-fallback | multimon-ng -t raw -a DTMF -", 
                                                                                stdout=subprocess.PIPE, stderr=open('/dev/null','a'), shell=True)
        os.set_blocking(self.dtmf.stdout.fileno(), False)
        self.number = ''
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
        #print(os.get_blocking(self.dtmf.stdout.fileno()))
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
        self.logcat = subprocess.Popen(self.adb + "logcat", stdout=subprocess.PIPE, stderr=open('/dev/null','a'), shell=True)
        self.drop_time = 0
        self.active = False
        self.monkey = MonkeyRunner.waitForConnection(5, self.id)

        self.group = 1
        self.set_group(self.group)

        self.transmit = False
        self.receive = False
        self.blank = False

        self.data = ""
        self.line = ""
        self.init = True

    def ptt_off(self):
        os.system(self.ptt_off_command)

    def ptt_on(self):
        os.system(self.ptt_on_command)

    def poll(self):
        self.data = self.logcat.stdout.readline()
        self.line = self.data.decode('utf-8')
        self.logcat.poll()

    def patch(self, trunk):
        print("Patch audio")
        self.mic_id = subprocess.check_output("pactl load-module module-loopback source=alsa_input.Trunk_" + trunk.channel + ".mono-fallback sink=alsa_output.Radio_" + self.channel + ".analog-stereo", shell=True).decode('utf-8').strip()
        self.speaker_id = subprocess.check_output("pactl load-module module-loopback source=alsa_input.Radio_" + self.channel + ".mono-fallback sink=alsa_output.Trunk_" + trunk.channel + ".analog-stereo", shell=True).decode('utf-8').strip()
        print(self.mic_id)
        print(self.speaker_id)

    def unpatch(self):
        print("Unpatch audio")
        try:
            os.system("pactl unload-module " + self.mic_id)
            os.system("pactl unload-module " + self.speaker_id)
        except AttributeError:
            print("Nothing to unpatch")

    def mute(self, trunk):
        print("Mute audio out")
        os.system("pactl set-sink-mute " + "alsa_output.Trunk_" + trunk.channel + ".analog-stereo" + " 1")

    def unmute(self, trunk):
        print("Unmute audio out")
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

    def set_group_thread(self, index):
        p = self.monkey
        
        #press_menu = "shell sendevent /dev/input/event2 1 139 1; shell sendevent /dev/input/event2 0 0 0; shell sendevent /dev/input/event2 1 139 0; shell sendevent /dev/input/event2 0 0 0"
        #press_down = "shell sendevent /dev/input/event2 1 108 1; shell sendevent /dev/input/event2 0 0 0; shell sendevent /dev/input/event2 1 108 0; shell sendevent /dev/input/event2 0 0 0"
        #press_up   = "shell sendevent /dev/input/event2 1 103 1; shell sendevent /dev/input/event2 0 0 0; shell sendevent /dev/input/event2 1 103 0; shell sendevent /dev/input/event2 0 0 0"
        #press_back = "shell sendevent /dev/input/event2 1 158 1; shell sendevent /dev/input/event2 0 0 0; shell sendevent /dev/input/event2 1 158 0; shell sendevent /dev/input/event2 0 0 0"

        for x in range(5):
            self.press_back(p)

        self.press_menu(p)
        time.sleep(0.2)
        self.press_down(p)
        time.sleep(0.2)
        self.press_select(p)
        
        print("Changing from group #" + str(self.group) + " to group #" + str(index))
        if self.init:
            for x in range(10):
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

    def set_group(self, index):
        task = threading.Thread(target=self.set_group_thread, args=(index,))
        task.start()

def router(trunk, radio):
    try:
        if trunk.gpio():
            trunk.busy = True
        else:
            trunk.busy = False

        trunk.poll()
        
        if (not trunk.active) and (not radio.active):
            if ("DTMF:" in trunk.line):
                trunk.digit = trunk.line.split()[1]
                trunk.number += trunk.digit
            
            if len(trunk.number) == 7:
                trunk.valid = True
                if trunk.number == "3319904":
                    trunk.active = True
                    radio.active = True
                    trunk.delay = True
                    print(trunk.number)
                    radio.ptt_off()

                    trunk.number = ''
                    print("Keying radio in 7 seconds")

                    radio.set_group(3)

                    trunk.time_delay = time.time() + 7

                    trunk.time_start = time.time() + 7
                    trunk.time_stop = time.time() + 37
                
                    radio.drop_time = trunk.time_start + 0.5
                else:
                    print(trunk.number + " is not a valid pager number, ignoring...")
                    trunk.number = ''
        else:
            if trunk.active:
                radio.poll()

            if trunk.delay and trunk.time_delay < time.time():
                radio.ptt_off()
                radio.ptt_on()
                radio.transmit = True
                radio.receive = False

                print("Using: Trunk_" + trunk.channel + " // Radio_" + radio.channel + " //")
                radio.patch(trunk)

                trunk.delay = False


            # Handle "bwong" call interrupt SFX from paging kirisun
            if ("AudioTrack: start(): 0x8fcf7e00, mState = 1" in radio.line) and (radio.transmit):
                radio.ptt_off()
                radio.transmit = False
                radio.receive = True
                radio.mute(trunk)
                radio.blank = True

            if ("AudioTrack: stop(): 0x8fcf7e00, mState = 0" in radio.line) and (radio.blank):
                radio.unmute(trunk)
                radio.blank = False

            #if "onPttChangeEvent:2-1" in radio.line and trunk.active and radio.drop_time < time.time():
            if ("AudioTrack: stop(): 0x8fcf8100, mState = 0" in radio.line) and (trunk.active): #and (radio.drop_time < time.time()):
                radio.drop_time = time.time() + 0.5
                print("***ptt dropped: re-keying radio***")
                radio.ptt_off()
                radio.ptt_on()
                radio.transmit = True
                radio.receive = False

            if (trunk.active) and ((time.time() > trunk.time_stop) or (not trunk.gpio())):
                print("unkeying radio...")
                radio.ptt_off()
                radio.transmit = False
                radio.receive = True
                radio.unpatch()
                print("[[PAGE DONE]]")

                radio.set_group(1)
                trunk.number = ''
                
                trunk.time_start = 0
                trunk.time_stop = 99999999999
                trunk.active = False
                trunk.valid = False
                radio.active = False

            if (not trunk.busy):
                trunk.valid = False

    except KeyboardInterrupt:
        radio.ptt_off()
        os.kill(trunk.dtmf.pid, 9)
        os.kill(radio.logcat.pid, 9)
        radio.unpatch()
        GPIO.cleanup()
        exit()

trunk_1 = Trunk("1", 17) 
trunk_2 = Trunk("2", 27)
trunk_3 = Trunk("3", 22)
trunk_4 = Trunk("4", 23)
trunk_5 = Trunk("5", 24)
trunk_6 = Trunk("6", 25)



radio_1 = Radio("1", radio_1_id)

radio_1.ptt_off()

while True:
    try:
        router(trunk_1, radio_1)
        router(trunk_2, radio_1)
        router(trunk_3, radio_1)
        router(trunk_4, radio_1)
        router(trunk_5, radio_1)
        router(trunk_6, radio_1)

    except KeyboardInterrupt:
        radio_1.ptt_off()
        os.kill(trunk_1.dtmf.pid, 9)
        os.kill(trunk_2.dtmf.pid, 9)
        os.kill(trunk_3.dtmf.pid, 9)
        os.kill(trunk_4.dtmf.pid, 9)
        os.kill(trunk_5.dtmf.pid, 9)
        os.kill(trunk_6.dtmf.pid, 9)
        


        os.kill(radio_1.logcat.pid, 9)
        
        radio_1.unpatch()
        GPIO.cleanup()
        exit()

