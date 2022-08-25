from .db import engine_nl

def get_light_level(run_begin, run_end, fv_cut):
    '''
    Get the light levels from the 210Po peak location
    '''
    conn = engine_nl.connect()

    result = conn.execute("SELECT DISTINCT ON(run) run::INTEGER, peak "
                          "FROM po210_nhits WHERE run >= %s AND run <= %s "
                          "ANd fv_cut = %s ORDER BY run, timestamp DESC", (run_begin, run_end, fv_cut))

    keys = map(str, result.keys())
    rows = result.fetchall()

    return [dict(zip(keys,row)) for row in rows]


def get_all_light_levels(run_begin, run_end, fv_cut):
    '''
    Get the light levels from the 210Po peak location
    '''
    conn = engine_nl.connect()

    result = conn.execute("SELECT DISTINCT ON(run) run::INTEGER, peak, peak_unc, fv_cut, "
                          "entries FROM po210_nhits WHERE run >= %s AND run <= %s "
                          "AND fv_cut = %s ORDER BY run, timestamp DESC", (run_begin, run_end, fv_cut))

    keys = map(str, result.keys())
    rows = result.fetchall()

    return [dict(zip(keys,row)) for row in rows]

