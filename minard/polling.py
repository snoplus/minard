from .db import engine 
import detector_state

# PMT Type defines
PMT_TYPES = {
    'LOWG'   : 0x21,
    'NONE'   : 0x0,
    'NECK'   : 0x9,
    'FECD'   : 0x10,
    'BUTT'   : 0x81,
    'OWL'    : 0x41,
    'HQE'    : 0x101,
    'NORMAL' : 0x3,
}

voltages_str_dict = {
    'vref0_8p': ['+0.8V', 0.8], 
    'vref1m': ['-1V', -1.0], 
    'vref1p': ['+1V', 1.0], 
    'vref2m': ['-2V', -2.0],
    'vref4p': ['+4V', 4.0], 
    'vref5p': ['+5V', 5.0],
    'vcc': ['+5V (Vcc)', 5.0], 
    'vee': ['-5V', -5.0], 
    'vsup15m': ['-15V', -15.0], 
    'vsup15p': ['+15V', 15.0], 
    'vsup24m': ['-24V', -24.0], 
    'vsup24p': ['+24V', 24.0], 
    'vsup2m': ['-2V', -2.0],
    'vsup3_3m': ['-3.3V', -3.3], 
    'vsup3_3p': ['+3.3V', 3.3],
    'vsup4p': ['+4V', 4.0], 
    'vsup6_5p': ['+6.5V', 6.5], 
    'vsup8p': ['+8V', 8.0]
}

# Fractional threshold for a bad voltage
VMON_THRESH = 0.15

def polling_runs(limit=100):
    """
    Returns two lists of runs, one where CMOS rates were polled using check
    rates, the other where base currents were polled using check rates.
    """
    conn = engine.connect()

    result = conn.execute("SELECT DISTINCT ON (run) run FROM cmos "
        "ORDER BY run DESC LIMIT %s", (limit,))

    if result is not None:
        keys = result.keys()
        rows = result.fetchall()
        cmos_runs = [dict(zip(keys,row)) for row in rows]

    result = conn.execute("SELECT DISTINCT ON (run) run FROM base "
        "ORDER BY run DESC LIMIT %s", (limit,))

    if result is not None:
        keys = result.keys()
        rows = result.fetchall()
        base_runs = [dict(zip(keys,row)) for row in rows]

    return cmos_runs, base_runs


def get_most_recent_polling_info(crate, slot, channel):
    """
    Returns a dictionary of the cmos and base currents check rates polling 
    info for a single channel in the detector, for the most recent check rates.
    """
    polls = {}

    conn = engine.connect()

    # Get the latest cmos rates
    result = conn.execute("SELECT * FROM cmos WHERE crate = %s "
        "AND slot = %s AND channel = %s ORDER BY run DESC LIMIT 1",
        (crate, slot, channel))

    if result is None:
        return None, None

    keys = result.keys()
    row = result.fetchone()

    if row:
        cmos = dict(zip(keys,row))
        polls.update(cmos)

    # Get the latest base currents
    result = conn.execute("SELECT * FROM base WHERE crate = %s "
        "AND slot = %s AND channel = %s ORDER BY run DESC LIMIT 1",
        (crate, slot, channel))

    if result is None:
        return None, None

    keys = result.keys()
    row = result.fetchone()

    if row:
        base = dict(zip(keys,row))
        polls.update(base)

    return polls

def get_base_current_history(crate, slot, channel, min_run):
    """
    Returns a list of form

        [{'timestamp': datetime, 'base_current': base current},...]

    for all runs with base current data.
    """
    conn = engine.connect()

    result = conn.execute("SELECT timestamp, base_current FROM base "
                          "WHERE crate = %s AND slot = %s AND channel = %s "
                          "AND run > %s ORDER BY timestamp DESC",
                          (crate, slot, channel, min_run))

    if result is None:
        return None

    keys = map(str,result.keys())
    rows = result.fetchall()

    return [dict(zip(keys,row)) for row in rows]

