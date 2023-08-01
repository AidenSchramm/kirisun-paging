#!/usr/bin/python

import time
import signal
import sys
import subprocess
import os
from multiprocessing import Pool, Process, Manager

radio_1_id = "SK7SPJ8PY9OJZ5EU"

class Trunk:
    def __init__(self, index):
        self.channel = index
        self.dtmf = subprocess.Popen("parec --channels=1 -d alsa_input.Trunk_" + self.channel + ".mono-fallback | multimon-ng -a DTMF", 
                                                                                stdout=subprocess.PIPE, stderr=open('/dev/null','a'), shell=True)
        self.number = ''
        self.digit  = ''
        self.time_start = 0
        self.time_stop  = 0
        self.active = False

        self.data = ""
        self.line = ""

    def poll(self):
        self.data = self.dtmf.stdout.readline()
        self.line = self.data.decode('utf-8')
        self.dtmf.poll()

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

        self.data = ""
        self.line = ""

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
        os.system("pactl unload-module " + self.mic_id)
        os.system("pactl unload-module " + self.speaker_id)

def router(trunk, radio):
    try:
        radio.ptt_off()
        while True:
            if not trunk.active:
                trunk.poll()

                if "DTMF:" in trunk.line:
                    trunk.digit = trunk.line.split()[1]
                    trunk.number += trunk.digit
                if len(trunk.number) == 7:
                    trunk.active = True
                    print(trunk.number)

                    trunk.number = ''
                    print("Keying radio in 7 seconds")
                    time.sleep(7)
                    radio.ptt_off()
                    radio.ptt_on()

                    radio.patch(trunk)

                    trunk.time_start = time.time()
                    trunk.time_stop = time.time() + 30
                    
                    radio.drop_time = trunk.time_start + 0.5
            else:
                radio.poll()

                if "onPttChangeEvent:2-1" in radio.line and trunk.active and radio.drop_time < time.time():
                    radio.drop_time = time.time() + 0.5
                    print("***ptt dropped: re-keying radio***")
                    radio.ptt_off()
                    radio.ptt_on()

                if trunk.active and (time.time() > trunk.time_stop):
                    print("unkeying radio...")
                    radio.ptt_off()
                    radio.unpatch()
                    print("[[PAGE DONE]]")
                    trunk.number = ''
                    
                    trunk.time_start = 0
                    trunk.time_stop = 99999999999
                    trunk.active = False

    except KeyboardInterrupt:
        radio.ptt_off()
        os.kill(trunk.dtmf.pid, 9)
        os.kill(radio.logcat.pid, 9)
        os.system("pactl unload-module " + radio.mic_id)
        os.system("pactl unload-module " + radio.speaker_id)



trunk_1 = Trunk("1")
radio_1 = Radio("1", radio_1_id)

router(trunk_1, radio_1)












'''
try:
    os.system(radio_1_ptt_off)
    #os.system(radio_2_ptt_off)
    #os.system(radio_3_ptt_off)
    #os.system(radio_4_ptt_off)
    #os.system(radio_5_ptt_off)
    #os.system(radio_6_ptt_off)

    while True:
        if not trunk_1_active:
            trunk_1_dtmf_data = trunk_1_dtmf.stdout.readline()
            trunk_1_dtmf_line = trunk_1_dtmf_data.decode('utf-8')
            trunk_1_dtmf.poll()

            trunk_2_dtmf_data = trunk_2_dtmf.stdout.readline()
            trunk_2_dtmf_line = trunk_2_dtmf_data.decode('utf-8')
            trunk_2_dtmf.poll()
        
            if "DTMF:" in trunk_1_dtmf_line:    # filter out only the DTMF
                trunk_1_digit = trunk_1_dtmf_line.split()[1]
                trunk_1_number += trunk_1_digit
            if len(trunk_1_number) == 7:
                print(trunk_1_number)
                print("keying radio in 7 seconds...")
                time.sleep(7)
                os.system(radio_1_ptt_off)
                os.system(radio_1_ptt_on)
                trunk_1_active = True
            
                time_start = time.time()
                time_stop = time.time() + 30
                drop_time = time_start + 0.5
            
                print(time_start)
                print(time_stop)
                trunk_1_number = ''
        
        
        radio_1_logcat_data = radio_1_logcat.stdout.readline()
        radio_1_logcat_line = radio_1_logcat_data.decode('utf-8')
        radio_1_logcat.poll()
        
        
        
        if "onPttChangeEvent:2-1" in radio_1_logcat_line and trunk_1_active and drop_time < time.time():
            drop_time = time.time() + 0.5
            print("***ptt dropped: re-keying radio***")
            os.system(radio_1_ptt_off)
            os.system(radio_1_ptt_on)
                    
            
        if trunk_1_active and (time.time() > time_stop):
            print("unkeying radio...")
            os.system(radio_1_ptt_off)
            print("[[PAGE DONE]]")
            trunk_1_number = ''
            
            time_start = 0
            time_stop = 99999999999
            trunk_1_active = False

except KeyboardInterrupt:
    os.kill(trunk_1_dtmf.pid, 9)
'''
