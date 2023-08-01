#!/bin/bash

# trap ctrl-c and call ctrl_c()
trap ctrl_c INT

function ctrl_c() {
    eval "$PTT_OFF"
    pkill -9 -f "adb logcat"
    echo "exiting"
    exit
}

PTT_ON="adb shell sendevent /dev/input/event1 1 60 1; adb shell sendevent /dev/input/event1 0 0 0"
PTT_OFF="adb shell sendevent /dev/input/event1 1 60 0; adb shell sendevent /dev/input/event1 0 0 0" 

eval "$PTT_OFF"
sleep 0.1
eval "$PTT_ON"
sleep 0.5


# Watch output from logcat and trigger anytime the PTT is "released"
adb logcat | awk '
    { command = "set -o xtrace; echo OFF; \
                 adb shell sendevent /dev/input/event1 1 60 0; adb shell sendevent /dev/input/event1 0 0 0 \
                 ; echo ON; \
                 adb shell sendevent /dev/input/event1 1 60 1; adb shell sendevent /dev/input/event1 0 0 0 \
                 >/dev/null 2>&1" }  
    /onPttChangeEvent:2-1/ { system(command) }
    /new USB high speed/  { system("echo \"New USB\" | mail admin") }'
    