def polling_history(crate, slot, channel, min_run):
    """
    Return a list of form [[run number, cmos rate]] for all runs with cmos data
    polling. Also returns a list which included statistics on the cmos data.
    """
    conn = engine.connect()

    result = conn.execute("SELECT run, cmos_rate FROM cmos WHERE crate = %s "
        "AND slot = %s AND channel = %s AND run > %s ORDER BY run DESC",
        (crate, slot, channel, min_run))

    if result is None:
        return None, None

    keys = result.keys()
    rows = result.fetchall()

    data = []
    for run, rate in rows:
        data.append([int(run),rate])

    data_stats = []
    if data:
        z = zip(*data)
        data_max = max(z[1])
        data_min = min(z[1])
        data_average = sum(z[1])/(len(z[1]))

        data_std = 0
        for i in range(len(z[1])):
            data_std += (z[1][i] - data_average)**2
        data_std = (data_std/len(z[1]))**(0.5)

        data_stats = [int(data_max), int(data_min), int(data_average), int(data_std)]

    return data, data_stats


def polling_info(data_type, run_number):
    """
    Returns the polling data for the detector
    """
    conn = engine.connect()

    # Hold the polling information
    # for the entire detector
    data = [0]*9728

    # Default load the most recent run
    if run_number == 0:
        if data_type == "cmos":
            result = conn.execute("SELECT run FROM cmos ORDER BY run DESC LIMIT 1")
        elif data_type == "base":
            result = conn.execute("SELECT run FROM base ORDER BY run DESC LIMIT 1")
        else:
            return None

        if result is None:
            return None

        cmos_run = result.fetchone()

        for run in cmos_run:
            run_number = run

    if data_type == "cmos":
        result = conn.execute("SELECT DISTINCT ON (run, crate, slot, channel) "
            "crate, slot, channel, cmos_rate FROM cmos WHERE run = %s "
            "ORDER BY run, crate, slot, channel", (run_number,))
    elif data_type == "base":
        result = conn.execute("SELECT DISTINCT ON (run, crate, slot, channel) "
            "crate, slot, channel, base_current FROM base WHERE run = %s "
            "ORDER BY run, crate, slot, channel", (run_number,))
    else:
        return None

    if result is None:
        return None

    row = result.fetchall()
    for crate, card, channel, cmos_rate in row:
        lcn = crate*512 + card*32 + channel
        data[lcn] = cmos_rate

    return data


