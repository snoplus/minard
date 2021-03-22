from .db import engine_nl

def get_scintillator_level(run_begin, run_end):
    '''
    Get the scintillator level from the scint_level table.
    '''
    conn = engine_nl.connect()

    # Get one result per run, with most recent timestamp
    result = conn.execute("SELECT DISTINCT ON(run) run::INTEGER, scint_lvl FROM scint_level WHERE " 
                          "run >= %s AND run <= %s ORDER BY run, timestamp DESC", (run_begin, run_end))

    keys = map(str, result.keys())
    rows = result.fetchall()

    return [dict(zip(keys,row)) for row in rows]


def get_av_z_offset(run_begin, run_end):
    '''
    Retrieve the daily AV z-offset from the av-offset table.
    '''
    conn = engine_nl.connect()

    # Get one result per run, with most recent timestamp
    result = conn.execute("SELECT DISTINCT ON(run) run::INTEGER, av_offset_z FROM av_offset WHERE " 
                          "run >= %s AND run <= %s ORDER BY run, timestamp DESC", (run_begin, run_end))

    keys = map(str, result.keys())
    rows = result.fetchall()

    return [dict(zip(keys,row)) for row in rows]


def get_av_rope_data(run_begin, run_end):
    '''
    Retrieve the rope length data from the av-offset table.
    The rope length data are daily averages.

    Note: Rope B reading is not used.
    '''
    conn = engine_nl.connect()

    result = conn.execute("SELECT run::INTEGER, avg_rope_a_reading, avg_rope_b_reading, "
                          "avg_rope_c_reading, avg_rope_d_reading, avg_rope_e_reading, "
                          "avg_rope_f_reading, avg_rope_g_reading FROM av_offset WHERE " 
                          "run >= %s AND run <= %s ORDER BY run", (run_begin, run_end))

    keys = map(str, result.keys())
    rows = result.fetchall()

    return [dict(zip(keys,row)) for row in rows]


