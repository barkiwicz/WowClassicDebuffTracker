import argparse, csv, re, pprint

"""

Expected file format:

"Time","Event",""
"00:00:01.215","Vaelastrasz the Corrupt is afflicted by  Curse of Recklessness  from Hrocdol",""
"00:00:02.432","Vaelastrasz the Corrupt is afflicted by  Faerie Fire (Feral)  from Bag",""
"00:00:03.640","Vaelastrasz the Corrupt is afflicted by  Sunder Armor  from Dispholidus",""

"""

max_debuffs = 16
debug = False
debuff_list = []
last_timestamp = 0
last_push_off_timestamp = 0
stacking_debuff_list = ["Armor Shatter",
                        "Curse of Elements",
                        "Curse of Shadow",
                        "Curse of Recklessness",
                        "Deep Wound", 
                        "Demoralizing Shout",
                        "Gift of Arthas",
                        "Hunter's Mark",
                        "Shadow Vulnerability",
                        "Sunder Armor",
                        "Winter's Chill"]
precast_debuff_list = ["Hunter's Mark"]
debuff_durations_list = [
    {"name": "Armor Shatter", "duration": 45},
    {"name": "Corruption", "duration": 12},
    {"name": "Curse of Agony", "duration": 24},
    {"name": "Curse of the Elements", "duration": 300},
    {"name": "Curse of Recklessness", "duration": 120},
    {"name": "Curse of Shadow", "duration": 300},
    {"name": "Curse of Tongues", "duration": 30},
    {"name": "Deep Wound", "duration": 12},
    {"name": "Demoralizing Shout", "duration": 30},
    {"name": "Faerie Fire (Feral)", "duration": 40},
    {"name": "Faerie Fire", "duration": 40},
    {"name": "Gift of Arthas", "duration": 180},
    {"name": "Hunter's Mark", "duration": 120},
    {"name": "Judgement of Light", "duration": 20},
    {"name": "Judgement of Wisdom", "duration": 20},
    {"name": "Screech", "duration": 4},
    {"name": "Siphon Life", "duration": 30},
    {"name": "Shadow Vulnerability", "duration": 12},
    {"name": "Shadow Weaving", "duration": 15},
    {"name": "Sunder Armor", "duration": 30},
    {"name": "Thunderfury", "duration": 12},
    {"name": "Winter's Chill", "duration": 15}
]

"""
- parse log and build stack of debuffs
- when debuff fades, if another debuff is added at the same timestamp, we assume it pushed the other off
- 


"""

def convert_to_seconds(raw_timestamp):
    word = raw_timestamp.split(':', 3)
    time = float(word[0]) * 60 * 60
    time += float(word[1]) * 60
    time += float(word[2])
    return (time)

def get_event_type(raw_event):
    if (re.search("is afflicted by", raw_event)):
        return("add")
    elif (re.search("is refreshed by", raw_event)):
        return("refresh")
    elif (re.search("\A[\D]+ fades from", raw_event)):
        return("delete")
    return("skip")

def event_is_add(event_type):
    if (event_type == "add"):
        return True
    return False

def event_is_refresh(event_type):
    if (event_type == "refresh"):
        return True
    return False

def event_is_delete(event_type):
    if (event_type == "delete"):
        return True
    return False

def event_is_skip(event_type):
    if (event_type == "skip"):
        return True
    return False

def get_event_target(raw_event, event_type):
    if (event_is_add(event_type)):
        m = re.match(r"(.*) is afflicted by", raw_event)
        event_target = m.group(1)
    elif (event_is_refresh(event_type)):
        m = re.match(r"(.*)'s", raw_event)
        event_target = m.group(1)
    elif (event_is_delete(event_type)):
        m = re.match(r"(.*) fades from (.*)", raw_event)
        event_target = m.group(2)
    return event_target

