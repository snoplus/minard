import couchdb
from . import app

BATCH_SIZE = 1

def connect(user=None, pw=None, server="localhost", port=5984):
    if user is None and pw is None:
        import couchcreds
        user = couchcreds.user
        pw = couchcreds.pw
    return couchdb.Server(f"http://{user}:{pw}@{server}:{port}")

def get_data_from_view(db, view, startkey=0, endkey=999999999999, limit=500):
    viewData = db.view(view, limit=limit, startkey=startkey, endkey=endkey)
    return [(r["key"], r["value"]) for r in viewData] #time value pairs

def get_rack_supply_voltage_view_name(rack, voltage):
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
    
    return f"slowcontrol-data-5sec/{ios}_{card}_{channel}"

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

    return f"slowcontrol-data-5sec/{ios}_{card}_{channel}"

if __name__ == "__main__":
    couch = connect(user=app.config[COUCHDB_USER], pw=app.config[COUCHDB_PASS])
    db = couch['slowcontrol-data-5sec']
    viewname = get_rack_supply_voltage_view_name(rack=1, voltage=24)
    data = get_data_from_view(db, viewname, limit=99999999999999)

    print(len(data))