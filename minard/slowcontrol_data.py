import datetime
import grequests
import json
from . import app

MAX_ROWS_RETURNED = 2000

class CouchException(Exception):
    def __init__(self, message):
        self.message = message

def getTimestamp(targetTime):
    return targetTime.strftime("%s") #python2 doesn't support unix ts, but somehow this method does... on unix only

def get_data_from_view_http_threaded(viewName, startkey, endkey, threadCount=20, server="http://couch.snopl.us", stable='true', update='lazy'):
    startkey = int(startkey)
    endkey = int(endkey)

    interval = (endkey-startkey)//threadCount #the range of keys in each request
    intervalList = range(startkey, endkey, interval) #the breakpoints

    #the template of parameters we will pass to the request
    #we will insert the startkey and endkey in the next step
    baseThreadParams = {
        "stable": stable,
        "update": update,
        "inclusive_end": "true",
        "sorted": "false", #faster to sort on our end with concurrent requests
    }

    threadParamsList = []

    #first, create many parameter dicts, with evenly-spaced start and stop keys
    for step in intervalList:
        newThreadParams = baseThreadParams.copy() #shallow copy, ie. copy by value
        newThreadParams["startkey"] = str(step)
        newThreadParams["endkey"] = str(step + interval)
        threadParamsList.append(newThreadParams)
    
    startTime = datetime.datetime.now()

    #next, use grequests to submit all requests concurrently
    callList = (grequests.get(server+"/slowcontrol-data-5sec/_design/echolocator/_view/"+viewName, 
        auth=(app.config['COUCH_USER'], app.config['COUCH_PASS']), params=params) for params in threadParamsList) #define the requests
    responses = grequests.map(callList) #submit all requests
    responseTime = datetime.datetime.now()
    print("{0} threads returned in {1}s".format(len(responses), responseTime-startTime))

    #extract the list of "rows" from each response (the actual data)
    data = map(lambda response: response.json()['rows'], responses)
    unpackingTime = datetime.datetime.now()
    print("Unpacked threads in {0}s".format(unpackingTime-responseTime))
    
    #this is a bit tricky - the map() applies the *sort lambda* to each list in data
    #the sort lambda sorts each list of dicts by key INDIVIDUALLY of the others
    #since grequests keeps the requests in order, the data is now completely sorted
    data = map(lambda response: sorted(response, key=lambda point: point['key']), data)
    sortingTime = datetime.datetime.now()
    print("Sorted threads in {0}s".format(sortingTime-unpackingTime))

    #finally, merge each list with a reduce()
    data = reduce(lambda a, b: a+b, data)
    mergingTime = datetime.datetime.now()
    print("Merged threads in {0}s".format(mergingTime-unpackingTime))

    print("{0} rows returned in {1}s total ({2}x threaded)".format(len(data), mergingTime-startTime, threadCount))
    return data
    
def get_rack_supply_voltage_view_name(rack, voltage, httpStr=False):
    '''Gets the view name for a specified rack and voltage channel.
        :param int|str rack: Integer from 1 to 11 or "timing".
        :param int voltage: Valid voltage channels: 24, -24, 8, 5, -5.'''
    RACKS = list(range(1, 11+1)) + ["timing"]
    VOLTAGES = [24, -24, 8, 5, -5]
    VOLTAGES_TIMING = [24, -24, 5, -5, 6, 'mtcd']
    CARDS = ['A', 'B', 'C', 'D']
    ios = 2

    if rack not in RACKS:
        raise CouchException("Rack " + str(rack) + " is invalid.")
    if voltage not in VOLTAGES + VOLTAGES_TIMING: 
        raise CouchException("Voltage " + str(voltage) + " is invalid.")

    if rack == "timing":
        card = 'D'
        channel = VOLTAGES_TIMING.index(voltage)
        if voltage == 'mtcd':
            channel = 7
    else:
        raw_channel = 5 * RACKS.index(rack) + VOLTAGES.index(voltage)
        card = CARDS[raw_channel // 20]
        channel = raw_channel % 20
    
    viewStr = str(ios) + "_" + str(card) + "_" + str(channel)
    return viewStr

def get_crate_baseline_voltage_view_name(crate, trigger):
    '''Gets the view name for a specified crate and trigger baseline voltage.
        :param int crate: Integer from 0 to 18.
        :param int trigger: Integers 100, 20. (N100_BL, N20_BL)'''
    CRATES = range(0, 18+1)
    TRIGGERS = [100, 20]
    CARDS = ['A', 'B', 'C', 'D']
    ios = 4

    if crate not in CRATES: raise CouchException("Crate " + str(crate) + " is invalid.")
    if trigger not in TRIGGERS: raise CouchException("Trigger " + str(trigger) + " is invalid.")

    card = CARDS[crate // 6]
    channel = (crate % 6) * 3 + TRIGGERS.index(trigger)
    if channel >= 12: channel += 1

    viewStr = str(ios) + "_" + str(card) + "_" + str(channel)
    return viewStr

def get_supply_data_http(datelow, datehigh, rack, voltage):
    #TODO: more docstrings
    startkey = getTimestamp(datelow)
    endkey = getTimestamp(datehigh)
    
    try: #verify rack is int OR the string "timing"
        rack = int(rack)
        friendlyViewName = "Rack " + str(rack) + ": " + voltage + "V supply"
    except ValueError:
        if rack == "timing":
            if voltage == "mtcd":
                friendlyViewName = "MTCD -2V Supply"
            else: 
                friendlyViewName = "Timing Rack: " + voltage + "V supply"
        else:
            raise Exception("Rack was invalid.")

    try: 
        voltage = int(voltage)
        baseRange = voltage
    except ValueError:
        if voltage != "mtcd":
            return None, None
        baseRange = -2
    
    viewName = get_rack_supply_voltage_view_name(rack=rack, voltage=voltage)
    data = get_data_from_view_http_threaded(viewName, startkey=startkey, endkey=endkey)

    x = len(data)
    if x > MAX_ROWS_RETURNED:
        crushFactor = int(x/MAX_ROWS_RETURNED) #cap rows
        data = data[crushFactor::crushFactor]
    
    return json.dumps(data), friendlyViewName, baseRange

def get_baseline_data_http(datelow, datehigh, crate, trigger):
    startkey = getTimestamp(datelow)
    endkey = getTimestamp(datehigh)
    
    try: #verify crate, trigger is int - this SUCKS prob just returns string always anyways
        crate = int(crate)
        trigger = int(trigger)
        friendlyViewName = "Crate " + str(crate) + ": N" + str(trigger) + "_BL"
    except ValueError:
        print("Crate (" + str(crate) + ") or trigger (" + str(trigger) + ") was invalid.")
        return None, None
    
    viewName = get_crate_baseline_voltage_view_name(crate=crate, trigger=trigger)
    data = get_data_from_view_http_threaded(viewName, startkey=startkey, endkey=endkey)
    baseRange = 0 #TODO
    
    x = len(data) 
    if x > MAX_ROWS_RETURNED:
        crushFactor = int(x/MAX_ROWS_RETURNED) #cap rows
        data = data[crushFactor::crushFactor]
    
    return json.dumps(data), friendlyViewName, baseRange