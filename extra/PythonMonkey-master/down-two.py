# Imports the monkeyrunner modules used by this program.
from monkeyrunner import MonkeyRunner, MonkeyDevice
import time
import os

# Connects to the current device, returning a MonkeyDevice object.
device = MonkeyRunner.waitForConnection(5)

# go up to top
device.press('KEYCODE_DPAD_DOWN', MonkeyDevice.DOWN_AND_UP)
time.sleep(0.2)
device.press('KEYCODE_DPAD_DOWN', MonkeyDevice.DOWN_AND_UP)
time.sleep(0.2)
