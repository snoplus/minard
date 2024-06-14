import couchdb
import datetime
import requests
import json

BATCH_SIZE = 1
MAX_LIMIT = 268435456 #couchdb rules

def getTimestamp(targetTime):
    return targetTime.strftime("%s") #python2 doesn't support unix ts, but somehow this method does... on unix only

def connect(user=None, pw=None, server="localhost", port=5984):
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

def get_data_from_view_http(viewName, server="http://192.168.80.89:5984", startkey=0, endkey=999999999999, limit=MAX_LIMIT, sanitize=False):
    opts = "limit=" + str(limit) + "&startkey=" + str(startkey) + "&endkey=" + str(endkey)    
    tic = datetime.datetime.now()
    r = requests.get(server+'/slowcontrol-data-5sec/_design/slowcontrol-data-5sec/_view/'+viewName+'?'+opts, auth=("admin", "pass"))
    if r.status_code == 200:
        print(str(len(r.json()['rows'])) + " rows returned in " + str(datetime.datetime.now()-tic))
        if sanitize: return json.dumps(r.json()['rows']) # really dumb... but sanitizes unicode (u'(whatever...)')
        else: return r.json()['rows']
    else:
        raise Exception

def get_rack_supply_voltage_view_name(rack, voltage, httpStr=False):
    '''Gets the view name for a specified rack and voltage channel.
        Valid racks: Integers from 1 to 11 or "timing".
        Valid voltage channels: 24, -24, 8, 5, -5.'''
    RACKS = list(range(1, 11+1)) + ["timing"]
    VOLTAGES = [24, -24, 8, 5, -5]
    CARDS = ['A', 'B', 'C', 'D']
    ios = 1

    if rack not in RACKS: return None
    if voltage not in VOLTAGES: return None

    if rack == "timing":
        card = 'D'
        channel = VOLTAGES.index(voltage) 
    else:
        raw_channel = 5 * RACKS.index(rack) + VOLTAGES.index(voltage)
        card = CARDS[raw_channel // 20]
        channel = raw_channel % 20
    
    viewStr = str(ios) + "_" + str(card) + "_" + str(channel)
    return viewStr

def get_crate_baseline_voltage_view_name(crate, trigger):
    '''Gets the view name for a specified crate and trigger baseline voltage.
        Valid crates: Integers from 0 to 18.
        Valid triggers: Integers 100, 20. (N100_BL, N20_BL)'''
    CRATES = range(0, 18+1)
    TRIGGERS = [100, 20]
    CARDS = ['A', 'B', 'C', 'D']
    ios = 3

    if crate not in CRATES: return None
    if trigger not in TRIGGERS: return None

    card = CARDS[crate // 6]
    channel = (crate % 6) * 3 + TRIGGERS.index(trigger)
    if channel >= 12: channel += 1

    viewStr = str(ios) + "_" + str(card) + "_" + str(channel)
    return viewStr

def get_supply_data_http(datelow, datehigh, rack, voltage):
    db = connect(user="admin", pw="pass", server="192.168.80.89")['slowcontrol-data-5sec']
    startkey = getTimestamp(datelow)
    endkey = getTimestamp(datehigh)
    
    try: #verify rack is int OR the string "timing"
        rack = int(rack)
        friendlyViewName = "Rack " + str(rack) + " - " + voltage + "V supply"
    except ValueError:
        if rack == "timing":
            return None
        else:
            friendlyViewName = "Timing Rack - " + voltage + "V supply"

    try: 
        voltage = int(voltage)
    except ValueError:
        return None
    
    viewName = get_rack_supply_voltage_view_name(rack=rack, voltage=voltage)
    data = get_data_from_view_http(viewName, startkey=startkey, endkey=endkey)

    x = len(data)
    if x > 5000:
        crushFactor = int(x/5000) #cap rows at 5000
        data = data[crushFactor::crushFactor]
    
    return json.dumps(data), friendlyViewName

def get_baseline_data_http(datelow, datehigh, crate, trigger):
    db = connect(user="admin", pw="pass", server="192.168.80.89")['slowcontrol-data-5sec']
    startkey = getTimestamp(datelow)
    endkey = getTimestamp(datehigh)
    
    # try: #verify crate is int
    crate = int(crate)
    friendlyViewName = "Crate " + str(crate) + " - N" + trigger + "BL"
    # except ValueError:
    #     if crate == "timing":
    #         return None
    #     else:
    #         friendlyViewName = "Timing Rack - " + voltage + "V supply"
    
    viewName = get_crate_baseline_voltage_view_name(crate=crate, trigger=trigger)
    data = get_data_from_view_http(viewName, startkey=startkey, endkey=endkey)
    
    if len(data) > 10000:
        crushFactor = max(1, int(0.02*(len(data))**(1/2))) #0.02 * sqrt(len)
        del data[crushFactor-1::crushFactor]
    
    return data, friendlyViewName


def get_plot_data(startDate, endDate, dataName=str(datetime.datetime.now().microsecond), collate=False, limit=1000):
    '''Test function for now'''
    db = connect(user="admin", pw="pass", server="192.168.80.89")['slowcontrol-data-5sec']
    tic = datetime.datetime.now()
    data = get_data_from_view(db, 'slowcontrol-data-5sec/'+get_rack_supply_voltage_view_name(rack=1, voltage=24), limit=limit, startkey=1380882382, collate=collate)
    print("Data returned in " + str(datetime.datetime.now()-tic) + " and collate was " + str(collate))
    return data, dataName, startDate, endDate

def get_plot_data_http(startDate, endDate, dataName=str(datetime.datetime.now().microsecond), limit=1000):
    '''Test function for now'''
    db = connect(user="admin", pw="pass", server="192.168.80.89")['slowcontrol-data-5sec']
    tic = datetime.datetime.now()
    viewName = get_rack_supply_voltage_view_name(rack=1, voltage=24)
    data = get_data_from_view_http(viewName, limit=limit, startkey=1380882382)
    print("Data returned in " + str(datetime.datetime.now()-tic))
    return data, dataName, startDate, endDate

if __name__ == "__main__":
    couch = connect(user="admin", pw="pass", server="192.168.80.89")
    db = couch['slowcontrol-data-5sec']
    viewname = get_rack_supply_voltage_view_name(rack=1, voltage=24)
    pass