def get_event_source(raw_event, event_type):
    if (event_is_add(event_type)):
        m = re.match(r"(.*) from +(\S.*)", raw_event)
        event_source = m.group(2)
    elif (event_is_refresh(event_type)):
        m = re.match(r"(.*) is refreshed by +(\S.+)", raw_event)
        event_source = m.group(2)
    elif (event_is_delete(event_type)):
        m = re.match(r"([^']*)'s", raw_event)
        event_source = m.group(1)
    return event_source

def get_event_debuff(raw_event, event_type):
    if (event_is_add(event_type)):
        m = re.match(r".* is afflicted by  (\S[\D\(\)]+\S) +(\(\d+\))? +from", raw_event)
        event_debuff = m.group(1)
    elif (event_is_refresh(event_type)):
        m = re.match(r"(.*)'s (.*)  is refreshed by", raw_event)
        event_debuff = m.group(2)
    elif (event_is_delete(event_type)):
        m = re.match(r"\A([^']*)'s (.*)  fades from", raw_event)
        event_debuff = m.group(2)
    return event_debuff

def is_stacking_debuff(debuff_type):
    if debuff_type in stacking_debuff_list:
        return True
    return False

def handle_debuff(event):
    global debuff_list
    # since there can be more than one target in a log, the debuff list is actually a list of lists
    if not debuff_list:
        print("Init list with new target " + event["target"])
        d = {"target" : event["target"], "debuffs" : []}
        d_copy = d.copy()
        debuff_list.append(d_copy)
    elif not (next((item for item in debuff_list if item["target"] == event["target"]), False)):
        print("Adding target " + event["target"])
        d = {"target" : event["target"], "debuffs" : []}
        d_copy = d.copy()
        debuff_list.append(d_copy)
    else:
        d = next((item for item in debuff_list if item["target"] == event["target"]))

    # non-stacking debuffs should be treated like refreshes
    if ((event_is_add(event["type"])) and not (is_stacking_debuff(event["debuff"]))):
        new_debuff = {"start_time" : event["time"], "name" : event["debuff"], "source" : event["source"]}
        new_debuff_copy = new_debuff.copy()
        d["debuffs"].append(new_debuff_copy)
    elif ((event_is_add(event["type"])) and (is_stacking_debuff(event["debuff"]))):
        # search for an existing debuff to refresh
        found = False
        for i in d["debuffs"]:
            # if it already exists, just refresh it
            if (i["name"] == event["debuff"]):
                i["start_time"] = event["time"]
                found = True
                event["type"] = "refresh"
        if not (found):
            new_debuff = {"start_time" : event["time"], "name" : event["debuff"], "source" : event["source"]}
            new_debuff_copy = new_debuff.copy()
            d["debuffs"].append(new_debuff_copy)
    elif ((event_is_refresh(event["type"]))):
        # find the matching debuff in the list and update the start_time
        found = False
        for i in d["debuffs"]:
            if (i["name"] == event["debuff"]):
                i["start_time"] = event["time"]
                found = True
        if not (found):
            new_debuff = {"start_time" : event["time"], "name" : event["debuff"], "source" : event["source"]}
            new_debuff_copy = new_debuff.copy()
            d["debuffs"].append(new_debuff_copy)
            event["type"] = "add"
    elif (event_is_delete(event["type"])):
        # find the matching debuff in the list and update the start_time
        found = False
        for i in d["debuffs"]:
            if (is_stacking_debuff(event["debuff"])):
                if (i["name"] == event["debuff"]):
                    d["debuffs"].remove(i)
                    found = True
                    break
            else:
                if ((i["name"] == event["debuff"]) and (i["source"] == event["source"])):
                    d["debuffs"].remove(i)
                    found = True
                    break
        if not (found) and not (is_stacking_debuff(event["debuff"])):
            print ("Error: Delete with no existing debuff:")
  
    if (event["type"] == "refresh"):
        print("EVENT: {:6.3f}: ".format(event["time"]) + event["type"] + " " + event["debuff"] + " on " + event["target"] + " from " + event["source"])
    else:
        print("EVENT: {:6.3f}: ".format(event["time"]) + event["type"] + " " + event["debuff"] + " on " + event["target"] + " from " + event["source"] + " (" + str(len(d["debuffs"])) + " debuffs)")

