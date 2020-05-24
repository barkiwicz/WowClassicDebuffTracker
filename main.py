import argparse, csv, re, pprint, datetime

"""
Expected file format:

5/21 21:28:35.045  ENCOUNTER_START,664,"Magmadar",9,40,409
5/21 21:28:36.272  SPELL_AURA_APPLIED,Player-4372-00128F78,"Lilnott-Atiesh",0x40514,0x0,Creature-0-4377-409-22615-11982-000047218A,"Magmadar",0x10a48,0x0,17392,"Faerie Fire (Feral)",0x8,DEBUFF
5/21 21:28:38.708  SPELL_AURA_REMOVED,Player-4372-00DCB2B5,"Acidberry-Atiesh",0x512,0x0,Creature-0-4377-409-22615-11982-000047218A,"Magmadar",0x10a48,0x0,17937,"Curse of Shadow",0x20,DEBUFF
5/21 21:28:43.183  SPELL_AURA_REFRESH,Player-4372-0107CF35,"Dispholidus-Atiesh",0x514,0x0,Creature-0-4377-409-22615-11982-000047218A,"Magmadar",0x10a48,0x0,12721,"Deep Wound",0x1,DEBUFF

"""

max_debuffs = 16
debug = False
debuff_list = []
encounter_start_data = []
last_timestamp = 0
last_push_off_timestamp = 0

valid_event_list = ["SPELL_AURA_APPLIED",
                    "SPELL_AURA_APPLIED_DOSE",
                    "SPELL_AURA_REMOVED",
                    "SPELL_AURA_REFRESH",
                    "ENCOUNTER_START",
                    "ENCOUNTER_END"]
valid_encounter_list = ["Lucifron",
                        "Magmadar",
                        "Gehennas",
                        "Garr",
                        "Baron Geddon",
                        "Shazzrah",
                        "Sulfuron Harbinger",
                        "Golemagg the Incinerator",
                        "Majordomo Executus",
                        "Ragnaros",
                        "Razorgore",
                        "Vaelastraz the Corrupted",
                        "Broodlord Lashlayer",
                        "Firemaw",
                        "Ebonroc",
                        "Flamegor",
                        "Chromaggus",
                        "Nefarian"]

debuff_durations_list = [
    {"debuff": "Armor Shatter", "duration": 45},
    {"debuff": "Corruption", "duration": 18},
    {"debuff": "Curse of Agony", "duration": 24},
    {"debuff": "Curse of the Elements", "duration": 300},
    {"debuff": "Curse of Recklessness", "duration": 120},
    {"debuff": "Curse of Shadow", "duration": 300},
    {"debuff": "Curse of Tongues", "duration": 30},
    {"debuff": "Deaden Magic", "duration": 30},
    {"debuff": "Deadly Poison IV", "duration": 12},
    {"debuff": "Deep Wound", "duration": 12},
    {"debuff": "Demoralizing Shout", "duration": 30},
    {"debuff": "Drain Life", "duration": 5},
    {"debuff": "Drain Soul", "duration": 15},
    {"debuff": "Faerie Fire (Feral)", "duration": 40},
    {"debuff": "Faerie Fire", "duration": 40},
    {"debuff": "Flare", "duration": 30},
    {"debuff": "Gift of Arthas", "duration": 180},
    {"debuff": "Hunter's Mark", "duration": 120},
    {"debuff": "Inferno", "duration": 2},
    {"debuff": "Inspire", "duration": 10},
    {"debuff": "Judgement of Light", "duration": 20},
    {"debuff": "Judgement of Wisdom", "duration": 20},
    {"debuff": "Rip", "duration": 12},
    {"debuff": "Screech", "duration": 4},
    {"debuff": "Shadowburn", "duration": 5},
    {"debuff": "Siphon Life", "duration": 30},
    {"debuff": "Shadow Vulnerability", "duration": 12},
    {"debuff": "Shadow Weaving", "duration": 15},
    {"debuff": "Sunder Armor", "duration": 30},
    {"debuff": "Taunt", "duration": 3},
    {"debuff": "Thunderfury", "duration": 12},
    {"debuff": "Winter's Chill", "duration": 15}
]

"""
- parse log and build stack of debuffs
- when debuff fades, if another debuff is added at the same timestamp, we assume it pushed the other off
- 


"""

def short_event_str(event_type):
    if (event_type == "SPELL_AURA_APPLIED"):
        return "applied"
    elif (event_type == "SPELL_AURA_REMOVED"):
        return "removed"
    elif (event_type == "SPELL_AURA_REFRESH"):
        return "refresh"
    elif (event_type == "ENCOUNTER_START"):
        return "start"
    elif (event_type == "ENCOUNTER_END"):
        return "end"

