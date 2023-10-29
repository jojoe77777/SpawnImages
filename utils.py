import glob
import os
import threading

import requests

from instance import Instance

def getMostRecentFile(path: str):
    try:
        fileList = glob.glob(path.replace('\\', "/"))
        if not fileList:
            return False
        latest = max(fileList, key=os.path.getctime)
        return latest
    except:
        return False

def actuallyUploadImage(data: dict, img: str, token: str):
    requests.post("https://spawn-image-5j3nqpagta-ue.a.run.app/upload", json={
        "token": token,
        "data": data,
        "image": img
    })

def uploadImage(*args):
    t = threading.Thread(target=actuallyUploadImage, args=args)
    t.start()

def parseStats(inst: Instance, token: str):
    record = inst.record
    adv = record["advancements"]
    uuids = list(record["stats"].keys())
    stats = []
    if len(uuids) > 0:
        stats = record["stats"][uuids[0]]["stats"]
    openLan = record["open_lan"]
    if openLan is not None and openLan < 30000:  # ignore run if opened to lan in first 30 seconds rta of world
        return

    finalTime = record["final_igt"]
    if finalTime == 0:
        return

    biome = "unknown"
    if "minecraft:adventure/adventuring_time" in adv:
        biomes = adv["minecraft:adventure/adventuring_time"]["criteria"]
        for b in biomes:
            if biomes[b]["igt"] == 0:
                biome = b
                break

    lava = False
    if "minecraft:story/lava_bucket" in adv:
        lava = adv["minecraft:story/lava_bucket"]["complete"]

    chestOpened = False
    if "minecraft:custom" in stats:
        custom = stats["minecraft:custom"]
        if "minecraft:open_chest" in custom:
            chestOpened = custom["minecraft:open_chest"] > 0

    sandMined = 0
    gravelMined = 0
    logsMined = 0
    magmaMined = 0
    if "minecraft:mined" in stats:
        mined = stats["minecraft:mined"]
        if "minecraft:sand" in mined:
            sandMined = mined["minecraft:sand"]
        if "minecraft:gravel" in mined:
            gravelMined = mined["minecraft:gravel"]
        for logType in ["oak", "birch", "spruce", "jungle", "acacia", "dark_oak"]:
            if f"minecraft:{logType}_log" in mined:
                logsMined += mined[f"minecraft:{logType}_log"]
        if "minecraft:magma_block" in mined:
            magmaMined = mined["minecraft:magma_block"]

    ironPick = False
    goldPick = False
    if "minecraft:crafted" in stats:
        crafted = stats["minecraft:crafted"]
        if "minecraft:iron_pickaxe" in crafted or "minecraft:diamond_pickaxe" in crafted:
            ironPick = True
        if "minecraft:gold_pickaxe" in crafted:
            goldPick = True

    netherIgt = 0
    for timeline in record["timelines"]:
        if timeline["name"] == "enter_nether":
            netherIgt = timeline["igt"]
            break

    data = {
        "biome": biome,
        "lava": lava,
        "chest": chestOpened,
        "sand": sandMined,
        "gravel": gravelMined,
        "logs": logsMined,
        "magma": magmaMined,
        "iron_pick": ironPick,
        "gold_pick": goldPick,
        "nether_igt": netherIgt,
        "final_igt": finalTime
    }

    print(f"Uploading run: " + str(data))
    uploadImage(data, inst.img, token)