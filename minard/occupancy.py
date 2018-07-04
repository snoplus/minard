from .db import engine_nl
from .detector_state import get_latest_run

def occupancy_by_trigger_limit(limit, selected_run, run_range_low, run_range_high, gold):
    """
    Returns a dictionary of the ESUMH occupacy status indexed by run
    """
    conn = engine_nl.connect()


    try:
        if not selected_run and not run_range_high:
            latest_run = get_latest_run()
            result = conn.execute("SELECT DISTINCT ON (run, crate, slot) "
                                  "run, status, crate, slot "
                                  "FROM esumh_occupancy_fail WHERE run > %s "
                                  "ORDER BY run, crate, slot", \
                                  (latest_run - limit))
        elif run_range_high:
            result = conn.execute("SELECT DISTINCT ON (run, crate, slot) "
                                  "run, status, crate, slot "
                                  "FROM esumh_occupancy_fail WHERE run >= %s "
                                  "AND run <= %s ORDER BY run, crate, slot", \
                                  (run_range_low, run_range_high))
        else:
            result = conn.execute("SELECT DISTINCT ON (run, crate, slot) "
                                  "run, status, crate, slot "
                                  "FROM esumh_occupancy_fail WHERE run = %s "
                                  "AND timestamp = (SELECT timestamp FROM "
                                  "esumh_occupancy_fail WHERE run = %s ORDER BY "
                                  "timestamp DESC LIMIT 1) "
                                  "ORDER BY run, crate, slot", \
                                  (selected_run, selected_run))
    except Exception as e:
        return {}, {}, {}

    rows = result.fetchall()

    crates = {}
    slots = {}
    status = {}
    runs = []
    # Check the ESUMH occupancy by run and format the message
    # for the monitoring page
    for run, run_status, crate, slot in rows:
        if gold != 0 and run not in gold:
            continue
        status[run] = run_status
        if run not in runs:
            runs.append(run)
        if run_status == 0:
            crates[run] = "None"
            slots[(run, -1)] = "None"
            continue
        try:
            if crate != crates[run][-1]:
                crates[run].append(crate)
        except Exception as e:
            crates[run] = [crate]
        try:
            slots[(run,crate)].append(slot)
        except Exception as e:
            slots[(run,crate)] = [slot]

    # Some formatting
    for run in runs:
        if crates[run] == "None":
            continue
        crates[run] = str(crates[run])[1:-1]

    return status, crates, slots

def occupancy_timestamp(run):
    """
    Grab the timestamp before the queried run to speed up
    the occupancy query
    """
    conn = engine_nl.connect()

    result = conn.execute("SELECT timestamp FROM esumh_occupancy_fail "
                          "WHERE run < %s ORDER BY timestamp DESC LIMIT 1", run)

    row = result.fetchone()
    if row is None:
        return None

    t = row[0]
    time = t.strftime('%Y-%m-%d %H:%M:%S.%f')

    return time

def occupancy_by_trigger(trigger_type, run, find_issues):
    """
    Returns a list specifing the normalized occupancy
    for the trigger type.
    """
    conn = engine_nl.connect()

    # Used to speed up select statement
    time = occupancy_timestamp(run)

    result = conn.execute("SELECT DISTINCT ON (run, lcn, trigger_bit) "
                          "lcn, trigger_norm, occupancy "
                          "FROM trigger_occupancy WHERE timestamp >= %s "
                          "AND trigger_bit = %s AND run = %s "
                          "ORDER BY run, lcn, trigger_bit ", \
                          (time, trigger_type, run))

    rows = result.fetchall()

    if not rows:
        return None

    data = [0]*9728
    trigger_norm = 0
    for lcn, norm, occupancy in rows:
        trigger_norm = norm
        data[lcn] = occupancy

    if trigger_norm == 0:
        data = [0]*9728
        return data

    data = [float(x) / trigger_norm for x in data]

    return data

def run_list(limit, run_range_low, run_range_high, gold):
    """
    Get a list of runs where the trigger
    occupancy job ran.
    """
    conn = engine_nl.connect()

    if not run_range_high:
        latest_run = get_latest_run()
        result = conn.execute("SELECT DISTINCT ON (run) run FROM esumh_occupancy_fail "
                              "WHERE run > %s ORDER BY run DESC", (latest_run - limit))
    else:
        result = conn.execute("SELECT DISTINCT ON (run) run FROM esumh_occupancy_fail "
                              "WHERE run >= %s and run <= %s ORDER BY run DESC", \
                              (run_range_low, run_range_high))

    rows = result.fetchall()
    runs = []
    for run in rows:
        if gold != 0 and run[0] not in gold:
            continue
        runs.append(run[0])

    return runs