def polling_summary(run):
    ''' 
    Get the crate average base currents and cmos rates 
    for the run nearest to the requested run. Split up
    the OWL and HQE tubes separately.
    '''
    conn = engine.connect()

    messages = []

    current_run = detector_state.get_latest_run()

    if run == 0 or run > current_run:
       run = current_run

    result = conn.execute("SELECT run FROM cmos WHERE run <= %s ORDER BY run DESC LIMIT 1", run)
    try:
        crun = result.fetchone()[0]
    except TypeError:
        messages.append("No polling data available for run %i" % run)
        return 0, 0, 0, messages

    result = conn.execute("SELECT run FROM base where run <= %s ORDER BY run DESC LIMIT 1", run)
    try:
        brun = result.fetchone()[0]
    except TypeError:
        messages.append("No polling data available for run %i" % run)
        return 0, 0, 0, messages

    # Channels with open relays during cmos polling run
    relays_cmos = relay_status(conn, crun)
    # Channels with open relays during base polling run
    relays_base = relay_status(conn, brun)
    # Gets each PMT type
    types = pmt_type(conn)
    # Pulled resistors
    channel_info = channel_information(conn)

    crate_average_cmos = [0.0]*21 # 19 crates + OWLS + HQEs
    crate_average_base = [0.0]*21
    crates_cmos = [16*32]*21
    crates_base = [16*32]*21
    crates_cmos[19] = 3*32 # Default number of OWLS + NECKS
    crates_base[19] = 3*32
    crates_cmos[20] = 4 # Default number of HQEs
    crates_base[20] = 4

    result = conn.execute("SELECT DISTINCT ON (crate, slot, channel) "
        "cmos_rate, crate, slot, channel FROM cmos WHERE run = %s "
        "ORDER BY crate, slot, channel, timestamp DESC", (crun,))
    if result is None:
        messages.append("Polling query failed for cmos rates, run %i" % crun)
        return 0, 0, 0, messages

    row = result.fetchall()

    # Loop over cmos rates and find average for each crates
    # Keep track of channels not at high voltage
    for cmos_rate, crate, slot, channel in row:
        lcn = crate*512 + slot*32 + channel
        if not check_hv_status(relays_cmos, types, channel_info, crate, slot, channel):
            if types[lcn] == PMT_TYPES['OWL'] or \
               types[lcn] == PMT_TYPES['NECK']:
                crates_cmos[19]-=1
                crates_cmos[crate]-=1
            elif types[lcn] == PMT_TYPES['HQE']:
                crates_cmos[20]-=1
                crates_cmos[crate]-=1
            else:
                crates_cmos[crate]-=1
            continue
        # Reject hits where the CMOS rates are very high and bias the average
        # Need to be a little careful with this since it potentially masks issues
        # For now I've chosen 200kHz, but might need to be tuned
        if cmos_rate < 200000:
            if types[lcn] == PMT_TYPES['OWL'] or \
               types[lcn] == PMT_TYPES['NECK']:
                crate_average_cmos[19] += float(cmos_rate)
                crates_cmos[crate]-=1
            elif types[lcn] == PMT_TYPES['HQE']:
                crate_average_cmos[20] += float(cmos_rate)
                crates_cmos[crate]-=1
            else:
                crate_average_cmos[crate] += float(cmos_rate)
        else:
            crates_cmos[crate]-=1

    result = conn.execute("SELECT DISTINCT ON (crate, slot, channel) "
        "base_current, crate, slot, channel FROM base WHERE run = %s "
        "ORDER BY crate, slot, channel, timestamp DESC", (brun,))

    if result is None:
        messages.append("Polling query failed for base currents, run %i" % brun)
        return 0, 0, 0, messages

    row = result.fetchall()

    # Loop over base currents and find average for each crates
    # Keep track of channels not at high voltage
    for base_current, crate, slot, channel in row:
        lcn = crate*512 + slot*32 + channel
        if not check_hv_status(relays_base, types, channel_info, crate, slot, channel):
            if types[lcn] == PMT_TYPES['OWL'] or \
               types[lcn] == PMT_TYPES['NECK']:
                crates_base[19]-=1
                crates_base[crate]-=1
            elif types[lcn] == PMT_TYPES['HQE']:
                crates_base[20]-=1
                crates_base[crate]-=1
            else:
                crates_base[crate]-=1
            continue
        # Ignore bad readback, this should handle FECs at -127 without
        # needing to check the channeldb. This should not mask any issues
        # since we're mostly looking for many channels at 0.
        if base_current > -10:
            if types[lcn] == PMT_TYPES['OWL'] or \
               types[lcn] == PMT_TYPES['NECK']:
                crate_average_base[19] += float(base_current)
                crates_base[crate]-=1
            elif types[lcn] == PMT_TYPES['HQE']:
                crate_average_base[20] += float(base_current)
                crates_base[crate]-=1
            else:
                crate_average_base[crate] += float(base_current)
        else:
            crates_base[crate]-=1

    crate_average = []
    for crate in range(21):
        # If the crate was off during the polling
        if crates_cmos[crate] == 0:
           crate_average.append((crate, -1.0, -1.0))
           continue
        if crates_base[crate] == 0:
           crate_average.append((crate, -1.0, -1.0))
           continue
        cmos = round(float(crate_average_cmos[crate])/crates_cmos[crate], 2)
        base = round(float(crate_average_base[crate])/crates_base[crate], 2)
        crate_average.append((crate, cmos, base))

    return crate_average, crun, brun, messages


