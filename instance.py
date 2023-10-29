import os
import time

import win32con
import win32gui
import win32ui
from PIL import Image
import json
import base64
from io import BytesIO

class Instance(object):

    STATE_RESETTING = 0
    STATE_PREVIEWING = 1
    STATE_INWORLD = 2

    def __init__(self, name, pid, hwnd, path):
        self.name = name
        self.pid = pid
        self.hwnd = hwnd
        self.path = path
        self.state = self.STATE_INWORLD
        self.statePath = path + "/.minecraft/wpstateout.txt"
        self.stateFile = open(self.statePath, "r")

        self.takenImage = False
        self.worldPath = None
        self.img = None
        self.record = None
        self.lastWorldNum = None
        self.needsReprint = False

    def storeWorldPath(self):
        path = self.path
        while True:
            world = f"{path}/.minecraft/saves/Random Speedrun #{self.lastWorldNum + 1}"
            if not os.path.exists(world):  # if next world doesn't exist, use current world
                self.worldPath = f"{path}/.minecraft/saves/Random Speedrun #{self.lastWorldNum}"
                return
            self.lastWorldNum += 1

    def storeStats(self):
        if self.worldPath is None:
            return False

        record = self.worldPath + "/speedrunigt/record.json"
        if not os.path.exists(record):
            print("No record file found for " + self.worldPath)
            return False
        with open(record, "r") as f:
            self.record = json.loads(f.read())
        return True

    def getMTime(self):
        return os.path.getmtime(self.statePath)

    def getStateStr(self):
        while True:
            self.stateFile.seek(0)
            contents = self.stateFile.read()
            if contents == "":
                time.sleep(0.0001)
                continue
            return contents

    def getSplitState(self):
        return self.getStateStr().split(",")

    def capture(self, crop):
        # get crop settings
        left, right, top, bottom = crop

        # get window size
        rect = win32gui.GetWindowRect(self.hwnd)
        x = rect[0]
        y = rect[1]
        width = rect[2] - x
        height = rect[3] - y

        # calculate new size after cropping
        newWidth = width - left - right
        newHeight = height - top - bottom

        # capture image
        wDC = win32gui.GetWindowDC(self.hwnd)
        dcObj = win32ui.CreateDCFromHandle(wDC)
        cDC = dcObj.CreateCompatibleDC()
        dataBitMap = win32ui.CreateBitmap()
        dataBitMap.CreateCompatibleBitmap(dcObj, newWidth, newHeight)
        cDC.SelectObject(dataBitMap)
        cDC.BitBlt((0, 0), (newWidth, newHeight), dcObj, (left, top), win32con.SRCCOPY)
        bmpinfo = dataBitMap.GetInfo()
        bmpstr = dataBitMap.GetBitmapBits(True)

        # create Pillow image object
        im = Image.frombuffer(
            'RGB',
            (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
            bmpstr, 'raw', 'BGRX', 0, 1)

        # resize Pillow image to thumbnail size, 0 = antialias
        im2 = im.resize((480, 270), 0)
        buffer = BytesIO()
        im2.save(buffer, format="jpeg", subsampling=0, quality=95)
        self.img = base64.b64encode(buffer.getvalue()).decode("utf-8")

        # close and release resources
        im.close()
        im2.close()
        buffer.close()
        dcObj.DeleteDC()
        cDC.DeleteDC()
        win32gui.ReleaseDC(self.hwnd, wDC)
        win32gui.DeleteObject(dataBitMap.GetHandle())

    def __str__(self):
        return self.name + " (" + str(self.pid) + ")"

