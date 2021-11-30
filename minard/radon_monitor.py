from .db import engine
import datetime

def get_radon_monitor(yr_low, mn_low, d_low, yr_high, mn_high, d_high):

    conn = engine.connect()

    result = conn.execute("SELECT po210_counts, po212_counts, po214_counts, po218_counts, livetime, start_time "
                          "FROM radon_monitor ORDER BY "
                          "start_time ASC")

    keys = map(str, result.keys())
    rows = result.fetchall()

    data = []

    datetime_low = datetime.datetime(yr_low, mn_low, d_low)
    datetime_high = datetime.datetime(yr_high, mn_high, d_high)

    for po210, po212, po214, po218, livetime, start_time in rows:
        x = {}
        x['po210_rate'] = int(po210)/float(livetime)     
        x['po212_rate'] = int(po212)/float(livetime)     
        x['po214_rate'] = int(po214)/float(livetime)     
        x['po218_rate'] = int(po218)/float(livetime)     
        date = datetime.datetime.fromtimestamp(start_time)
        if date > datetime_high or date < datetime_low:
            continue
        d =  date.strftime("%Y-%m-%dT%H:%M:%S.%f")
        x['timestamp'] = d
        data.append(x)

    return data