def parse_file(file):
    # parse to a list of lists
    print("Parsing file")

    reader = csv.reader(file)
    list_of_rows = list(reader)
    return (list_of_rows)

def find_precast_debuffs(debuff_data):
    # right now this is only Hunter's Mark, but it's possible that a debuff already exists before the log starts (ie. pre-combat)
    # only do this if there's no add
    for i in debuff_data:
        if (i["debuff"] in precast_debuff_list):
            # if the first event is a remove, then we need to push an add to the start
            if (i["type"] == "delete"):
                print("Adjusting precast list")
                event_time = 0
                event_type = "add"
                event_target = i["target"]
                event_source = i["source"]
                event_debuff = i["debuff"]
                if (debug):
                    print(str(event_time) + ": " + event_type + " " + event_debuff + " on " + event_target + " from " + event_source)
                    pass
                d = {"time" : event_time, "type" : event_type, "debuff" : event_debuff, "target" : event_target, "source" : event_source}
                d_copy = d.copy()
                debuff_data.insert(0, d_copy)
                break

    return (debuff_data)

def parse_raw_data(raw_data):
    # We need to split the 2 columns (time and event) into all the components:
    # - timestamp
    # - add/delete/refresh
    # - target
    # - source
    # - debuff
    debuff_data = []
    for l in raw_data:
        if not (l[0] == "Time"):
            event_type = get_event_type(l[1])
            if not (event_is_skip(event_type)):
                event_time = convert_to_seconds(l[0])
                event_target = get_event_target(l[1], event_type)
                event_source = get_event_source(l[1], event_type)
                event_debuff = get_event_debuff(l[1], event_type)
                if (debug):
                    print(str(event_time) + ": " + event_type + " " + event_debuff + " on " + event_target + " from " + event_source)
                    pass
                d = {"time" : event_time, "type" : event_type, "debuff" : event_debuff, "target" : event_target, "source" : event_source}
                d_copy = d.copy()
                debuff_data.append(d_copy)
    
    return (debuff_data)

def get_debuff_duration(debuff_name):
    global debuff_durations_list
    i = next(item for item in debuff_durations_list if item["name"] == debuff_name)
    return (i["duration"])

def dump_at_timestamp(debuff_data, event):
    global debuff_list
    global last_timestamp

    if (last_timestamp == event["time"]):
        return

    last_timestamp = event["time"]

    d = next((item for item in debuff_list if item["target"] == event["target"]))

    print("---------------------------------------------------")
    print("Debuff pushed off at " + str(event["time"]))
    print("Events at current timestamp:")
    for i in debuff_data:
        if ((i["time"] == event["time"]) and (i["target"] == event["target"])):
            print(" " + i["type"] + " " + i["debuff"] + " on " + i["target"] + " from " + i["source"])

    print("Debuffs before timestamp: " + str(len(d["debuffs"])))

    for i in d["debuffs"]:
        remaining_time = get_debuff_duration(i["name"]) + i["start_time"] - event["time"]
        print(" " + i["name"] + " from " + i["source"] + " (added: {:.3f}".format(i["start_time"]) + ", estimated remaining: {:.3f}".format(remaining_time) + ")")
    print("---------------------------------------------------")

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
        if (i["time"] == event["time"]):
            if (event_is_delete(i["type"])):
                delete_found = True
            elif (event_is_add(i["type"])):
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

    with open(args.file) as file:
        # parse input file and return a list of lists
        raw_data = parse_file(file)

        debuff_data = parse_raw_data(raw_data)

        debuff_data = find_precast_debuffs(debuff_data)

        # walk debuffs
        walk_debuffs(debuff_data)

        # dump remaining debuffs (this should be empty)
        dump_debuffs()


if __name__ == "__main__":
    # execute only if run as a script
    main()