def event_is_applied(event_type):
    if (event_type == "SPELL_AURA_APPLIED"):
        return True
    return False

def event_is_applied_dose(event_type):
    if (event_type == "SPELL_AURA_APPLIED_DOSE"):
        return True
    return False

def event_is_removed(event_type):
    if (event_type == "SPELL_AURA_REMOVED"):
        return True
    return False

def event_is_refresh(event_type):
    if (event_type == "SPELL_AURA_REFRESH"):
        return True
    return False

def event_is_start(event_type):
    if (event_type == "ENCOUNTER_START"):
        return True
    return False

def event_is_end(event_type):
    if (event_type == "ENCOUNTER_END"):
        return True
    return False

def is_stacking_debuff(debuff_type):
    if debuff_type in stacking_debuff_list:
        return True
    return False

def handle_debuff(event):
    global debuff_list
    # since there can be more than one target in a log, the debuff list is actually a list of lists
    if not debuff_list:
        print("=============================================================================")
        print("Encounter: " + event["target"])
        print("=============================================================================")
        d = {"target" : event["target"], "debuffs" : []}
        d_copy = d.copy()
        debuff_list.append(d_copy)
    elif not (next((item for item in debuff_list if item["target"] == event["target"]), False)):
        print("=============================================================================")
        print("Encounter: " + event["target"])
        print("=============================================================================")
        d = {"target" : event["target"], "debuffs" : []}
        d_copy = d.copy()
        debuff_list.append(d_copy)
    else:
        d = next((item for item in debuff_list if item["target"] == event["target"]))

    if (event_is_applied(event["type"])):
        found = False
        for i in d["debuffs"]:
            if ((i["debuff"] == event["debuff"]) and (i["source"] == event["source"])):
                print("WARNING: Duplicate apply with no remove:")
                i["time"] = event["time"]
                found = True
        if not (found):
            new_debuff = {"time" : event["time"], "debuff" : event["debuff"], "source" : event["source"]}
            new_debuff_copy = new_debuff.copy()
            d["debuffs"].append(new_debuff_copy)
    elif (event_is_refresh(event["type"])):
        # find the matching debuff in the list and update the start time
        found = False
        for i in d["debuffs"]:
            if ((i["debuff"] == event["debuff"]) and (i["source"] == event["source"])):
                i["time"] = event["time"]
                found = True
        if not (found):
            new_debuff = {"time" : event["time"], "debuff" : event["debuff"], "source" : event["source"]}
            new_debuff_copy = new_debuff.copy()
            d["debuffs"].append(new_debuff_copy)
    elif (event_is_removed(event["type"])):
        # find the matching debuff in the list and update the start time
        found = False
        for i in d["debuffs"]:
            if ((i["debuff"] == event["debuff"]) and (i["source"] == event["source"])):
                d["debuffs"].remove(i)
                found = True
                break
        if not (found):
            print ("WARNING: Delete with no existing debuff:")
  
    if (event_is_refresh(event["type"])):
        print("{:6.3f}: ".format(event["time"]) + short_event_str(event["type"]) + " " + event["debuff"] + " on " + event["target"] + " from " + event["source"])
        pass
    else:
        print("{:6.3f}: ".format(event["time"]) + short_event_str(event["type"]) + " " + event["debuff"] + " on " + event["target"] + " from " + event["source"] + " (" + str(len(d["debuffs"])) + " debuffs)")
        pass

def keep_entry(event):
    # is the event type is something we care about?
    if event[1] not in valid_event_list:
        return False
    # is the target of this event a boss?
    if ((event[1] != "ENCOUNTER_START") and (event[1] != "ENCOUNTER_END")):
        if (event[7] not in valid_encounter_list):
            return False
    return True

def parse_file(file):
    # parse to a list of lists
    print("Parsing file")

    line = file.readline()
    raw_data = []

    while line:
        # replace the double-whitespace delimiter with a comma
        line = re.sub('  ',',', line)
        line = re.sub('\"','', line)
        event = re.split(r',', line)
        # get rid of anything we don't care about
        if (keep_entry(event)):
            raw_data.append(event)

        line = file.readline()

    if (debug):
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(raw_data)
    return (raw_data)

