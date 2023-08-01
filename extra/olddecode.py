#!/usr/bin/python

'''

!! This requires a recent build of Multimon-NG as the old builds wont accept a piped input !!

Change the rtl_fm string to suit your needs.. add -a POCSAG512 , 2400 etc if needed to the Multimon-ng string
This just prints and writes to a file, you can put it in a threaded class and pass though a queue or whatever suits your needs.


'''
import time
import signal
import time
import sys
import subprocess
import os

radio_1 = "SK7SPJ8PY9OJZ5EU"
radio_2 = ""
radio_3 = ""
radio_4 = ""
radio_5 = ""
radio_6 = ""


adb_logcat = subprocess.Popen("adb logcat", stdout=subprocess.PIPE, stderr=open('/dev/null','a'), shell=True)

multimon_ng = subprocess.Popen("parec --channels=1 --rate=22050 -d alsa_input.Trunk_1.mono-fallback  | multimon-ng -a DTMF",
                               stdout=subprocess.PIPE,
                               stderr=open('/dev/null','a'),
                               shell=True)

# parecord --channels=1 -d alsa_input.Trunk_1.mono-fallback | sox -t raw -esigned-integer -b 16 -r 48000 - -esigned-integer -b 16 -r 22050 -t raw - | multimon-ng -a DTMF
# parecord --channels=1 -d alsa_input.Trunk_1.mono-fallback - | sox -t raw -esigned-integer -b 16 -r 48000 - -esigned-integer -b 16 -r 22050 -t raw - | multimon-ng -a DTMF

number = ''
digit = ''
in_progress = False
time_start = 0
time_stop = 0
drop_time = 0

try:
    os.system("adb shell sendevent /dev/input/event1 1 60 0; adb shell sendevent /dev/input/event1 0 0 0")

    while True:
        if not in_progress:
            multimon_data = multimon_ng.stdout.readline()
            multimon_line = multimon_data.decode('utf-8')
            multimon_ng.poll()
         
            if "DTMF:" in multimon_line:    # filter out only the DTMF
                digit = multimon_line.split()[1]
                number += digit
            if len(number) == 7:
                print(number)
                print("keying radio in 7 seconds...")
                time.sleep(7)
                os.system("adb shell sendevent /dev/input/event1 1 60 0; adb shell sendevent /dev/input/event1 0 0 0")
                os.system("adb shell sendevent /dev/input/event1 1 60 1; adb shell sendevent /dev/input/event1 0 0 0")
                in_progress = True
            
                time_start = time.time()
                time_stop = time.time() + 30
                drop_time = time_start + 0.5
            
                print(time_start)
                print(time_stop)
                number = ''
        
        
        adb_logcat_data = adb_logcat.stdout.readline()
        adb_logcat_line = adb_logcat_data.decode('utf-8')
        adb_logcat.poll()
        
        
        
        if "onPttChangeEvent:2-1" in adb_logcat_line and in_progress and drop_time < time.time():
            drop_time = time.time() + 0.5
            os.system("adb shell sendevent /dev/input/event1 1 60 0; adb shell sendevent /dev/input/event1 0 0 0")
            os.system("adb shell sendevent /dev/input/event1 1 60 1; adb shell sendevent /dev/input/event1 0 0 0")
            
            
        if in_progress and (time.time() > time_stop):
            print("unkeying radio...")
            os.system("adb shell sendevent /dev/input/event1 1 60 0; adb shell sendevent /dev/input/event1 0 0 0")
            print("[[PAGE DONE]]")
            number = ''
            
            time_start = 0
            time_stop = 99999999999
            in_progress = False

except KeyboardInterrupt:
    os.kill(multimon_ng.pid, 9)