def polling_check(high_rate, low_rate, pct_change):
    """
    Perform sanity checks on the cmos rates and return a list
    of channels with rates changing by more than 100%, a list
    of high rate channels, and a list of low rate channels. 
    """
    conn = engine.connect()

    run_number = []

    # Get the two most recent runs with valid cmos data
    result = conn.execute("SELECT DISTINCT ON (run) run FROM cmos "
        "ORDER BY run DESC LIMIT 2")

    rows = result.fetchall()
    for run in rows:
        run_number.append(run[0])

    data_run1 = [0]*9728
    data_run2 = [0]*9728

    # Get the cmos data from the two most recent runs with valid data
    result = conn.execute("SELECT crate, slot, channel, cmos_rate, run FROM cmos WHERE "
        "run = %s or run = %s", (run_number[0], run_number[1]))

    rows = result.fetchall()
    for crate, slot, channel, cmos_rate, run in rows:
        lcn = crate*512 + slot*32 + channel
        if run == run_number[0]:
            data_run1[lcn] = cmos_rate
        elif run == run_number[1]:
            data_run2[lcn] = cmos_rate

    zero_threshold = [0]*9728
    threshold = [0]*9728

    # Get the discriminator thresholds
    result = conn.execute("SELECT crate, slot, zero_disc FROM current_zdisc "
        "ORDER BY crate, slot")

    rows = result.fetchall()

    for crate, slot, zero in rows:
        for i in range(len(zero)):
            lcn = crate*512 + slot*32 + i
            zero_threshold[lcn] = zero[i]

    # Get the discriminator zeros
    result = conn.execute("SELECT crate, slot, vthr FROM current_detector_state "
        "ORDER BY crate, slot")

    rows = result.fetchall()

    for crate, slot, thresh in rows:
        for i in range(len(thresh)):
            lcn = crate*512 + slot*32 + i
            threshold[lcn] = thresh[i]

    # Get the information needed to determine whether a channel is online
    relays = relay_status(conn, run_number[0])
    types = pmt_type(conn)
    channel_info = channel_information(conn)

    cmos_changes = []
    cmos_high_rates = []
    cmos_low_rates = []

    # Loop through the channels and warn about misbehaving channels
    for crate in range(19):
        for slot in range(16):
            for channel in range(32):
                lcn = crate*512 + slot*32 + channel
                # Warn about any high rate channel
                if data_run1[lcn] > high_rate:
                    vthr = threshold[lcn] - zero_threshold[lcn]
                    cmos_high_rates.append("%i/%i/%i: %i Hz, Vthr: %i" %\
                            (crate, slot, channel, data_run1[lcn], vthr))
                elif data_run2[lcn] > high_rate:
                    vthr = threshold[lcn] - zero_threshold[lcn]
                    cmos_high_rates.append("%i/%i/%i: %i Hz, Vthr: %i" %\
                            (crate, slot, channel, data_run2[lcn], vthr))
                if not check_hv_status(relays, types, channel_info, crate, slot, channel):
                    continue
                # For normal/HQE online PMTs, warn about channels
                # that are fluctuating a lot. Put a low rate cut
                # so that we don't warn about channels we don't care about 
                if data_run1[lcn] > 50 and data_run2[lcn] > 50:
                    change1 = 100*((data_run2[lcn] - data_run1[lcn])/data_run1[lcn])
                    change2 = 100*((data_run1[lcn] - data_run2[lcn])/data_run2[lcn])
                    if change1 > pct_change or change2 > pct_change:
                        cmos_changes.append("%i/%i/%i: %i Hz to %i Hz" %\
                            (crate, slot, channel, data_run1[lcn], data_run2[lcn]))
                # If the channel is not marked as low/zero/disc warn about low rates
                if not channel_info[lcn][1]:
                    if data_run1[lcn] < low_rate:
                        cmos_low_rates.append("%i/%i/%i: %i Hz" %\
                            (crate, slot, channel, data_run1[lcn]))
                    elif data_run2[lcn] < low_rate:
                        cmos_low_rates.append("%i/%i/%i: %i Hz" %\
                            (crate, slot, channel, data_run2[lcn]))

    return cmos_changes, cmos_high_rates, cmos_low_rates, run_number


