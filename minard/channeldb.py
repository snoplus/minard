from wtforms import Form, BooleanField, StringField, validators, IntegerField, PasswordField
from .db import engine
from .views import app
import psycopg2
import psycopg2.extensions

class ChannelStatusForm(Form):
    """
    A class for the form to update the channel status database.
    """
    crate =              IntegerField('crate', [validators.NumberRange(min=0,max=19)])
    slot =               IntegerField('slot', [validators.NumberRange(min=0,max=15)])
    channel =            IntegerField('channel', [validators.NumberRange(min=0,max=31)])
    pmt_removed =        BooleanField('PMT removed')
    pmt_reinstalled =    BooleanField('PMT reinstalled')
    low_occupancy =      BooleanField('Low Occupancy')
    zero_occupancy =     BooleanField('Zero Occupancy')
    screamer =           BooleanField('Screamer')
    bad_discriminator =  BooleanField('Bad Discriminator')
    no_n100 =            BooleanField('No N100')
    no_n20 =             BooleanField('No N20')
    no_esum =            BooleanField('No ESUM')
    cable_pulled =       BooleanField('Cable pulled')
    bad_cable =          BooleanField('Bad Cable')
    resistor_pulled =    BooleanField('Resistor pulled')
    disable_n100 =       BooleanField('Disable N100')
    disable_n20 =        BooleanField('Disable N20')
    high_dropout =       BooleanField('High Dropout')
    bad_base_current =   BooleanField('Bad Base Current')
    bad_data =           BooleanField('Bad Data')
    bad_calibration =    BooleanField('Bad Calibration')
    name =               StringField('Name', [validators.Length(min=1)])
    reason =             StringField('Reason')
    info =               StringField('Info', [validators.Length(min=1)])
    password =           PasswordField('Password')

@app.template_filter('pmt_type_description')
def pmt_type_description(pmt_type):
    """
    Converts a PMT type -> useful description.
    """
    active, pmt_type = pmt_type & 0x1, pmt_type & 0xfffe

    if pmt_type == 0x2:
        return "Normal"
    elif pmt_type == 0x4:
        return "Rope"
    elif pmt_type == 0x8:
        return "Neck"
    elif pmt_type == 0x10:
        return "FECD"
    elif pmt_type == 0x20:
        return "Low Gain"
    elif pmt_type == 0x40:
        return "OWL"
    elif pmt_type == 0x80:
        return "BUTT"
    elif pmt_type == 0x12:
        return "Petal-less"
    elif pmt_type == 0x00:
        return "None"
    elif pmt_type == 0x100:
        return "HQE"
    else:
        return "Unknown type 0x%04x" % pmt_type

