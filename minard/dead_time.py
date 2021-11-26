from .db import engine

def get_dead_time(key):
    '''
    Get the dead-time scan information
    '''
    conn = engine.connect()

    result = conn.execute("SELECT total_delay, trigger_rate FROM dead_time_test_scan WHERE key = %s", (key,))

    keys = map(str, result.keys())
    rows = result.fetchall()
    data = [dict(zip(keys,row)) for row in rows]

    return data


def get_dead_time_runs():
    '''
    Get the information for all of the dead-time runs
    '''
    conn = engine.connect()

    result = conn.execute("SELECT key, dgt_delay, lo_source, lo_length, pulser_rate, trig FROM dead_time_test")

    rows = result.fetchall()

    return rows


def get_dead_time_run_by_key(key):
    '''
    Get the dead-time information for a specific run
    '''
    conn = engine.connect()

    result = conn.execute("SELECT dgt_delay, lo_source, lo_length, pulser_rate, trig FROM dead_time_test WHERE key = %s", (key,))

    rows = result.fetchall()

    return rows

