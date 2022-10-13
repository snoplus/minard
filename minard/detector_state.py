from __future__ import print_function, division
from .views import app
from .db import engine, engine_nl
from .channeldb import get_nominal_settings_for_run
from collections import defaultdict

def get_latest_run():
    """
    Returns the latest run number.
    """
    conn = engine.connect()

    result = conn.execute("SELECT last_value FROM run_number")

    return result.fetchone()[0]

def get_runs_with_run_type(run, run_type, max_run=1e9):
    """
    Returns a list all runs with a certain run type with a given run limit
    """
    conn = engine.connect()

    result = conn.execute("SELECT run from run_state where run > %s and run < %s AND (run_type & %s) > 0 ", \
                          (run, max_run, run_type))

    rows = result.fetchall()
    runs_with_runtype = []
    for run in rows:
        runs_with_runtype.append(int(run[0]))

    return runs_with_runtype

def get_mtc_state_for_run(run=0):
    """
    Returns a dictionary of the mtc settings for a given run. If there is no
    row in the database for the run, returns None.
    """
    conn = engine.connect()

    result = conn.execute("SELECT * FROM mtc WHERE key = (SELECT mtc FROM run_state WHERE run = %s)", (run,))

    if result is None:
        return None

    keys = result.keys()
    row = result.fetchone()

    return dict(zip(keys,row))

def get_tubii_state_for_run(run=0):
    """
    Returns a dictionary of the tubii settings for a given run. If there is no
    row in the database for the run, returns None.
    """
    conn = engine.connect()

    result = conn.execute("SELECT * FROM tubii WHERE key = (SELECT tubii FROM run_state WHERE run = %s)", (run,))

    keys = result.keys()
    row = result.fetchone()

    if row is None:
        return None

    return dict(zip(keys,row))

def get_caen_state_for_run(run=0):
    """
    Returns a dictionary of the caen settings for a given run. If there is no
    row in the database for the run, returns None.
    """
    conn = engine.connect()

    result = conn.execute("SELECT * FROM caen WHERE key = (SELECT caen FROM run_state WHERE run = %s)", (run,))

    if result is None:
        return None

    keys = result.keys()
    row = result.fetchone()

    return dict(zip(keys,row))

def get_detector_state(run=0):
    """
    Returns a dictionary of the crate settings for a given run. If there is no
    row in the database for the run, returns None.
    """
    conn = engine.connect()

    result = conn.execute("SELECT * FROM detector_state WHERE run = %s", (run,))

    if result is None:
        return None

    keys = result.keys()
    rows = result.fetchall()

    if len(rows) == 0:
        return None

    detector_state = dict((i, None) for i in range(20))

    for row in rows:
        crate = row[keys.index('crate')]

        if detector_state[crate] is None:
            detector_state[crate] = dict((i, None) for i in range(16))

        slot = row[keys.index('slot')]

        detector_state[crate][slot] = dict(zip(keys,row))

    result = conn.execute("SELECT * FROM crate_state WHERE run = %s", (run,))

    if result is not None:
        keys = result.keys()

        for row in result:
            crate = row[keys.index('crate')]

            if detector_state[crate] is None:
                detector_state[crate] = dict((i, None) for i in range(16))

            for i, key in enumerate(keys):
                detector_state[crate][key] = row[i]

    return detector_state

def get_alarms(run=0):
    """
    Returns a list of alarms that were active for a given run. If run is 0,
    then return the currently active alarms. If there is no row in the database
    for the run, returns None.
    """
    conn = engine.connect()

    if run == 0:
        result = conn.execute("SELECT * FROM active_alarms, alarm_descriptions "
            "WHERE active_alarms.alarm_id = alarm_descriptions.id")
    else:
        # get the start and stop times of the run
        result = conn.execute("SELECT timestamp, end_timestamp FROM run_state "
            "WHERE run = %s", (run,))

        row = result.fetchone()

        if row is None:
            return None

        timestamp, end_timestamp = row

        # select only alarms which were active sometime during the run
        # to do this, we find any alarm whose initial time is before the end of
        # the run and whose end time (cleared or acknowledged, whichever is
        # greater) is after the start of the run.
        result = conn.execute("SELECT * FROM alarms, alarm_descriptions "
            "WHERE (%s,COALESCE(%s,now())) OVERLAPS (time,GREATEST(COALESCE(cleared,now()), COALESCE(acknowledged,now()))) AND "
            "alarms.alarm_id = alarm_descriptions.id",
            (timestamp, end_timestamp))

    if result is None:
        return None

    keys = result.keys()
    rows = result.fetchall()

    return [dict(zip(keys,row)) for row in rows]

