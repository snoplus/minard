import sqlalchemy
from minard import app

engine = sqlalchemy.create_engine('postgresql://%s:%s@%s:%i/%s' %
                                 (app.config['DB_USER'], app.config['DB_PASS'],
                                  app.config['DB_HOST'], app.config['DB_PORT'],
                                  app.config['DB_NAME']))

def get_nhit_monitor_thresholds(limit=100):
    """
    Returns a list of the latest nhit monitor records in the database.
    """
    conn = engine.connect()

    result = conn.execute("SELECT * FROM nhit_monitor_thresholds ORDER BY timestamp DESC LIMIT %s", (limit,))

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

def get_trigger_scan_for_run(run):
    # These names were taken from the trigger_scan source code in daq/utils/trigger_scan
    # Should those names ever change, these names will need to be updated as well.
    names = ['n100hi','n100lo','n100med','n20LB','n20']
    results = []
    for name in names:
        key = "(SELECT key from trigger_scan where timestamp = "\
                "(SELECT max(timestamp) FROM trigger_scan WHERE "\
                "(timestamp < (SELECT timestamp FROM run_state WHERE run = %i)"\
                " AND name='%s')))" % (run,name)
        try:
            results.append(fetch_from_table_with_key("trigger_scan",key))
        except ValueError:
            results.append(False)
    return dict(zip(names,results))
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
    return fetch_from_table_with_key('run_state',run,key_name='run')

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

def translate_ped_delay(coarseDelay_mask,fineDelay_mask):
    MIN_GT_DELAY = 18.35; #Taken from daq/src/mtc.c
    AddelSlope = 0.1; #Taken from daq/src/mtc.c
    coarseDelay = ((~coarseDelay_mask & 0xFF))*10;
    fine_delay = (fineDelay_mask & 0xFF) * AddelSlope;
    return coarseDelay + fine_delay;

def translate_lockout_width(lockout_mask):
    lockout = (~lockout_mask) & 0xFF;
    return lockout*20

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

def translate_prescale(prescale):
    return (~prescale & 0xFFFF)+1

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
        ret['lockout_width'] = translate_lockout_width(mtc['lockout_width'])
        ret['control_reg'] = translate_control_reg(mtc['control_register'])
        ret['prescale'] = translate_prescale(mtc['prescale'])
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
            ret['channel_offsets'] = [x/2**16-1.0 for x in caen['channel_dacs']]
        except TypeError:
            ret['channel_offsets'] = 0

    except Exception as e:
        print "CAEN translation error: %s" % e
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
        ret['counter_mask'] = tubii['counter_mask']
        ret['counter_mode'] = tubii['counter_mode']
        ret['speaker_mask'] = tubii['speaker_mask']
        ret['caen_gain_path'] = tubii['caen_gain_reg']
        ret['caen_channel_select'] = tubii['caen_channel_reg']
        ret['lockout_reg'] = 5*tubii['lockout_reg']
        ret['dgt_reg'] = 2*tubii['dgt_reg']
        ret['dac_reg'] = (10/4096)*tubii['dac_reg'] -5
    except Exception as e:
        print "TUBii translation error: %s" % e
        return False
    return ret

@app.template_filter('all_crates_human_readable')
def all_crates_human_readable(crates):
    if crates is None:
        return False
    ret = {}
    crates =  map(crate_human_readable_filter,crates)
    ret['crates'] = crates
    available_crates = filter(None,crates)
    ret['num_n100_triggers'] = sum(map(lambda x:x['num_n100_triggers'],available_crates))
    ret['num_n20_triggers'] = sum(map(lambda x:x['num_n20_triggers'],available_crates))
    ret['num_sequencers'] = sum(map(lambda x:x['num_sequencers'],available_crates))
    return ret

@app.template_filter('crate_human_readable')
def crate_human_readable_filter(crate):
    if crate is None:
        return False
    fecs = []
    ret = {}
    try:
        for i in range(0,16):
            fecs.append(fec_human_readable_filter(crate[i]))
    except Exception as e:
        print "Crate translation error: %s" % e
        return False
    ret['fecs'] = fecs
    available_fecs = filter(None,fecs)
    ret['num_n100_triggers'] = sum(map(lambda x:x['num_n100_triggers'],available_fecs))
    ret['num_n20_triggers'] = sum(map(lambda x:x['num_n20_triggers'],available_fecs))
    ret['num_sequencers'] = sum(map(lambda x:x['num_sequencers'],available_fecs))
    return ret

def translate_fec_disable_mask(mask):
    return map(lambda x: 0 if ((mask & (1<<x))>0) else 1,range(32))

@app.template_filter('fec_human_readable')
def fec_human_readable_filter(fec):
    if fec is None:
        return False
    ret = {}
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
        print "FEC translation error : %s" % e
        return False
    return ret

# The trigger scan names aren't exactly the same as the MTCA names I used here.
# By happy coincidence the only difference is I use upper case and have a ' '
# between the n100/n20 and the gain. Should ESUM ever be added this will break
def trigger_scan_string_translate(name):
    index = name.rfind('0')
    if(index <0):
        return name
    return (name[:index+1]+" "+name[index+1:]).upper()


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
        print "trigger scan translation error: %s" % e
        return False
    return res
