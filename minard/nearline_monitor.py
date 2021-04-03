from .db import engine, engine_nl
from .detector_state import get_latest_run
from .pingcratesdb import ping_crates_list
from .channelflagsdb import get_channel_flags, get_channel_flags_by_run
from .triggerclockjumpsdb import get_clock_jumps, get_clock_jumps_by_run
from .nlrat import RUN_TYPES
from .occupancy import run_list, occupancy_by_trigger, occupancy_by_trigger_limit
from .muonsdb import get_muons
from .gain_monitor import crate_gain_monitor

# Limits for failing channel flags check
OUT_OF_SYNC_1 = 32
OUT_OF_SYNC_2 = 64
MISSED_COUNT_1 = 64
MISSED_COUNT_2 = 256
MISSED_BURST = 3

# Limits for failing clock jump check
CLOCK_JUMP_1 = 100
CLOCK_JUMP_2 = 200

# Limits for muons failing check
MUONS = 20
MISSED_MUONS = 1000

# Limits for crate gain failing
QHS_MAX = 30
QHS_MIN = 15

def get_run_list(limit, selected_run, run_range_low, run_range_high, all_runs, gold):
    '''
    Returns dictionaries keeping track of a list
    of failures for each nearline job
    '''
    occupancy_status = occupancy(limit, selected_run, run_range_low, run_range_high, all_runs, gold)
    muon_status = muons(limit, selected_run, run_range_low, run_range_high, all_runs, gold)
    gain_status = gain_monitor(limit, selected_run, run_range_low, run_range_high, all_runs, gold)
    if not selected_run:
        ping_crates_status = ping_crates(limit, run_range_low, run_range_high, all_runs, gold)
        channel_flags_status = channel_flags(limit, run_range_low, run_range_high, all_runs, True, gold) 
        clock_jumps_status = clock_jumps(limit, run_range_low, run_range_high, all_runs, gold)
    else:
        ping_crates_status = ping_crates_run(selected_run)
        channel_flags_status = channel_flags_run(selected_run)
        clock_jumps_status = clock_jumps_run(selected_run)

    return clock_jumps_status, ping_crates_status, channel_flags_status, occupancy_status, muon_status, gain_status

def gain_monitor(limit, selected_run, run_range_low, run_range_high, all_runs, gold):
    """
    Check that the QHS peaks for each crate is within an acceptable range
    """
    gain_fail = {}
    runs, qhs_array, crate_array = crate_gain_monitor(limit, selected_run, run_range_low, run_range_high, gold)
    for run in all_runs:
        try:
            gain_fail[run] = 0
            for crate in crate_array[run]:
                if qhs_array[(run, crate)][0] > QHS_MAX or \
                   qhs_array[(run, crate)][0] < QHS_MIN:
                    gain_fail[run] = 1
        except KeyError:
            gain_fail[run] = -1

    return gain_fail

def muons(limit, selected_run, run_range_low, run_range_high, all_runs, gold):
    """
    Checks the numbers of muons and missed muons and fails run if they exceed
    a hard-coded limit. Also checks the times of the muons, atmospherics, and
    missed muons are within an acceptable range of time.
    """
    muon_fail = {}
    _, mcount, mmcount, _, _, _, time_check = get_muons(limit, selected_run, run_range_low, run_range_high, gold, 0)

    for run in all_runs:
        try:
            if not time_check[run]:
                muon_fail[run] = 1
            elif mcount[run] > MUONS:
                muon_fail[run] = 1
            elif mmcount[run] > MISSED_MUONS:
                muon_fail[run] = 1
            else:
                muon_fail[run] = 0
        except KeyError:
            muon_fail[run] = -1

    return muon_fail


def occupancy(limit, selected_run, run_range_low, run_range_high, all_runs, gold):
    '''
    Return a dictionary of ESUM occupancy status by run
    '''
    occupancy_fail = {}
    status,_,_ = occupancy_by_trigger_limit(limit, selected_run, run_range_low, run_range_high, gold)
    for run in all_runs:
        try:
            # Check ESUMH Occupancy
            if status[run] == 1:
                occupancy_fail[run] = 1
            elif status[run] == 0:
                occupancy_fail[run] = 0
        except KeyError:
            occupancy_fail[run] = -1
            continue

    return occupancy_fail


def clock_jumps_run(run):
    '''
    Return the clock jumps status for a selected run
    '''
    clock_jumps_status = {}
    conn = engine_nl.connect()

    result = conn.execute("SELECT run FROM trigger_clock_jumps WHERE run = %s", run)

    # This should be the best way to check if the job ran for the given run
    try:
        result.fetchone()[0]
    except Exception:
        clock_jumps_status[run] = -1
        return clock_jumps_status

    data10, data50 = get_clock_jumps_by_run(run)
    njump10 = len(data10)
    njump50 = len(data50)
    if((njump10 + njump50) > CLOCK_JUMP_1 and \
       (njump10 + njump50) < CLOCK_JUMP_2):
        clock_jumps_status[run] = 2
    elif(njump10 + njump50 >= CLOCK_JUMP_2):
        clock_jumps_status[run] = 1
    else:
        clock_jumps_status[run] = 0

    return clock_jumps_status