def compare_ecal_to_detector_state(run, crate, slot):
    """
    Comapre the detector state hardware settings for a run
    to the ECAL ran most recently before that run. Allows
    user to select crate and slot as well.
    Returns lists with differences between the states.
    """
    conn = engine.connect()

    if run == 0:
        run = get_latest_run()

    # Only select hardware values that are actually changed by the ECAL
    result = conn.execute("SELECT DISTINCT ON (crate, slot) crate, slot, vthr, tcmos_isetm, "
                           "vbal_0, vbal_1, mbid, dbid, tdisc_rmp FROM fecdoc WHERE "
                           "timestamp < (SELECT timestamp FROM "
                           "run_state WHERE run = %s) ORDER BY crate, slot, "
                           "timestamp DESC LIMIT 304", run)

    ecal_rows = result.fetchall()

    result = conn.execute("SELECT DISTINCT ON (crate, slot) crate, slot, vthr, tcmos_isetm, "
                          "vbal_0, vbal_1, mbid, dbid, tdisc_rmp FROM detector_state WHERE "
                          "run = %s ORDER BY crate, slot, timestamp DESC LIMIT 304", run)

    detector_rows = result.fetchall()

    vthr = []
    mbid = []
    dbid = []
    vbal0 = []
    vbal1 = []
    isetm = []
    rmp = []

    for crate1, slot1, vthr1, isetm1, vbal_01, vbal_11, mbid1, dbid1, rmp1 in ecal_rows:
        for crate2, slot2, vthr2, isetm2, vbal_02, vbal_12, mbid2, dbid2, rmp2 in detector_rows:
            if crate1 != crate2 or slot1 != slot2:
                continue
            if crate != -1 and crate != crate1: 
                continue
            if slot != -1 and slot != slot1:
                continue
            for i in range(32):
                if vthr1[i] != vthr2[i]:
                    vthr.append((crate1, slot1, i, vthr1[i], vthr2[i]))
                if vbal_01[i] != vbal_02[i]:
                    vbal0.append((crate1, slot1, i, vbal_01[i], vbal_02[i]))
                if vbal_11[i] != vbal_12[i]:
                    vbal1.append((crate1, slot1, i, vbal_11[i], vbal_12[i]))
                if i >= 8:
                    continue
                if rmp1[i] != rmp2[i]:
                    rmp.append((crate1, slot1, i, rmp1[i], rmp2[i]))
                if i >= 4:
                    continue
                if dbid1[i] != dbid2[i]:
                    dbid.append((crate1, slot1, i, hex(int(dbid1[i])), hex(int(dbid2[i]))))
                if i >= 2:
                    continue
                if isetm1[i] != isetm2[i]:
                    isetm.append((crate1, slot1, i, isetm1[i], isetm2[i]))
            if mbid1 != mbid2:
                mbid.append((crate1, slot1, hex(int(mbid1)), hex(int(mbid2))))

    return vthr, mbid, dbid, vbal0, vbal1, isetm, rmp