def get_fec_db_history(crate, card, channel):
    """
    Returns a list of the FEC and/or DB swaps for a given channel.
    """
    conn = engine.connect()

    query = ("SELECT run, timestamp, mbid, dbid FROM ("
        "SELECT run, mbid, dbid FROM ("
            "SELECT run, mbid, dbid[%i] as dbid, "
            "lag(mbid) OVER (ORDER BY run ASC) "
                "IS DISTINCT FROM mbid AS fec_changed, "
            "lag(dbid[%i]) OVER (ORDER BY run ASC) "
                "IS DISTINCT FROM dbid[%i] AS db_changed "
            "FROM detector_state WHERE crate = %%(crate)s AND "
            "slot = %%(card)s AND mbid IS NOT NULL AND dbid IS NOT NULL AND "
            "run > 0) sub WHERE fec_changed OR db_changed"
        ") _ NATURAL JOIN run_state ORDER BY run" % \
        (channel//8+1, channel//8+1, channel//8+1))

    result = conn.execute(query, crate=crate, card=card)

    keys = result.keys()
    rows = result.fetchall()

    return [dict(zip(keys,row)) for row in rows]

def get_channels(kwargs, limit=100, sort_by=None):
    """
    Returns a list of the current channel statuses for multiple channels in the
    detector. `kwargs` should be a dictionary containing fields and their
    associated values to select on. For example, to select only channels that
    have low occupancy:

        >>> get_channels({'low_occupancy': True})

    `limit` should be the maximum number of records returned.
    """
    conn = engine.connect()

    fields = [field.name for field in ChannelStatusForm()]

    conditions = []
    for key in kwargs:
        if key == 'type':
            conditions.append("type & 65534 = %(type)s")
        elif key in fields:
            conditions.append("%s = %%(%s)s" % (key, key))

    query = "SELECT * FROM current_channel_status NATURAL JOIN pmt_info "
    if len(conditions):
        query += "WHERE %s " % (" AND ".join(conditions))

    if sort_by == 'timestamp':
        query += "ORDER BY timestamp DESC LIMIT %i" % limit
    else:
        query += "ORDER BY crate, slot, channel LIMIT %i" % limit

    result = conn.execute(query, kwargs)

    if result is None:
        return None

    keys = result.keys()
    rows = result.fetchall()

    return [dict(zip(keys,row)) for row in rows]

def get_channel_history(crate, slot, channel, limit=None):
    """
    Returns a list of the channel statuses for a single channel in the
    detector. `limit` is the maximum number of records to return.
    """
    conn = engine.connect()

    query = "SELECT * FROM channel_status " + \
        "WHERE crate = %s AND slot = %s AND channel = %s " + \
        "ORDER BY timestamp DESC"

    if limit is not None:
        query += " LIMIT %i" % limit

    result = conn.execute(query, (crate,slot,channel))

    if result is None:
        return None

    keys = result.keys()
    rows = result.fetchall()

    return [dict(zip(keys,row)) for row in rows]

def get_pmt_info(crate, slot, channel):
    """
    Returns a dictionary of the pmt info for a given channel.
    """
    conn = engine.connect()

    result = conn.execute("SELECT * FROM pmt_info "
        "WHERE crate = %s AND slot = %s AND channel = %s",
        (crate, slot, channel))

    if result is None:
        return None

    keys = result.keys()
    row = result.fetchone()

    if row is None:
        return None

    return dict(zip(keys,row))

def get_pmt_types():
    """
    Returns a list of the pmt types for all channels.
    """
    conn = engine.connect()

    result = conn.execute("SELECT crate, slot, channel, type FROM pmt_info")

    if result is None:
        return None

    rows = result.fetchall()

    pmt_info = {}
    for row in rows:
        crate, slot, channel, pmt_type = row
        if crate not in pmt_info:
            pmt_info[crate] = {}
        if slot not in pmt_info[crate]:
            pmt_info[crate][slot] = {}
        pmt_info[crate][slot][channel] = pmt_type

    return pmt_info

def get_nominal_settings_for_run(run=0):
    """
    Returns a dictionary of the nominal settings for all the channels in the
    detector for a given run.
    """
    conn = engine.connect()

    if run == 0:
        # current nominal settings
        result = conn.execute("SELECT crate, slot, channel, n100, n20, "
            "sequencer FROM current_nominal_settings")
    else:
        result = conn.execute("SELECT DISTINCT ON (crate, slot, channel) "
            "crate, slot, channel, n100, n20, sequencer FROM nominal_settings "
            "WHERE timestamp < (SELECT timestamp FROM run_state WHERE run = %s) "
            "ORDER BY crate, slot, channel, timestamp DESC", (run,))

    if result is None:
        return None

    keys = result.keys()
    rows = result.fetchall()

    channels = {}
    for row in rows:
        crate, slot, channel, n100, n20, sequencer = row
        if crate not in channels:
            channels[crate] = {}
        if slot not in channels[crate]:
            channels[crate][slot] = {}
        channels[crate][slot][channel] = n100, n20, sequencer

    return channels

def get_nominal_settings(crate, slot, channel):
    """
    Returns a dictionary of the current nominal settings for a single channel
    in the detector.
    """
    conn = engine.connect()

    result = conn.execute("SELECT * FROM current_nominal_settings "
        "WHERE crate = %s AND slot = %s AND channel = %s",
        (crate,slot,channel))

    if result is None:
        return None

    keys = result.keys()
    row = result.fetchone()

    return dict(zip(keys,row))

def get_discriminator_threshold(crate, slot):
    """
    Get the current discriminator threshold for a specified crate and card.
    Returns a dictionary of the discriminator threshold and zero threshold.
    """
    conn = engine.connect()

    # Select most recent zdisc with ecalid field
    result = conn.execute("SELECT zero_disc FROM current_zdisc WHERE "
        "crate = %s AND slot = %s", (crate, slot))

    if result is None:
        return None

    keys = result.keys()
    row = result.fetchone()

    if row is None:
        return None

    zthr = dict(zip(keys,row))

    # Get the current discriminator threshold
    result = conn.execute("SELECT vthr FROM current_detector_state WHERE "
        "crate = %s AND slot = %s", (crate, slot))

    if result is None:
        return None

    keys = result.keys()
    row = result.fetchone()

    if row is None:
        result = conn.execute("SELECT vthr FROM detector_state WHERE "
            "crate = %s AND slot = %s ORDER BY run DESC LIMIT 1", (crate, slot))
        keys = result.keys()
        row = result.fetchone()

    vthr = dict(zip(keys,row))

    threshold = zthr.copy()
    threshold.update(vthr)

    result = conn.execute("SELECT vthr FROM fecdoc WHERE crate = %s AND slot = %s "
        "ORDER BY timestamp DESC LIMIT 1", (crate, slot))

    rows = result.fetchone()

    if rows is None:
        threshold['ecal_vthr'] = [0]*32
        return threshold

    threshold['ecal_vthr'] = rows[0]

    return threshold

def get_gtvalid_lengths(crate, slot):
    """
    Get the gtvalid length for a specified crate and card. There are two
    TACs per CMOS chip so there are two GTValid lengths per channel. Returns
    a dictionary of the gtvalids lengths for each TAC
    """
    conn = engine.connect()

    result = conn.execute("SELECT gtvalid0_length, gtvalid1_length FROM gtvalid "
        "WHERE crate = %s AND slot = %s ORDER BY timestamp DESC LIMIT 1", (crate, slot))

    if result is None:
        return None

    keys = result.keys()
    row = result.fetchall()

    if row == []:
        return None

    gtvalid = dict(zip(keys,row[0]))

    return gtvalid

def get_all_thresholds(run):
    """
    Get the discriminator threshold and zero threshold for the entire detector.
    Returns a list of thresholds above zero and some information about channels
    with maxed thresholds.
    """
    # hack to avoid circular imports
    from .detector_state import get_latest_run

    message = ""

    conn = engine.connect()

    zero = [[0 for i in range(16)] for j in range(19)]
    thr = [[0 for i in range(16)] for j in range(19)]
    disc = [9999]*9728

    if run == 0:
        result = conn.execute("SELECT crate, slot, vthr FROM current_detector_state "
                              "ORDER BY crate, slot")
    else:
        result = conn.execute("SELECT crate, slot, vthr FROM detector_state WHERE "
                              "run = %s ORDER BY crate, slot", run)

    rows = result.fetchall()

    if not rows:
        message = "Failure getting vthr information."
        return None, None, None, message

    for crate, slot, vthr in rows:
        thr[crate][slot] = vthr

    if run == 0:
        run = get_latest_run()

    # Select the ZDISC information with the timestamp before the requested
    # VTHR information.
    result = conn.execute("SELECT DISTINCT ON (crate, slot) crate, slot, zero_disc "
                          "FROM zdisc WHERE "
                          "(ecalid <> '')  AND timestamp < (SELECT timestamp FROM "
                          "run_state WHERE run = %s) ORDER BY crate, slot, timestamp "
                          "DESC LIMIT 304", (run,))

    rows = result.fetchall()

    # Result is empty, probably zdisc info didn't exist
    if not rows:
        message = "Failure getting zdisc info, only goes back to run 103216." 
        return None, None, None, message

    for crate, slot, zero_disc in rows:
        zero[crate][slot] = zero_disc

    disc_average = 0
    lower_disc_average = 0
    online_channels = 0
    count_max_thresholds = 0
    crate_average = [0.0]*19
    slot_average = [0.0]*16
    count_channels_crate = [0.0]*19
    count_channels_slot = [0.0]*16

    for crate in range(19):
        for slot in range(16):
            # No Vthr information, slot is missing
            if thr[crate][slot] != 0 and zero[crate][slot] != 0:
                for channel in range(len(thr[crate][slot])):
                    threshold = thr[crate][slot][channel] - zero[crate][slot][channel]
                    lcn = crate*512+slot*32+channel
                    if thr[crate][slot][channel] <= 254:
                        disc[lcn] = int(threshold)
                        disc_average += int(threshold) 
                        # Only count online, non-maxed channels
                        online_channels += 1
                        crate_average[crate] += threshold
                        slot_average[slot] += threshold
                        count_channels_crate[crate] +=1
                        count_channels_slot[slot] += 1
                    else: 
                        count_max_thresholds += 1
    cr_avg = []
    for crate in range(19):
        if count_channels_crate[crate]:
            crate_average[crate] /= count_channels_crate[crate]
            cr_avg.append([crate, crate_average[crate]])
        else:
            cr_avg.append([crate, 0])
    sl_avg = []
    for slot in range(16):
        if count_channels_slot[slot]:
            slot_average[slot] /= count_channels_slot[slot]
            sl_avg.append([slot, slot_average[slot]])
        else:
            sl_avg.append([slot, 0])
 
    cr_range = [max(crate_average), min(crate_average)]
    sl_range = [max(slot_average), min(slot_average)]

    disc_average = round(float(disc_average) / online_channels, 3)

    return disc, disc_average, count_max_thresholds, message, cr_avg, sl_avg, cr_range, sl_range

def get_maxed_thresholds(run):
    """
    Get the crate, card, channels of all discriminator thresholds >= 254.

    Returns a list of the form [(crate, slot, [channels]), ...].
    """
    conn = engine.connect()

    if run == 0:
        result = conn.execute("SELECT crate, slot, vthr FROM current_detector_state "
            "ORDER BY crate, slot")
    else:
        result = conn.execute("SELECT crate, slot, vthr FROM detector_state WHERE "
            "run = %s ORDER BY crate, slot", run)

    rows = result.fetchall()

    maxed = []
    for crate, slot, vthr in rows:
        channels = []
        for j in range(len(vthr)):
            if vthr[j] >= 254:
                channels.append(j)
        maxed.append((crate,slot,channels))

    return maxed

def get_channel_status(crate, slot, channel):
    """
    Returns a dictionary of the channel status for a single channel in the
    detector.
    """
    conn = engine.connect()

    result = conn.execute("SELECT * FROM current_channel_status "
        "WHERE crate = %s AND slot = %s AND channel = %s",
        (crate,slot,channel))

    if result is None:
        return None

    keys = result.keys()
    row = result.fetchone()

    return dict(zip(keys,row))

def get_channel_status_form(crate, slot, channel):
    """
    Returns a channel status form filled in with the current channel status for
    a single channel in the detector.
    """
    return ChannelStatusForm(**get_channel_status(crate, slot, channel))

def upload_channel_status(form):
    """
    Upload a new channel status record in the database.
    """
    conn = psycopg2.connect(dbname=app.config['DB_NAME'],
                            user=app.config['DB_EXPERT_USER'],
                            host=app.config['DB_HOST'],
                            password=form.password.data)
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

    cursor = conn.cursor()
    cursor.execute("INSERT INTO channel_status "
        "(crate, slot, channel, pmt_removed, pmt_reinstalled, low_occupancy, "
        "zero_occupancy, screamer, bad_discriminator, no_n100, no_n20, "
        "no_esum, cable_pulled, bad_cable, resistor_pulled, disable_n100, "
        "disable_n20, high_dropout, bad_base_current, bad_data, "
        "bad_calibration, name, reason, " "info) "
        "VALUES (%(crate)s, %(slot)s, %(channel)s, %(pmt_removed)s, "
        "%(pmt_reinstalled)s, %(low_occupancy)s, %(zero_occupancy)s, "
        "%(screamer)s, %(bad_discriminator)s, %(no_n100)s, %(no_n20)s, "
        "%(no_esum)s, %(cable_pulled)s, %(bad_cable)s, %(resistor_pulled)s, "
        "%(disable_n100)s, %(disable_n20)s, %(high_dropout)s, "
        "%(bad_base_current)s, %(bad_data)s, %(bad_calibration)s, %(name)s, "
        "%(reason)s, %(info)s)", form.data)
