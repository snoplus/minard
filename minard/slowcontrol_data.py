import couchdb
import datetime
import requests
import json
from . import app

MAX_LIMIT = 268435456 #couchdb rules
MAX_ROWS_RETURNED = 2000

class CouchException(Exception):
    def __init__(self, message):
        self.message = message

def getTimestamp(targetTime):
    return targetTime.strftime("%s") #python2 doesn't support unix ts, but somehow this method does... on unix only

def connect(user=None, pw=None, server="localhost", port=5984):
    '''Deprecated in favour of HHTP/request methods.'''
    if user is None and pw is None:
        import couchcreds
        user = couchcreds.user
        pw = couchcreds.pw
    serverStr = "http://" + str(user) + ":" + str(pw) + "@" + str(server) + ":" + str(port)
    return couchdb.Server(serverStr)

def get_data_from_view(db, viewName, startkey=0, endkey=999999999999, limit=500, request=True, collate=False):
    viewData = db.view(viewName, limit=limit, startkey=startkey, endkey=endkey)
    if collate: 
        return [[r["key"], r["value"]] for r in viewData] #time value pairs (slower!!!)
    else:
        return [[r['key'] for r in viewData], [r["value"] for r in viewData]] #array of keys, array of values

def get_data_from_view_http(viewName, server="http://couch.snopl.us", startkey=0, endkey=999999999999, limit=MAX_LIMIT, sanitize=False, stable='true', update='lazy'):
    params = {
        "startkey": startkey,
        "endkey": endkey,
        "limit": limit,
        "stable": stable, #whether to only pull from a stable "shard" (docs do not change, so keep 'true')
        "update": update #whether to update the view ('true' for before, 'lazy' for after', 'false' for not at all)
    }
    tic = datetime.datetime.now()
    r = requests.get(server+"/slowcontrol-data-5sec/_design/echolocator/_view/"+viewName, auth=(app.config['COUCH_USER'], app.config['COUCH_PASS']), params=params)
    if r.status_code == 200:
        print(str(len(r.json()['rows'])) + " rows returned in " + str(datetime.datetime.now()-tic))
        if sanitize: return json.dumps(r.json()['rows']) # really dumb... but sanitizes unicode (u'(whatever...)') i think?
        else: return r.json()['rows']
    else:
        print("Getting data failed with code " + str(r.status_code) + "! " + str(r.json()))

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
        friendlyViewName = "Rack " + str(rack) + " - " + voltage + "V supply"
    except ValueError:
        if rack == "timing":
            if voltage == "mtcd":
                friendlyViewName = "MTCD -2V Supply"
            else: 
                friendlyViewName = "Timing Rack - " + voltage + "V supply"
        else:
            raise Exception("Rack was invalid.")

    try: 
        voltage = int(voltage)
    except ValueError:
        if voltage != "mtcd":
            return None, None
    
    viewName = get_rack_supply_voltage_view_name(rack=rack, voltage=voltage)
    data = get_data_from_view_http(viewName, startkey=startkey, endkey=endkey)

    x = len(data)
    if x > MAX_ROWS_RETURNED:
        crushFactor = int(x/MAX_ROWS_RETURNED) #cap rows
        data = data[crushFactor::crushFactor]
    
    return json.dumps(data), friendlyViewName

def get_baseline_data_http(datelow, datehigh, crate, trigger):
    startkey = getTimestamp(datelow)
    endkey = getTimestamp(datehigh)
    
    try: #verify crate, trigger is int - this SUCKS prob just returns string always anyways
        crate = int(crate)
        trigger = int(trigger)
        friendlyViewName = "Crate " + str(crate) + " - N" + str(trigger) + "_BL"
    except ValueError:
        print("Crate (" + str(crate) + ") or trigger (" + str(trigger) + ") was invalid.")
        return None, None
    
    viewName = get_crate_baseline_voltage_view_name(crate=crate, trigger=trigger)
    data = get_data_from_view_http(viewName, startkey=startkey, endkey=endkey)
    
    x = len(data) 
    if x > MAX_ROWS_RETURNED:
        crushFactor = int(x/MAX_ROWS_RETURNED) #cap rows
        data = data[crushFactor::crushFactor]
    
    return json.dumps(data), friendlyViewName

def get_plot_data(startDate, endDate, dataName=str(datetime.datetime.now().microsecond), collate=False, limit=1000):
    '''Test function for now'''
    db = connect(user="admin", pw="pass", server="192.168.80.89")['slowcontrol-data-5sec']
    tic = datetime.datetime.now()
    data = get_data_from_view(db, 'slowcontrol-data-5sec/'+get_rack_supply_voltage_view_name(rack=1, voltage=24), limit=limit, startkey=1380882382, collate=collate)
    print("Data returned in " + str(datetime.datetime.now()-tic) + " and collate was " + str(collate))
    return data, dataName, startDate, endDate

def get_plot_data_http(startDate, endDate, dataName=str(datetime.datetime.now().microsecond), limit=1000):
    '''Test function for now'''
    tic = datetime.datetime.now()
    viewName = get_rack_supply_voltage_view_name(rack=1, voltage=24)
    data = get_data_from_view_http(viewName, limit=limit, startkey=1380882382)
    print("Data returned in " + str(datetime.datetime.now()-tic))
    return data, dataName, startDate, endDate

if __name__ == "__main__":
    data = get_data_from_view_http("2_A_2", limit=100)
    print(data)