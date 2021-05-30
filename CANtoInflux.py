# TODO: timestamp data frames

import time
import requests
import os
import threading

from pyvit import can
from pyvit.hw import socketcan

# Globals
dataBuf = ''                                                                    # buffer will hold data to push to InfluxDB
influxURL = 'http://localhost:8086/write?db=car&precision=ms'                   # local InfluxDB server URL
CAN_BITRATE = 250000
rxFrames = []

# Data to capture
rpm = 0
waterTemp = 0
wheelSpeed = 0
gear = 0

# CAN IDs
PE1_ID = 0x0CFFF048
PE6_ID = 0x0CFFF548
THERMOCOUPLE_A_ID = 0x1E
THERMOCOUPLE_B_ID = 0x1F

canBus = socketcan.SocketCanDev("can0")

def addToData(key, value):                                                      # function to build InfluxDB line protocol strings
    global dataBuf
    dataBuf += '\n' + f'{key} value={value}'                                    # add up multiple data points to send to InfluxDB

def sendData():
    global dataBuf
    requests.post(influxURL, data = dataBuf)
    print('data pushed')
    dataBuf = ''                                                                # clear out buffer
    threading.Timer(1, sendData).start()                                        # run this func periodically

def readFrames():
    inMsg = canBus.recv()

    if inMsg.arb_id == PE1_ID:
        rpm = ((inMsg.data[1] << 8) + inMsg.data[0])
        addToData('rpm', rpm)

    elif inMsg.arb_id == PE6_ID:
        newTemp = ((inMsg.data[5] << 8) + inMsg.data[4])
        if (newTemp > 32767):
            newTemp = newTemp - 65536
        waterTemp = ((newTemp / 10.0) * 1.8) + 32                               # link fury specific, convert to F
        addToData('waterTemp', waterTemp)

    elif inMsg.arb_id == THERMOCOUPLE_A_ID:
        tempArray = [0, 0, 0, 0]

        tempArray[0] = (inMsg.data[0] << 8) + inMsg.data[1]
        tempArray[1] = (inMsg.data[2] << 8) + inMsg.data[3]
        tempArray[2] = (inMsg.data[4] << 8) + inMsg.data[5]
        tempArray[3] = (inMsg.data[6] << 8) + inMsg.data[7]

        addToData('therm1', tempArray[0])
        addToData('therm2', tempArray[1])
        addToData('therm3', tempArray[2])
        addToData('therm4', tempArray[3])

    elif inMsg.arb_id == THERMOCOUPLE_B_ID:
        tempArray = [0]

        tempArray[0] = (inMsg.data[0] << 8) + inMsg.data[1]

        addToData('therm5', tempArray[0])

#                                                               ------ Enter Program -----



for i in range (0, 40):                                                         # burn time as influxDB and Grafana start up
    os.system('echo 0 | sudo tee /sys/class/leds/led1/brightness > /dev/null')  # turn off red PWR led (send print output to null)
    time.sleep(0.5)
    os.system('echo 1 | sudo tee /sys/class/leds/led1/brightness > /dev/null')  # turn on red PWR led (send print output to null)
    time.sleep(0.5)

os.system(f'sudo ip link set can0 up type can bitrate {str(CAN_BITRATE)}')      # bring up CAN bus (USB CANable device)
canBus.start()                                                                  # fire up CANable connection to library

os.system('echo 1 | sudo tee /sys/class/leds/led1/brightness > /dev/null')      # turn on red PWR led (send print output to null)

threading.Timer(1, sendData).start()                                            # run this func periodically

counter = 0
while 1:
    readFrames()