def parse_raw_data(raw_data):
    global encouter_start_data
    # We need to split the columns into all the components:
    # - timestamp
    # - add/delete/refresh
    # - target
    # - source
    # - debuff

    # it's inefficient, but we'll cycle the list twice to build the start times first
    print("Encounters in log:")
    for l in raw_data:
        if (event_is_start(l[1])):
            t = re.split(' |/|:|\.', l[0])
            start = datetime.datetime(2020, int(t[0]), int(t[1]), int(t[2]), int(t[3]), int(t[4]), int(t[5]) * 1000)
            d = {"debuff" : l[3], "start" : start}
            d_copy = d.copy()
            encounter_start_data.append(d_copy)
            print(d["debuff"] + " : ")
            print(start)

    debuff_data = []
    for l in raw_data:
        event_type = l[1]

        if (event_is_applied_dose(event_type)):
            event_type = "SPELL_AURA_REFRESH"

        if ((event_is_start(l[1])) or (event_is_end(l[1]))):
            continue

        # the tricky part is we want to split this up per-encounter and start the timer
        # at the start of an encounter
        t = re.split(' |/|:|\.', l[0])
        absolute_time = datetime.datetime(2020, int(t[0]), int(t[1]), int(t[2]), int(t[3]), int(t[4]), int(t[5]) * 1000)
        # the timestamp is relative to the start of the encounter in seconds
        d = next(item for item in encounter_start_data if item["debuff"] == l[7])
        difference = absolute_time - d["start"]
        event_time = difference.total_seconds()
        event_target = l[7]
        event_source = l[3]
        event_debuff = l[11]
        if (debug):
            print(str(event_time) + ": " + short_event_str(event_type) + " " + event_debuff + " on " + event_target + " from " + event_source)
            pass
        d = {"time" : event_time, "type" : event_type, "debuff" : event_debuff, "target" : event_target, "source" : event_source}
        d_copy = d.copy()
        debuff_data.append(d_copy)
    
    return (debuff_data)

def get_debuff_duration(debuff_name):
    global debuff_durations_list
    try:
        i = next(item for item in debuff_durations_list if item["debuff"] == debuff_name)
    except:
        print(debuff_name + " is not in the debuff list.")
    return (i["duration"])

def dump_at_timestamp(debuff_data, event):
    global debuff_list
    global last_timestamp

    if (last_timestamp == event["time"]):
        return

    last_timestamp = event["time"]

    d = next((item for item in debuff_list if item["target"] == event["target"]))

    print("-----------------------------------------------------------------------------")
    print("Debuff pushed off at " + str(event["time"]))
    print("Events at current timestamp:")
    for i in debuff_data:
        if ((i["time"] == event["time"]) and (i["target"] == event["target"])):
            print(" " + short_event_str(i["type"]) + " " + i["debuff"] + " on " + i["target"] + " from " + i["source"])

    print("Debuffs before timestamp: " + str(len(d["debuffs"])))

    for i in d["debuffs"]:
        remaining_time = get_debuff_duration(i["debuff"]) + i["time"] - event["time"]
        print(" " + i["debuff"] + " from " + i["source"] + " (added: {:.3f}".format(i["time"]) + ", estimated remaining: {:.3f}".format(remaining_time) + ")")
    print("-----------------------------------------------------------------------------")

def handle_push_off(debuff_data, event):
    global last_push_off_timestamp

    if (last_push_off_timestamp == event["time"]):
        return

    last_push_off_timestamp = event["time"]
    add_found = False
    delete_found = False

    # search the entries at the current timestamp to see if we have both a delete and add/refresh
    # if we have both, then one buff has pushed another off
    for i in debuff_data:
        if ((i["time"] == event["time"]) and (i["target"] == event["target"])):
            if (event_is_removed(i["type"])):
                delete_found = True
            elif (event_is_applied(i["type"])):
                add_found = True
            elif (event_is_refresh(i["type"])):
                add_found = True

    if ((add_found) and (delete_found)):
        # we found an add and delete
        dump_at_timestamp(debuff_data, event)

    return

def walk_debuffs(debuff_data):
    if (debug):
        #pp = pprint.PrettyPrinter(indent=4)
        #pp.pprint(debuff_data)
        pass
    # when adding:
    # - add to the debuff list
    # when deleting:
    # - remove from the debuff list
    #   - if there's an add at the same timestamp, flag this as a push-off
    # when refreshing:
    # - refresh the timestamp on the current buff
    print("Walking debuffs")

    for i in debuff_data:
        handle_push_off(debuff_data, i)
        handle_debuff(i)

def dump_debuffs():
    global debuff_list

    found = False
    for i in debuff_list:
        if i["debuffs"]:
            found = True

    if not (found):
        return

    print("---------------------------------------------------")
    print("Stale debuffs:")
    for i in debuff_list:
        if i["debuffs"]:
            print(debuff_list)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('file')
    args = parser.parse_args()

    print(args)

    with open(args.file, encoding="utf8") as file:
        # parse input file and return a list of lists
        raw_data = parse_file(file)

        debuff_data = parse_raw_data(raw_data)

        # walk debuffs
        walk_debuffs(debuff_data)

        # dump remaining debuffs (this should be empty)
        dump_debuffs()


if __name__ == "__main__":
    # execute only if run as a script
    main()
