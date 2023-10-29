import json
import multiprocessing
import time

import win32process
import psutil
import pygetwindow as gw
from multiprocessing import Pool

from utils import *
from instance import Instance
import sys
import os

def waitForStats(inst: Instance, cfg: dict):
    token = cfg["token"]
    screenshotPercent = cfg["screenshot_percent"]
    crop = cfg["crop"]
    cropLeft = crop["left"]
    cropRight = crop["right"]
    cropTop = crop["top"]
    cropBottom = crop["bottom"]
    startTime = inst.getMTime()
    while True:
        newTime = inst.getMTime()
        if newTime != startTime:
            startTime = newTime
            newState = inst.getSplitState()

            if inst.state == Instance.STATE_RESETTING:
                if newState[0] == "previewing":
                    inst.state = Instance.STATE_PREVIEWING
                    inst.takenImage = False
                    continue
            elif inst.state == Instance.STATE_PREVIEWING:
                if newState[0] == "inworld":
                    inst.state = Instance.STATE_INWORLD
                    if not inst.takenImage:
                        if not psutil.pid_exists(inst.pid):  # if it's dead we'll find the instance again when it restarts
                            continue
                        print(f"Instance {inst.name} entered world without taking preview screenshot, taking late screenshot now")
                        inst.storeWorldPath()
                        inst.takenImage = True
                        inst.capture((cropLeft, cropRight, cropTop, cropBottom))
                    continue
                elif newState[0] == "previewing":
                    percent = int(newState[1])
                    if percent > screenshotPercent and not inst.takenImage:
                        inst.storeWorldPath()
                        inst.takenImage = True
                        if not psutil.pid_exists(inst.pid):
                            print(f"Instance {inst.name} was restarted, updating PID and HWND")
                            mcList = gw.getWindowsWithTitle('Minecraft*')
                            for mc in mcList:
                                hwnd = mc._hWnd
                                pid = win32process.GetWindowThreadProcessId(hwnd)[1]
                                process = psutil.Process(pid)
                                try:
                                    envi = process.environ()
                                except psutil.AccessDenied:
                                    print("Access denied for pid " + str(pid) + ", skipping")
                                    continue
                                if 'INST_ID' in envi and envi['INST_ID'] == inst.name:
                                    print(f"Found new PID {pid} and HWND {hwnd} for instance {inst.name}")
                                    inst.pid = pid
                                    inst.hwnd = hwnd
                                    inst.needsReprint = True
                                    break
                            continue
                        inst.capture((cropLeft, cropRight, cropTop, cropBottom))

                elif newState[0] == "resetting":
                    inst.state = Instance.STATE_RESETTING
                    continue
            elif inst.state == Instance.STATE_INWORLD:
                if newState[0] != "inworld":
                    inst.state = Instance.STATE_RESETTING
                    time.sleep(0.2)  # wait 200ms to make sure the record file was written
                    if inst.storeStats():
                        parseStats(inst, token)
                    continue
        time.sleep(0.1)

def findLatestWorld(savesPath: str):
    world = getMostRecentFile(savesPath + "Random Speedrun #*")
    return int(world.split("/")[-1].split("#")[1])