def clock_jumps(limit, run_range_low, run_range_high, all_runs, gold):
    '''
    Return a dictionary of clock jumps status by run
    '''
    clock_jumps_fail = {}

    _, njump10, njump50, _ = get_clock_jumps(limit, 0, run_range_low, run_range_high, gold)
    for run in all_runs:
        try:
            if((njump10[run] + njump50[run]) >= CLOCK_JUMP_1 and \
               (njump10[run] + njump50[run]) < CLOCK_JUMP_2):
                clock_jumps_fail[run] = 2
            elif(njump10[run] + njump50[run] >= CLOCK_JUMP_2):
                clock_jumps_fail[run] = 1
            else:
                clock_jumps_fail[run] = 0
        except KeyError:
            clock_jumps_fail[run] = -1
            continue

    return clock_jumps_fail


def channel_flags_run(run):
    '''
    Return the channel flags status for a selected run
    '''
    channel_flags_status = {}
    conn = engine_nl.connect()

    result = conn.execute("SELECT sync16 FROM channel_flags WHERE run = %s", run)

    # This should be the best way to check if the job ran for the given run
    try:
        result.fetchone()[0]
    except Exception:
        channel_flags_status[run] = -1
        return channel_flags_status

    missed, sync16, sync24, _, _, burst, _, _, _ = get_channel_flags_by_run(run)
    missed = len(missed)
    sync16 = len(sync16)
    sync24 = len(sync24)
    missed_burst = len(burst)
    if(sync16 >= OUT_OF_SYNC_2 or missed >= MISSED_COUNT_2 or \
       missed_burst > MISSED_BURST):
        channel_flags_status[run] = 1
    elif((sync16 >= OUT_OF_SYNC_1 and sync16 < OUT_OF_SYNC_2) or \
         (missed >= MISSED_COUNT_1 and missed < MISSED_COUNT_2) or \
         (missed_burst > 0 and missed_burst <= MISSED_BURST)):
        channel_flags_status[run] = 2
    else:
        channel_flags_status[run] = 0

    return channel_flags_status 


def channel_flags(limit, run_range_low, run_range_high, all_runs, summary, gold):
    '''
    Return a dictionary of channel flags status by run
    '''
    _, _, _, _, count_sync16, _, count_missed, burst, count_sync16_pr, _, _, _, _ = \
        get_channel_flags(limit, run_range_low, run_range_high, summary, gold)
    channel_flags_fail = {}
    for run in all_runs:
        run = int(run)
        try:
            if(count_sync16[run] >= OUT_OF_SYNC_2 or count_missed[run] >= MISSED_COUNT_2 or \
               count_sync16_pr[run] >= OUT_OF_SYNC_2 or burst[run] > MISSED_BURST):
                channel_flags_fail[run] = 1
            elif((count_sync16[run] >= OUT_OF_SYNC_1 and count_sync16[run] < OUT_OF_SYNC_2) or \
                 (count_missed[run] >= MISSED_COUNT_1 and count_missed[run] < MISSED_COUNT_2) or \
                 (burst[run] > 0 and burst[run] <= MISSED_BURST)):
                channel_flags_fail[run] = 2
            else:
                channel_flags_fail[run] = 0
        except KeyError:
            channel_flags_fail[run] = -1
            continue

    return channel_flags_fail


def ping_crates_run(run):
    '''
    Return ping crates status for selected run
    '''
    conn = engine_nl.connect()

    ping_crates_status = {}
    result = conn.execute("SELECT status FROM ping_crates WHERE run = %i" % run)
    try:
        row = result.fetchone()[0]
        # Status is pass or override
        if row == 0 or row == 3: 
            ping_crates_status[run] = 0
        elif row == 1:
            ping_crates_status[run] = 1
        elif row == 2:
            ping_crates_status[run] = 2
    except Exception:
        ping_crates_status[run] = -1

    return ping_crates_status


def ping_crates(limit, run_range_low, run_range_high, all_runs, gold):
    '''
    Return a dictionary of ping crates status by run
    '''
    ping_list = ping_crates_list(limit, 0, run_range_low, run_range_high, gold)
    ping_crates_fail = {}
    ping_runs = []
    for i in ping_list:
        run = int(i[1])
        ping_runs.append(run)
        if i[6] == 1:
            ping_crates_fail[run] = 1
        elif i[6] == 0 or i[6] == 3:
            ping_crates_fail[run] = 0
        elif i[6] == 2:
            ping_crates_fail[run] = 2
    for run in all_runs:
        if run in ping_runs:
            continue
        ping_crates_fail[run] = -1

    return ping_crates_fail


def get_run_types(limit, selected_run, run_range_low, run_range_high, gold):
    '''
    Return a dictionary of run types for each run in the list
    '''
    conn = engine.connect()

    if not selected_run and not run_range_high:
        # Nearline jobs run after run has finished
        latest_run = get_latest_run()
        # Don't look at the current run
        result = conn.execute("SELECT DISTINCT ON (run) "
                              "run, run_type FROM run_state WHERE "
                              "run < %s and run > %s ORDER BY run DESC", \
                              (latest_run, latest_run - limit))
    elif run_range_high:
        result = conn.execute("SELECT DISTINCT ON (run) "
                              "run, run_type FROM run_state WHERE "
                              "run >= %s AND run <= %s ORDER BY run DESC", \
                              (run_range_low, run_range_high))
    else:
        result = conn.execute("SELECT DISTINCT ON (run) "
                              "run, run_type FROM run_state WHERE "
                              "run = %s" % selected_run)

    rows = result.fetchall()

    runs = []
    runtypes = {}
    for run, run_type in rows:
        if gold != 0 and run not in gold:
            continue
        runs.append(run)
        for i in range(len(RUN_TYPES)):
            if (run_type & (1<<i)):
                runtypes[run] = RUN_TYPES[i]
                break

    return runtypes, runs
