from .db import engine
import datetime

def get_radon_monitor(yr_low, mn_low, d_low, yr_high, mn_high, d_high):
    '''
    Get the radon monitor data between two dates.
    '''
    conn = engine.connect()

    result = conn.execute("SELECT po210_counts, po212_counts, po214_counts, po216_counts, "
                          "po218_counts, livetime, start_time FROM radon_monitor ORDER BY "
                          "start_time ASC")

    keys = map(str, result.keys())
    rows = result.fetchall()

    # Range of selected dates
    datetime_low = datetime.datetime(yr_low, mn_low, d_low)
    datetime_high = datetime.datetime(yr_high, mn_high, d_high)
    data = []

    for po210, po212, po214, po216, po218, livetime, start_time in rows:
        # Add a 4 hour calibration
        livetime += 4*3600.0
        rm = {}
        rm['po210_rate'] = int(po210)/float(livetime)     
        rm['po212_rate'] = int(po212)/float(livetime)     
        rm['po214_rate'] = int(po214)/float(livetime)     
        rm['po216_rate'] = int(po216)/float(livetime)     
        rm['po218_rate'] = int(po218)/float(livetime)     
        date = datetime.datetime.fromtimestamp(start_time)
        if date > datetime_high or date < datetime_low:
            continue
        rm['timestamp'] = date.strftime("%Y-%m-%dT%H:%M:%S.%f")
        data.append(rm)

    return data