def get_detector_state_check(run=0):
    """
    Checks the detector state for a given run to see if there are any unknown
    settings or triggers that should/shouldn't be on. Returns a tuple
    (messages, channels) where messages is a list of messages of problems at
    the crate/slot level and channels is a list of tuples of the form (crate,
    slot, channel, message) for any channels which have triggers on when they
    shouldn't be. If there is no row in the database for the given run, returns
    (None, None).
    """
    run_state = get_run_state(run)

    if run_state is None:
        return None, None, None, None, None

    nominal_settings = get_nominal_settings_for_run(run)
    mtc_key = run_state['mtc']
    tubii_key = run_state['tubii']
    caen_key = run_state['caen']

    channels = []
    trig_messages = []
    hv_messages = []
    fec_messages = []
    off_messages = []
    relay_messages = []

    gt_crate_mask = None

    if mtc_key is None:
        trig_messages.append("mtc state unknown")
    else:
        mtc = get_mtc_state(mtc_key)
        gt_crate_mask = mtc['gt_crate_mask']
        if gt_crate_mask is None:
            trig_messages.append("GT crate mask unknown")
        elif not (gt_crate_mask & (1<<23)):
            trig_messages.append("TUBII is not in the GT crate mask")

        lockout_width = mtc['lockout_width']
        if lockout_width is None:
            trig_messages.append("Lockout width unknown")
        elif lockout_width != 420:
            trig_messages.append("Lockout width is a bad value: %i" % lockout_width)

        relay_mask = mtc['mtca_relays']
        if relay_mask is None:
            trig_messages.append("MTCA/+ relay mask unknown")
        else:
            mtca_names = ['N100', 'N20', 'ESUMLO', 'ESUMHI', 'OWLELO', 'OWLEHI', 'OWLN']
            for i, (relay, mtca) in enumerate(zip(relay_mask,mtca_names)):
                crates = []
                potential_crates = range(20) if i<4 else [3,13,18]
                for crate in potential_crates:
                    if relay is not None and not (relay & (1<<crate)):
                        crates.append(crate)
                if len(crates):
                    if len(crates) == 1:
                        trig_messages.append("crate %i is out of the %s MTCA+ relay mask" % (crates[0], mtca))
                    else:
                        trig_messages.append("crates %s are out of the %s MTCA+ relay mask" % (str(crates)[1:-1], mtca))

    # Keep track of which channels on TUBII we've plugged 
    # the MTC/A+ analog signals in. We want to put those 
    # channels in non-attenuated mode, and keep the others
    # in attenuated mode. The TUBII channel mapping has 
    # changed several times and the run-numbers are hard-coded.
    # Now with PPO in we leave only the ESUMH unattenuated.
    if run == 0 or run > 253142:
        nonattenuated = [2]
        attenuated = [0, 1, 3, 4, 5, 6, 7] 
    elif run > 250000:
        nonattenuated = [7]
        attenuated = range(0, 7)
    elif run > 205825:
        nonattenuated = [2, 6, 7]
        attenuated = [0, 1, 3, 4, 5]
    elif run > 200386:
        nonattenuated = [1, 6, 7]
        attenuated = [0, 2, 3, 4, 5]
    elif run > 113781:
        nonattenuated = [0, 1, 3]
        attenuated = [2, 4, 5, 6, 7]
    elif run > 110119:
        nonattenuated = [3, 5, 7]
        attenuated = [0, 1, 2, 4, 6]
    elif run > 107556:
        nonattenuated = [3, 6, 7]
        attenuated = [0, 1, 2, 4, 5]
    else:
        nonattenuated = [2, 3, 6]
        attenuated = [0, 1, 4, 5, 7]

    if tubii_key is None:
        trig_messages.append("tubii state unknown")
    else:
        tubii = get_tubii_state(tubii_key)

        clock_status = tubii['clock_status']
        if clock_status == 1:
            trig_messages.append("TUBII running on backup clock")

        readout_status = tubii['readout_status']
        if readout_status == 0:
            trig_messages.append("TUBII is not reading out")

        control_reg = tubii['control_reg']
        if control_reg is not None and (control_reg & (1<<2)):
            trig_messages.append("TUBII ECAL bit set")
        if control_reg is not None and not (control_reg & (1<<1)):
            trig_messages.append("Using TUBII LO*")

        # TUBII CAEN mapping
        tubii_gain = [1<<0, 1<<2, 1<<7, 1<<5, 1<<1, 1<<3, 1<<6, 1<<4]
        gain_reg = tubii['caen_gain_reg']
        attenuated_channels = []
        non_attenuated_channels = []
        if gain_reg is not None:
            # Loop over the eight TUBII channels and check the correct
            # channels are in non-attenuating mode
            for i in range(8):
                if i in nonattenuated and (tubii_gain[i] & gain_reg):
                    non_attenuated_channels.append(i)
                elif i in attenuated and not (tubii_gain[i] & gain_reg):
                    attenuated_channels.append(i)
            if len(non_attenuated_channels):
                if len(non_attenuated_channels) == 1:
                    trig_messages.append("Warning: TUBII channel %s is in attenuating mode"\
                        % non_attenuated_channels[0])
                else:
                    trig_messages.append("Warning: TUBII channels %s are in attentuating mode"\
                        % str(non_attenuated_channels)[1:-1])
            if len(attenuated_channels):
                if len(attenuated_channels) == 1:
                    trig_messages.append("Warning: TUBII channel %s is in non-attenuating mode"\
                        % attenuated_channels[0])
                else:
                    trig_messages.append("Warning: TUBII channels %s are in non-attentuating mode"\
                        % str(attenuated_channels)[1:-1])

    caen_state = get_caen_state(caen_key)

    if caen_state is None:
        trig_messages.append("CAEN settings are unknown.")
    else:
        window_length = caen_state['custom_size']*4*4
        if window_length != 416: # Not the standard length
            trig_messages.append("CAEN window size is %i ns." % window_length)

    detector_state = get_detector_state(run)

    if detector_state is None:
        off_messages.append("All crates are off")
        return trig_messages, hv_messages, off_messages, fec_messages, channels

    for crate in range(19):
        if detector_state[crate] is None:
            off_messages.append("crate %i is off" % crate)
            continue

        if gt_crate_mask is not None and mtc_key is not None and not (gt_crate_mask & (1<<crate)):
            trig_messages.append("crate %i is not in the GT crate mask" % crate)

        xl3_mode = detector_state[crate]['xl3_mode']
        if xl3_mode == 1:
            fec_messages.append("crate %i is in init mode" % crate)

        hv_on = detector_state[crate]['hv_a_on'] == True
        if not hv_on:
            hv_messages.append("crate %i HV is off" % crate)

        if crate == 16 and not detector_state[crate]['hv_b_on']:
            hv_messages.append("OWL HV is off")

        hv_relay_mask1 = detector_state[crate]['hv_relay_mask1']
        hv_relay_mask2 = detector_state[crate]['hv_relay_mask2']

        readout_mask = detector_state[crate]['xl3_readout_mask']
        if readout_mask is None:
            off_messages.append("crate %i readout mask is unknown" % crate)

        if hv_relay_mask1 is None or hv_relay_mask2 is None:
            off_messages.append("crate %i relay settings are unknown" % crate)

        no_readout = []

        for slot in range(16):

            # Check HV on OWL slots
            if (crate == 3 or crate == 13 or crate == 18) and slot == 15:
                try:
                    hv_on = detector_state[16]['hv_b_on'] == True
                except KeyError:
                    hv_on = False
                except TypeError:
                    hv_on = False

            if detector_state[crate][slot] is None:
                fec_messages.append("FEC in crate %i slot %i is missing" % (crate, slot))
                continue

            if readout_mask is not None and not (readout_mask & (1<<slot)) and xl3_mode == 2:
                no_readout.append(slot) 

            slot_sequencers = detector_state[crate][slot]['disable_mask']
            if slot_sequencers is not None and slot_sequencers == 0xffffffff and (readout_mask & (1<<slot)):
                fec_messages.append("Sequencers disabled for crate %i, slot %i" % (crate, slot))

            if hv_relay_mask1 is None or hv_relay_mask2 is None:
                continue

            hv_relay_mask = hv_relay_mask2 << 32 | hv_relay_mask1

            if detector_state[crate][slot]['tr100_mask'] is None:
                fec_messages.append("trigger settings unknown for crate %i, slot %i" % (crate, slot))
                continue
            if detector_state[crate][slot]['tr20_mask'] is None:
                fec_messages.append("trigger settings unknown for crate %i, slot %i" % (crate, slot))
                continue
            if detector_state[crate][slot]['disable_mask'] is None:
                fec_messages.append("sequencer settings unknown for crate %i, slot %i" % (crate, slot))
                continue
            if detector_state[crate][slot]['vthr'] is None:
                fec_messages.append("vthr settings unknown for crate %i, slot %i" % (crate, slot))
                continue

            # Count consecutive maxed thresholds on each slot
            count_maxed_vthr = 0
            nmaxed = 0

            relay_count = 0
            relay_channels = []
            for channel in range(32):
                relay_closed = hv_relay_mask & (1 << (slot*4 + (3-channel//8)))
                if not relay_closed:
                    relay_count+=1
                    if (channel+1) % 8 == 0:
                        relay_channels.append(channel)

                if relay_count == 32:
                    relay_messages.append("Relays open for crate %i slot %i" % (crate, slot))

                hv_enabled = hv_relay_mask & relay_closed and hv_on
                n100 = bool(detector_state[crate][slot]['tr100_mask'][channel])
                n20 = bool(detector_state[crate][slot]['tr20_mask'][channel])
                sequencer = bool(~detector_state[crate][slot]['disable_mask'] & (1 << channel))
                vthr = detector_state[crate][slot]['vthr'][channel]
                if vthr is None:
                    fec_messages.append("vthr unknown for crate %i, slot %i" % (crate, slot))
                try:
                    n100_nominal, n20_nominal, sequencer_nominal = nominal_settings[crate][slot][channel]
                except KeyError:
                    channels.append("unable to get nominal settings for %i/%i/%i" % (crate, slot, channel))
                    continue

                if not hv_enabled:
                    if n100:
                        if hv_on:
                            channels.append((crate,slot,channel,"HV relay is open, but N100 trigger is on"))
                        else:
                            channels.append((crate,slot,channel,"HV is off, but N100 trigger is on"))
                    if n20:
                        if hv_on:
                            channels.append((crate,slot,channel,"HV relay is open, but N20 trigger is on"))
                        else:
                            channels.append((crate,slot,channel,"HV is off, but N20 trigger is on"))
                else:
                    if n100_nominal != n100:
                        channels.append((crate, slot, channel, "N100 trigger is %s, but nominal setting is %s" % \
                            ("on" if n100 else "off", "on" if n100_nominal else "off")))
                    if n20_nominal != n20:
                        channels.append((crate, slot, channel, "N20 trigger is %s, but nominal setting is %s" % \
                            ("on" if n20 else "off", "on" if n20_nominal else "off")))
                    if sequencer_nominal != sequencer:
                        channels.append((crate, slot, channel, "sequencer is %s, but nominal setting is %s" % \
                            ("on" if sequencer else "off", "on" if sequencer_nominal else "off")))
                    if not sequencer:
                        channels.append((crate, slot, channel, "sequencer is off, but channel is at HV! Potential blind flasher!"))
                    if readout_mask is not None and not (readout_mask & (1<<slot)) and xl3_mode == 2:
                        channels.append((crate, slot, channel, "not being read out, but is at HV! Potential blind flasher!"))
                    if vthr > 250 and n100:
                        channels.append((crate, slot, channel, "Maxed threshold but N100 trigger is on.")) 
                    if vthr > 250 and n20:
                        channels.append((crate, slot, channel, "Maxed threshold but N20 trigger is on."))
                    # FECD always fails the VTHR checks, so skip it
                    if crate == 17 and slot == 15:
                        continue
                    # Only warn if more than 8 consecutive maxed thresholds at high voltage
                    if count_maxed_vthr >= 8:
                        nmaxed = count_maxed_vthr
                    # Assumption is anything above 250 DAC counts is 'maxed'
                    if vthr > 250:
                        count_maxed_vthr += 1
                    else:
                        count_maxed_vthr = 0

            if nmaxed >= 8:
                fec_messages.append("Warning: crate %i slot %i at HV but has %i consecutive thresholds maxed" % (crate, slot, nmaxed))

            if len(relay_channels) == 1:
                relay_messages.append("Relay open crate %i slot %i PC %i" % (crate, slot, (relay_channels[0])/8))
            elif len(relay_channels) == 2:
                relay_messages.append("Relays open crate %i slot %i PC %i/%i" % (crate, slot, relay_channels[0]/8, relay_channels[1]/8))
            elif len(relay_channels) == 3:
                relay_messages.append("Relays open crate %i slot %i PC %i/%i/%i" % (crate, slot, relay_channels[0]/8, relay_channels[1]/8, relay_channels[2]/8))

        if no_readout:
            no_readout_list = "/".join(str(x) for x in no_readout)
            slot_str = "slot"
            FEC_str = "FEC"
            if len(no_readout) > 1:
                slot_str = "slots"
                FEC_str = "FECs"
            fec_messages.append("%s in crate %i %s %s not being readout" % (FEC_str, crate, slot_str, no_readout_list))

    return trig_messages, hv_messages, relay_messages, off_messages, fec_messages, channels

def get_nhit_monitor_thresholds(limit=100, offset=0):
    """
    Returns a list of the latest nhit monitor records in the database.
    """
    conn = engine.connect()

    result = conn.execute("SELECT * FROM nhit_monitor_thresholds ORDER BY timestamp DESC LIMIT %s OFFSET %s", (limit,offset))

    if result is None:
        return None

    keys = result.keys()
    rows = result.fetchall()

    return [dict(zip(keys,row)) for row in rows]

def get_nhit_monitor(key):
    """
    Returns an nhit monitor record from the database.
    """
    conn = engine.connect()

    result = conn.execute("SELECT * FROM nhit_monitor WHERE key=%s", (key,))

    if result is None:
        return None

    keys = result.keys()
    row = result.fetchone()

    return dict(zip(keys,row))

def get_nhit_monitor_thresholds_nearline(limit=100, offset=0, sort_by="run", run_range_low=0, run_range_high=0):
    """
    Returns a list of the latest nhit monitor records in the nearline database.
    """
    conn = engine_nl.connect()

    if run_range_high:
        if sort_by == "run":
            result = conn.execute("SELECT * FROM nhit_monitor_thresholds WHERE run >= %s AND run <= %s "
                                  "ORDER BY run DESC, timestamp DESC LIMIT %s OFFSET %s", \
                                  (run_range_low, run_range_high, limit, offset))
        if sort_by == "key":
            result = conn.execute("SELECT * FROM nhit_monitor_thresholds WHERE run >= %s AND run <= %s "
                                  "ORDER BY key DESC, timestamp DESC LIMIT %s OFFSET %s", \
                                  (run_range_low, run_range_high, limit, offset))
    else:
        if sort_by == "run":
            result = conn.execute("SELECT * FROM nhit_monitor_thresholds ORDER BY run DESC, " 
                                  "timestamp DESC LIMIT %s OFFSET %s", (limit,offset))
        if sort_by == "key":
            result = conn.execute("SELECT * FROM nhit_monitor_thresholds ORDER BY key DESC, " 
                                  "timestamp DESC LIMIT %s OFFSET %s", (limit,offset))

    if result is None:
        return None

    keys = result.keys()
    rows = result.fetchall()

    return [dict(zip(keys,row)) for row in rows]

def get_nhit_monitor_nearline(key):
    """
    Return an nhit monitor record from the nearline database.
    """
    conn = engine_nl.connect()

    result = conn.execute("SELECT * FROM nhit_monitor WHERE key=%s", (key,))

    if result is None:
        return None

    keys = result.keys()
    row = result.fetchone()

    return dict(zip(keys,row))

def get_latest_trigger_scans():
    """
    Returns a list of the latest trigger scans for each trigger type. Each item
    in the returned list is a dictionary with keys from the columns of the
    table and values from the rows.

    Returns None if there are no trigger scans.
    """
    conn = engine.connect()

    result = conn.execute("select distinct on (name) * from trigger_scan order by name, key desc")

    if result is None:
        return None

    keys = result.keys()
    rows = result.fetchall()

    return [dict(zip(keys,row)) for row in rows]

def get_trigger_scan_for_run(run):
    """
    Returns a dictionary with the trigger scan records for a given run. The
    keys of the dictionary are the trigger type names and the values are a
    dictionary with keys from the columns of the bable and values from the
    rows. For example,

        >>> get_trigger_scan_for_run(1000)
        {'N100MED': {'name':'N100MED', 'crate': 17, 'baseline': 4078, 'adc_per_nhit': -2.33}, ...}
    """
    names = ['N100HI','N100LO','N100MED','N20LB','N20','OWLN']

    conn = engine.connect()

    if run == 0:
        # get the latest trigger scan
        result = conn.execute("SELECT DISTINCT ON (name) * FROM trigger_scan "
            "ORDER BY name, key DESC", (run,))
    else:
        result = conn.execute("SELECT DISTINCT ON (name) * FROM trigger_scan "
            "WHERE timestamp < (SELECT timestamp FROM run_state WHERE run = %s) "
            "ORDER BY name, key DESC", (run,))

    keys = result.keys()
    rows = result.fetchall()

    return dict((row['name'], dict(zip(keys,row))) for row in rows if row['name'] in names)

def fetch_from_table_with_key(table_name, key, key_name='key'):
    if key is None:
        key = "(SELECT max(%s) FROM %s)" % (key_name, table_name)

    conn = engine.connect()

    command = "SELECT * FROM %s WHERE %s = %s" % (table_name, key_name, key)
    res =  conn.execute(command)

    try:
        values = zip(res.keys(),res.fetchone())
    except TypeError:
        # Chances are this failed b/c the SELECT command didn't find anything
        raise ValueError("%s %s is not valid...probably" % (key_name, key))

    return dict(values)

def get_detector_control_state(key):
    return fetch_from_table_with_key('detector_control',key)

def get_caen_state(key):
    return fetch_from_table_with_key('caen',key)

def get_tubii_state(key):
    return fetch_from_table_with_key('tubii',key)

def get_mtc_state(key):
    return fetch_from_table_with_key('mtc',key)

def get_crate_state(key):
    cards = fetch_from_table_with_key('crate',key)
    ret={}
    for card_num in range(16):
        card_key = "mb%i" % card_num
        ret[card_num] = fetch_from_table_with_key('fec',cards[card_key])
    return ret

def get_fec_state(key):
    return fetch_from_table_with_key('fec',key)

def get_run_state(run):
    """
    Returns a dictionary of the columns from the run_state table for a given
    run in the database. If run is None, return the columns from the run_state
    table for the latest run.

    Returns None if there is no data for that particular run.
    """
    conn = engine.connect()

    if run is None:
        # Return the latest run
        result = conn.execute("SELECT * FROM run_state ORDER BY timestamp DESC LIMIT 1")
    else:
        result = conn.execute("SELECT * FROM run_state WHERE run = %s", (run,))

    if result is None:
        return None

    keys = result.keys()
    row = result.fetchone()

    if row is None:
        return None

    return dict(zip(keys,row))

def get_hv_nominals():
    conn = engine.connect()
    command = "SELECT crate,supply,nominal FROM hvparams ORDER BY crate ASC"
    res =  conn.execute(command)
    if res is None:
        return None
    ret = {}
    for crate, supply, nominal in res.fetchall():
        if crate == 16 and supply == "B":
            ret["OWL"] = nominal
        else:
            ret[crate] = nominal
    return ret

def translate_trigger_mask(maskVal):
    trigger_bit_to_string = [
                                (0 ,"NHIT100LO"),
                                (1 ,"NHIT100MED"),
                                (2 ,"NHIT100HI"),
                                (3 ,"NHIT20"),
                                (4 ,"NHIT20LB"),
                                (5 ,"ESUMLO"),
                                (6 ,"ESUMHI"),
                                (7 ,"OWLN"),
                                (8 ,"OWLELO"),
                                (9 ,"OWLEHI"),
                                (10,"PULSE_GT"),
                                (11,"PRESCALE"),
                                (12,"PEDESTAL"),
                                (13,"PONG"),
                                (14,"SYNC"),
                                (15,"EXT_ASYNC"),
                                (16,"EXT2"),
                                (17,"EXT3"),
                                (18,"EXT4"),
                                (19,"EXT5"),
                                (20,"EXT6"),
                                (21,"EXT7"),
                                (22,"EXT8_PULSE_ASYNC"),
                                (23,"SPECIAL_RAW"),
                                (24,"NCD"),
                                (25,"SOFT_GT")
                            ]
    triggers =  filter(lambda x: ((maskVal & 1<<x[0]) > 0),trigger_bit_to_string)
    return map(lambda x: x[1],triggers)

def translate_ped_delay(coarse_delay, fine_delay):
    MIN_GT_DELAY = 18.35; # Taken from daq/src/mtc.c
    return MIN_GT_DELAY + coarse_delay + fine_delay/1000.0;

def translate_control_reg(control_reg):
    bit_to_string = [
        (0, "PED_EN"),
        (1, "PULSE_EN"),
        (2, "LOAD_ENPR"),
        (3, "LOAD_ENPS"),
        (4, "LOAD_ENPW"),
        (5, "LOAD_ENLK"),
        (6, "ASYNC_EN"),
        (7, "RESYNC_EN"),
        (8, "TESTGT"),
        (9, "TEST50"),
        (10, "kTEST10"),
        (11, "kLOAD_ENGT"),
        (12, "kLOAD_EN50"),
        (13, "kLOAD_EN10"),
        (14, "kTESTMEM1"),
        (15, "kTESTMEM2"),
        (16, "FIFO_RESET")
        ]
    word_list = filter(lambda x:((control_reg & 1<<x[0]) >0), bit_to_string)
    return map(lambda x:x[1], word_list)

def translate_crate_mask(mask):
    return map(lambda x: (mask & 1<<x) > 0,range(0,20))

def translate_mtca_dacs(dacs):
    ret = {}
    ret["N100 LO"] = dacs[0]
    ret["N100 MED"] = dacs[1]
    ret["N100 HI"] = dacs[2]
    ret["N20"] = dacs[3]
    ret["N20 LB"] = dacs[4]
    ret["ESUM LO"] = dacs[5]
    ret["ESUM HI"] = dacs[6]
    ret["OWLN"] = dacs[7]
    ret["OWLE LO"] = dacs[8]
    ret["OWLE HI"] = dacs[9]
    #Not bothering with the spares (for now) (or ever probably)
    return ret;

@app.template_filter('mtc_human_readable')
def mtc_human_readable_filter(mtc):
    ret = {}
    try:
        ret['gt_words'] = translate_trigger_mask(mtc['gt_mask'])
        ret['ped_delay'] = translate_ped_delay(mtc['coarse_delay'],mtc['fine_delay'])
        ret['lockout_width'] = mtc['lockout_width']
        ret['pulser_rate'] = mtc['pulser_rate']
        ret['control_reg'] = translate_control_reg(mtc['control_register'])
        ret['prescale'] = mtc['prescale']
        ret['gt_crates'] = translate_crate_mask(mtc['gt_crate_mask'])
        ret['ped_crates'] = translate_crate_mask(mtc['pedestal_mask'])
        ret['N100_crates'] = translate_crate_mask(mtc['mtca_relays'][0])
        ret['N20_crates'] = translate_crate_mask(mtc['mtca_relays'][1])
        ret['ESUMLO_crates'] = translate_crate_mask(mtc['mtca_relays'][2])
        ret['ESUMHI_crates'] = translate_crate_mask(mtc['mtca_relays'][3])
        ret['OWLELO_crates'] = translate_crate_mask(mtc['mtca_relays'][4])
        ret['OWLEHI_crates'] = translate_crate_mask(mtc['mtca_relays'][5])
        ret['OWLN_crates'] = translate_crate_mask(mtc['mtca_relays'][6])
        ret['MTCA_DACs'] = translate_mtca_dacs(mtc['mtca_dacs']);
    except Exception:
        return False
    return ret

def translate_caen_front_panel_io_control(mask):
    ret = {}
    ret["trigger_voltage_level"] = "TTL" if (mask & 1) >0 else "NIM"
    ret["high_impedance_output"] = (mask & 1<<1) > 0
    ret["lvds_input"] = [(mask & 1<<i) > 0 for i in range(2,6)]
    bit_6 = (mask & i <<6)>0
    bit_7 = (mask & i <<7)>0
    ret["lvds_mode"] = "Programmed IO" if bit_6 else "Pattern" if bit_7 else "General Purpose"
    ret["trig_out_logic_level"] = 1 if (mask & i<<14) >0 else 0
    ret["io_test_mode"] = (mask & i<<15) >0
    return ret

def translate_caen_acquisition_control(mask):
    ret = {}
    bit_0 = (mask & 1) >0
    bit_1 = (mask & 1<<1) >0
    if bit_0:
        ret["acquisition_mode"] = "Multi-board sync" if bit_1 else "S-IN Controlled Run"
    else:
        ret["acquisition_mode"] ="S-IN Gate" if bit_1 else "Register Controlled"
    ret["acquiring"] = (mask & 1<<2) > 0
    ret["count_all_triggers"] = (mask & 1<<2) >1
    return ret

def translate_caen_channel_configuaration(mask):
    ret = {}
    ret["trigger_overlapping"] = (mask & 1<<1) >0
    ret["test_pattern_generation"] = (mask & 1<<3) > 0 #NOTE TEST THIS IT MIGHT BE BIT 2 see 4.12 of CAEN MANUAL
    ret["sequential_memory_access"] = "Sequential" if (mask & 1<<4) >0 else "Random"
    ret["downward_going_trigger"] = (mask & 1<<6) >0 #Might be bit 5 again see 4.12 of CAEN
    ret["pack2.5"] = (mask & 1<<11) >0
    bit_16 = (mask & 1<<16) >0
    bit_17 = (mask & 1<<17) >0
    ret["zero_suppresion_algorithm"] = "ZS AMP" if bit_16 else "ZLE" if bit_17 else "None"
    return ret

def translate_caen_trigger(trig_source_mask,trig_out_mask):
    ret ={}
    channels = []
    for i in range(8):
        channels.append([(trig_source_mask & 1<<i) >0,(trig_out_mask & 1<<i)>0])
    ret["channel_triggers"] = channels
    ret["external_trigger"] = [(trig_source_mask & 1<<30) > 0, (trig_out_mask & 1<< 30 )> 0]
    ret["software_trigger"] = [(trig_source_mask & 1<<31) > 0, (trig_out_mask & 1<< 31 )> 0]
    return ret


@app.template_filter('caen_human_readable')
def caen_human_readable_filter(caen):
    ret = {}
    try:
        ret['post_trigger'] = caen['post_trigger']*4
        ret['enabled_channels'] = \
            map(lambda x: (1 << x & caen['channel_mask']) > 0, range(8))

        ret.update(translate_caen_front_panel_io_control(caen['front_panel_io_control']))
        ret.update(translate_caen_acquisition_control(caen['front_panel_io_control']))
        ret.update(translate_caen_channel_configuaration(caen['channel_configuration']))
        ret['buffer_organization'] = hex(caen["buffer_organization"])
        ret.update(translate_caen_trigger(caen["trigger_mask"], caen["trigger_out_mask"]))

        # channel_dacs was added to the DB later than everything else.
        # So a number of runs don't have channel_offset info.
        # Therefore it's afforded special treatment
        try:
            ret['channel_offsets'] = [x/0xffff-1.0 for x in caen['channel_dacs']]
        except TypeError:
            ret['channel_offsets'] = 0

    except Exception as e:
        print("CAEN translation error: %s" % e)
        return False
    return ret

@app.template_filter('tubii_human_readable')
def tubii_human_readable_filter(tubii):
    ret = {}
    try:
        ret['clock_source'] = tubii['control_reg'] & 1
        ret['lo_source'] = (tubii['control_reg'] & 2)/2
        ret['ecal'] = (tubii['control_reg'] & 4)/4
        ret['clock_status'] = tubii['clock_status']
        ret['trigger_mask'] = tubii['trigger_mask']
        ret['async_trigger_mask'] = tubii['async_trigger_mask']
        ret['counter_mask'] = tubii['counter_mask']
        ret['counter_mode'] = tubii['counter_mode']
        ret['speaker_mask'] = tubii['speaker_mask']
        ret['caen_gain_path'] = tubii['caen_gain_reg']
        ret['caen_channel_select'] = tubii['caen_channel_reg']
        ret['lockout_reg'] = 5*tubii['lockout_reg']
        ret['dgt_reg'] = 2*tubii['dgt_reg']
        ret['dac_reg'] = (10/4096)*tubii['dac_reg'] -5
        ret['burst_channel'] = tubii['burst_channel']
        ret['burst_slave'] = tubii['burst_slave']
        ret['burst_rate'] = tubii['burst_rate']
        ret['combo_mask'] = tubii['combo_mask']
        ret['combo_enable_mask'] = tubii['combo_enable_mask']
        ret['prescale_value'] = tubii['prescale_value']
        ret['prescale_channel'] = tubii['prescale_channel']
        ret['pgt_rate'] = tubii['pgt_rate']
        ret['smellie_delay_length'] = tubii['smellie_delay_length']
        ret['smellie_pulse_rate'] = tubii['smellie_pulse_rate']
        ret['smellie_pulse_width'] = tubii['smellie_pulse_width']
        ret['smellie_npulses'] = tubii['smellie_npulses']
        ret['tellie_delay_length'] = tubii['tellie_delay_length']
        ret['tellie_pulse_rate'] = tubii['tellie_pulse_rate']
        ret['tellie_pulse_width'] = tubii['tellie_pulse_width']
        ret['tellie_npulses'] = tubii['tellie_npulses']
        ret['delay_length'] = tubii['delay_length']
        ret['pulse_rate'] = tubii['pulse_rate']
        ret['pulse_width'] = tubii['pulse_width']
        ret['npulses'] = tubii['npulses']
    except Exception as e:
        print("TUBii translation error: %s" % e)
        return False
    return ret

@app.template_filter('all_crates_human_readable')
def all_crates_human_readable(detector_state):
    if detector_state is None:
        return False
    crates = []
    ret = {}
    try:
        for i in range(20):
            crates.append(crate_human_readable_filter(detector_state[i]))
    except Exception as e:
        print("Crate translation error: %s" % e)
        return False
    ret['crates'] = crates
    available_crates = filter(None,crates)
    ret['num_n100_triggers'] = sum(map(lambda x:x['num_n100_triggers'],available_crates))
    ret['num_n20_triggers'] = sum(map(lambda x:x['num_n20_triggers'],available_crates))
    ret['num_sequencers'] = sum(map(lambda x:x['num_sequencers'],available_crates))
    ret['num_relays'] = sum(map(lambda x:x['num_relays'],available_crates))

    return ret

@app.template_filter('crate_human_readable')
def crate_human_readable_filter(crate):
    if crate is None:
        return False
    fecs = []
    ret = {}
    relay_mask1 = crate["hv_relay_mask1"]
    relay_mask2 = crate["hv_relay_mask2"]

    if relay_mask2 is None or relay_mask1 is None:
        relay_mask = None
    else:
        relay_mask = relay_mask1 | relay_mask2 << 32
    try:
        for card in range(0,16):
            fecs.append(fec_human_readable_filter(crate[card]))
            fecs[card]["relays"] = [None]*4
            if relay_mask is not None:
                for PC in range(4):
                    fecs[card]["relays"][PC] = (relay_mask & 1<<(card*4+(3-PC)) ) > 0
    except Exception as e:
        print("FEC translation error: %s" % e)
        return False
    ret['fecs'] = fecs
    ret['hv_a_on'] = crate['hv_a_on']
    ret['hv_b_on'] = crate['hv_b_on']
    ret['hv_dac_a'] = crate['hv_dac_a']
    ret['hv_dac_b'] = crate['hv_dac_b']
    available_fecs = filter(None,fecs)
    ret['num_n100_triggers'] = sum(map(lambda x:x['num_n100_triggers'],available_fecs))
    ret['num_n20_triggers'] = sum(map(lambda x:x['num_n20_triggers'],available_fecs))
    ret['num_sequencers'] = sum(map(lambda x:x['num_sequencers'],available_fecs))
    ret['num_relays'] = sum( [ sum(fec['relays']) if any(fec['relays']) else 0 for fec in available_fecs])
    return ret

def translate_fec_disable_mask(mask):
    return map(lambda x: 0 if ((mask & (1<<x))>0) else 1,range(32))

@app.template_filter('fec_human_readable')
def fec_human_readable_filter(fec):
    ret = defaultdict(bool)
    try:
        ret['n20_triggers'] = fec['tr20_mask']
        ret['n100_triggers'] = fec['tr100_mask']
        ret['vthrs'] = fec['vthr']
        ret['num_n20_triggers'] = len(filter(None,fec['tr20_mask']))
        ret['num_n100_triggers'] = len(filter(None,fec['tr100_mask']))
        ret['DB_IDs'] = map(lambda x: '0x%x' % x,fec['dbid'])
        ret['MB_ID'] = '0x%x' % fec['mbid']
        ret['sequencers'] = translate_fec_disable_mask(fec['disable_mask'])
        ret['num_sequencers'] = len(filter(None,ret['sequencers']))
        ret['vbal_0'] = fec['vbal_0']
        ret['vbal_1'] = fec['vbal_1']
    except Exception as e:
        pass
    return ret

def trigger_scan_string_translate(name):
    if name == 'N100LO':
        return 'N100 LO'
    elif name == 'N100MED':
        return 'N100 MED'
    elif name == 'N100HI':
        return 'N100 HI'
    elif name == 'N20LB':
        return 'N20 LB'
    elif name == 'ESUMHI':
        return 'ESUM HI'
    elif name == 'ESUMLO':
        return 'ESUM LO'
    elif name == 'OWLEHI':
        return 'OWLE HI'
    elif name == 'OWLELO':
        return 'OWLE LO'

    return name

@app.template_filter('trigger_scan_human_readable')
def trigger_scan_human_readable(trigger_scan):
    if trigger_scan is None:
        return False
    res = {}
    try:
        for name, obj in trigger_scan.iteritems():
            name = trigger_scan_string_translate(name)
            vals = False
            if(obj):
                vals = (obj['baseline'], obj['adc_per_nhit'])
            res[name] = vals
    except Exception as e:
        print("trigger scan translation error: %s" % e)
        return False
    return res