if __name__ == "__main__":
    multiprocessing.freeze_support()
    if getattr(sys, 'frozen', False):
        # pyinstaller exe
        workingDir = os.path.dirname(sys.executable)
    else:
        workingDir = os.path.dirname(os.path.abspath(__file__))

    configPath = workingDir + "/config.json"
    if not os.path.exists(configPath):
        print(f"\nNo config file found, generating new one at {configPath}")
        with open(configPath, "w") as f:
            f.write(json.dumps({
                "token": "PUT_TOKEN_HERE",
                "screenshot_percent": 70,
                "crop": {
                    "left": 0,
                    "right": 0,
                    "top": 0,
                    "bottom": 0
                }
            }, indent=2))
        print("Edit this file to add your auth token")
        print("If you don't have an auth token yet, go to https://spawn-image-5j3nqpagta-ue.a.run.app/register/USERNAME")
        print("Replace USERNAME with your desired username")
        print("Then, copy the token from the response and paste it into the config file")
        print("\nOnce you've done that, restart this program")

        time.sleep(1000000)  # keep the window open so they can read the message
        exit(1)

    with open(configPath, "r") as f:
        config = json.loads(f.read())
    token = config["token"]
    if token == "PUT_TOKEN_HERE":
        print(f"Please edit the config file ({configPath}) to add your auth token")
        exit(1)

    r = requests.get(f"https://spawn-image-5j3nqpagta-ue.a.run.app/getNameFromToken/{config['token']}")
    if r.status_code != 200:  # invalid token = 401
        print("Invalid auth token")
        exit()
    username = r.content.decode("utf-8")
    print(f"\nLogged in as {username}")

    mcList = gw.getWindowsWithTitle('Minecraft*')
    instances = []
    for mc in mcList:
        hwnd = mc._hWnd
        pid = win32process.GetWindowThreadProcessId(hwnd)[1]
        process = psutil.Process(pid)
        try:
            envi = process.environ()
        except psutil.AccessDenied:
            print("Access denied for pid " + str(pid) + ", skipping")
            continue
        if 'INST_ID' in envi:
            if not os.path.exists(envi['INST_DIR'] + "/.minecraft/wpstateout.txt"):
                print("Skipping instance " + envi['INST_ID'] + " since it doesn't have WorldPreview")
                continue
            inst = Instance(envi['INST_ID'], pid, hwnd, envi['INST_DIR'])
            instances.append(inst)

    if len(instances) == 0:
        print("No instances found")
        exit()
    instances.sort(key=lambda x: x.name)

    # can't Pool.map() directly over instances because Instance objects can't be pickled
    # so we just get the saves path for each instance and map over that
    savesPaths = []
    for inst in instances:
        savesPaths.append(inst.path + "/.minecraft/saves/")

    print("Looking for latest world in each instance...")
    with Pool(len(savesPaths)) as p:
        res = p.map(findLatestWorld, savesPaths)
        for i in range(len(res)):
            instances[i].lastWorldNum = res[i]

    print("\n\n---------------- Instances ----------------")
    print("Name\tPID\tPath")
    for inst in instances:
        print(f"{inst.name}\t{inst.pid}\t{inst.path}")
        th = threading.Thread(target=waitForStats, args=(inst, config))
        th.daemon = True
        th.start()
    print("-------------------------------------------\n")
    print("Ready")

    while True:
        # check if any instances have restarted, and we need to print updated list of instances
        reprint = False
        for inst in instances:
            if inst.needsReprint:
                reprint = True
                inst.needsReprint = False

        mcList = gw.getWindowsWithTitle('Minecraft*')
        if len(mcList) != len(instances):
            for mc in mcList:
                hwnd = mc._hWnd
                pid = win32process.GetWindowThreadProcessId(hwnd)[1]
                process = psutil.Process(pid)
                try:
                    envi = process.environ()
                except psutil.AccessDenied:
                    print("Access denied for pid " + str(pid) + ", skipping")
                    continue
                if 'INST_ID' in envi:
                    # check if instance already in list
                    # if an instance restarts that will be handled in the waitForStats thread,
                    # this loop is only for new unique instances
                    exists = False
                    for inst in instances:
                        if inst.name == envi['INST_ID']:
                            exists = True
                            break
                    if exists:
                        continue
                    if not os.path.exists(envi['INST_DIR'] + "/.minecraft/wpstateout.txt"):
                        continue
                    inst = Instance(envi['INST_ID'], pid, hwnd, envi['INST_DIR'])
                    instances.append(inst)
                    inst.lastWorldNum = findLatestWorld(inst.path + "/.minecraft/saves/")
                    th = threading.Thread(target=waitForStats, args=(inst, config))
                    th.daemon = True
                    th.start()
                    print(f"New instance found: {inst.name}")
                    reprint = True
        if reprint:
            print("\n\n---------------- Instances ----------------")
            print("Name\tPID\tPath")
            for inst in instances:
                print(f"{inst.name}\t{inst.pid}\t{inst.path}")
            print("-------------------------------------------\n")
        time.sleep(3)  # the above loop takes milliseconds at most, it's fine to run it every 3 seconds