def check_hv_status(relays, types, channel_info, crate, slot, channel):
    """
    Check where the PMT has HV on it based on the HV relays during the run,
    the PMT type, and the channel information. This uses the current channel
    database, so has potentially incorrect information aboout rpulled for
    old runs.
    """
    lcn = crate*512 + slot*32 + channel

    if relays[crate][1] is None or relays[crate][0] is None:
        return 0

    # Check if the channel is at high voltage
    hv_relay_mask = relays[crate][1] << 32 | relays[crate][0]
    if not(hv_relay_mask & (1 << (slot*4 + (3-channel//8)))):
        return 0
    # Check the PMT is normal or HQE
    if types[lcn] in (PMT_TYPES['LOWG'], PMT_TYPES['NECK'], \
                      PMT_TYPES['FECD'], PMT_TYPES['BUTT'], \
                      PMT_TYPES['NONE']):
        return 0
    # Check the resistor is not pulled or channel is not marked as bad
    if channel_info[lcn][0] or channel_info[lcn][1]:
        return 0

    return 1


def pmt_type(conn):
    """
    Get the PMT types
    """
    types = [0]*9728
    sql_result = conn.execute("SELECT crate, slot, channel, type FROM pmt_info "
        "ORDER BY crate, slot, channel")

    sql_result = sql_result.fetchall()
    for crate, slot, channel, pmttype in sql_result:
        lcn = crate*512 + slot*32 + channel
        types[lcn] = pmttype

    return types


def channel_information(conn):
    """
    Get the channel status (whether its rpulled or occupancy issues)
    """

    channel_info = [0]*9728
    sql_result = conn.execute("SELECT crate, slot, channel, resistor_pulled, "
        "zero_occupancy, low_occupancy, bad_discriminator FROM current_channel_status "
        "ORDER BY crate, slot, channel")

    sql_result = sql_result.fetchall()
    for crate, slot, channel, rpulled, low_occ, zero_occ, bad_disc in sql_result:
        lcn = crate*512 + slot*32 + channel
        channel_info[lcn] = [rpulled, (low_occ | zero_occ | bad_disc)]

    return channel_info


def relay_status(conn, run):
    """
    Returns the hv relay masks
    """
    relays = []
    result = conn.execute("SELECT crate, hv_relay_mask1, hv_relay_mask2 FROM "
        "crate_state where run = %s ORDER BY crate", run)

    rows = result.fetchall()

    hv_relays = {}
    for crate, hv_relay_mask1, hv_relay_mask2 in rows:
        hv_relays[crate] = hv_relay_mask1, hv_relay_mask2

    return hv_relays


def polling_info_card(data_type, run_number, crate):
    """
    Returns the polling data for a crate
    """
    conn = engine.connect()

    # Hold the polling information
    # for a single crate
    data = [0]*512

    # Default load the most recent run
    if run_number == 0:
        if data_type == "cmos":
            result = conn.execute("SELECT run FROM cmos ORDER BY run DESC LIMIT 1")
        elif data_type == "base":
            result = conn.execute("SELECT run FROM base ORDER BY run DESC LIMIT 1")
        else:
            return None

        if result is None:
            return None

        cmos_run = result.fetchone()

        for run in cmos_run:
            run_number = run

    if data_type == "cmos":
        result = conn.execute("SELECT DISTINCT ON (run, crate, slot, channel) "
            "slot, channel, cmos_rate FROM cmos WHERE run = %s "
            "AND crate = %s ORDER by run, slot, channel", (run_number, crate))
    elif data_type == "base":
        result = conn.execute("SELECT DISTINCT ON (run, crate, slot, channel) "
            "slot, channel, base_current FROM base WHERE run = %s "
            "AND crate = %s ORDER by run, slot, channel", (run_number, crate))
    else:
        return None

    if result is None:
        return None

    row = result.fetchall()
    for card, channel, cmos_rate in row:
        data[card*32+channel] = cmos_rate

    return data

def get_vmon(crate, slot):
    """
    Get the vmon data for a given crate/slot
    """
    conn = engine.connect()

    voltages = str(voltages_str_dict.keys())[1:-1]
    voltages = voltages.replace("'","")

    result = conn.execute("SELECT %s FROM current_vmon WHERE crate = %s "
        "AND slot = %s" % (voltages, crate, slot))

    keys = result.keys()
    rows = result.fetchone()

    if rows is None:
        return None, None

    bad_voltages = {}
    result = dict(zip(keys,rows))
    for key in result.keys():
        value = result[key]
        nominal_value = voltages_str_dict[key][1]
        new_key = voltages_str_dict[key][0] 
        result[new_key] = result.pop(key)
        if abs(value) < abs(nominal_value)*(1 - VMON_THRESH) or \
           abs(value) > abs(nominal_value)*(1 + VMON_THRESH):
            bad_voltages[new_key] = 1
        else:
            bad_voltages[new_key] = 0 

    return result, bad_voltages
