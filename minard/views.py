from __future__ import division, print_function
from . import app
from flask import render_template, jsonify, request, redirect, url_for, flash, make_response
from itertools import product
import time
from redis import Redis
from os.path import join
import json
import HLDQTools
import RSTools
import requests
from .tools import parseiso, total_seconds
from collections import deque, namedtuple
from .timeseries import get_timeseries, get_interval, get_hash_timeseries
from .timeseries import get_timeseries_field, get_hash_interval
from .timeseries import get_cavity_temp
from .timeseries import get_psup_temp
from math import isnan
import os
import sys
import random
import detector_state
import orca
import nlrat
import nearline_monitor
import nearlinedb
import nearline_settings
import pingcratesdb
import triggerclockjumpsdb
import muonsdb
import redisdb
import cssProc as cssproc
import fiber_position
import occupancy
import channelflagsdb
import dropout
import pmtnoisedb
import gain_monitor
import activity
import scintillator_level
import burst as burst_f
import presn as presn_f
import pca_processing as pcaprocessing_f
from light_level import get_light_level, get_light_level_clean, get_all_light_levels
from shifter_information import get_shifter_information, set_shifter_information, ShifterInfoForm, get_experts, get_supernova_experts
from run_list import golden_run_list
from .polling import polling_runs, polling_info, polling_info_card, polling_check, get_cmos_rate_history, polling_summary, get_most_recent_polling_info, get_vmon, get_base_current_history, get_vmon_history
from .channeldb import ChannelStatusForm, upload_channel_status, get_channels, get_channel_status, get_channel_status_form, get_channel_history, get_pmt_info, get_nominal_settings, get_discriminator_threshold, get_all_thresholds, get_maxed_thresholds, get_gtvalid_lengths, get_pmt_types, pmt_type_description, get_fec_db_history
from .ecaldb import ecal_state, penn_daq_ccc_by_test, get_penn_daq_tests
from .mtca_crate_mapping import MTCACrateMappingForm, OWLCrateMappingForm, upload_mtca_crate_mapping, get_mtca_crate_mapping, get_mtca_crate_mapping_form, mtca_relay_status, get_mtca_retriggers, get_mtca_autoretriggers, RETRIGGER_LOGIC
import re
from .resistor import get_resistors, ResistorValuesForm, get_resistor_values_form, update_resistor_values
from .pedestalsdb import get_pedestals, bad_pedestals, qhs_by_channel
from datetime import datetime, timedelta
from functools import wraps, update_wrapper
from dead_time import get_dead_time, get_dead_time_runs, get_dead_time_run_by_key
from radon_monitor import get_radon_monitor

TRIGGER_NAMES = \
['100L',
 '100M',
 '100H',
 '20',
 '20LB',
 'ESUML',
 'ESUMH',
 'OWLN',
 'OWLEL',
 'OWLEH',
 'PULGT',
 'PRESCL',
 'PED',
 'PONG',
 'SYNC',
 'EXTA',
 'EXT2',
 'EXT3',
 'EXT4',
 'EXT5',
 'EXT6',
 'EXT7',
 'EXT8',
 'SRAW',
 'NCD',
 'SOFGT',
 'MISS']

class Program(object):
    def __init__(self, name, machine=None, link=None, description=None, expire=10, display_log=True):
        self.name = name
        self.machine = machine
        self.link = link
        self.description = description
        self.expire = expire
        self.display_log = display_log

redis = Redis()

PROGRAMS = [#Program('builder','builder1', description="event builder"),
            Program('L2-client','buffer1', description="L2 processor"),
            Program('L2-convert','buffer1',
                    description="zdab -> ROOT conversion"),
            Program('L1-delete','buffer1', description="delete L1 files"),
            Program('mtc','sbc', description="mtc server",
		    display_log=False),
            Program('data','buffer1', description="data stream server",
		    display_log=False),
            Program('xl3','buffer1', description="xl3 server",
		    display_log=False),
            Program('log','minard', description="log server",
		    display_log=False),
            Program('DetectorControl','minard', description="detector control server",
		    display_log=False),
            Program('estop-monitor','sbc', description="estop server",
		    display_log=False),
            Program('tubii','tubii', description="tubii server",
		    display_log=False),
            Program('noel','buffer1', description="noel server",
		    display_log=False)
]

def nocache(view):
    """
    Flask decorator to hopefully prevent Firefox from caching responses which
    are made very often.

    Example:

        @app.route('/foo')
        @nocache
        def foo():
            # do stuff
            return jsonify(*bar)

    Basic idea from https://gist.github.com/arusahni/9434953.

    Required Headers to prevent major browsers from caching content from
    https://stackoverflow.com/questions/49547.
    """
    @wraps(view)
    def no_cache(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers['Last-modified'] = datetime.now()
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    return update_wrapper(no_cache, view)

@app.template_filter('timefmt')
def timefmt(timestamp):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(float(timestamp)))

@app.errorhandler(500)
def internal_error(exception):
    return render_template('500.html'), 500

@app.route('/status')
def status():
    return render_template('status.html', programs=PROGRAMS)

def get_builder_log_warnings(run):
    """
    Returns a list of all the lines in the builder log for a given run which
    were warnings.
    """
    # regular expression matching error messages
    rerr = re.compile('error|warning|jumped|queue head|queue tail|fail|memory|NHIT > 10000|invalid|unknown|missing|collision|unexpected|garbage|sequence|skipped|FIXED|Orphan|Bad data', re.IGNORECASE)

    warnings = []
    with open(os.path.join(app.config["BUILDER_LOG_DIR"], "SNOP_%010i.log" % run)) as f:
        for line in f:
            if rerr.search(line):
                warnings.append(line)
    return warnings

def get_daq_log_warnings(run):
    """
    Returns a list of all the lines in the DAQ log for a given run which were
    warnings.
    """
    warnings = []
    with open(os.path.join(app.config["DAQ_LOG_DIR"], "daq_%08i.log" % run)) as f:
        for line in f:
            # match the log level
            match = re.match('.+? ([.\-*#])', line)

            if match and match.group(1) == '#':
                warnings.append(line)
    return warnings

@app.route('/update-pmtic-resistors', methods=["GET", "POST"])
def update_pmtic_resistors():
    pc = request.args.get("pc", 0, type=int)
    if request.form:
        form = ResistorValuesForm(request.form)
        crate = form.crate.data
        slot = form.slot.data
    else:
        crate = request.args.get("crate", 0, type=int)
        slot = request.args.get("slot", 0, type=int)
        try:
            form = get_resistor_values_form(crate, slot)
        except Exception as e:
            form = ResistorValuesForm(crate=crate, slot=slot)

    if request.method == "POST" and form.validate():
        try:
            update_resistor_values(form)
        except Exception as e:
            flash(str(e), 'danger')
            return render_template('update_pmtic_resistors.html', crate=crate, slot=slot, form=form, pc=pc)
        flash("Successfully submitted", 'success')
        return redirect(url_for('calculate_resistors', crate=form.crate.data, slot=form.slot.data))
    return render_template('update_pmtic_resistors.html', crate=crate, slot=slot, form=form, pc=pc)

@app.route('/calculate-resistors')
def calculate_resistors():
    crate = request.args.get("crate", 0, type=int)
    slot = request.args.get("slot", 0, type=int)
    resistors = get_resistors(crate, slot)
    return render_template('calculate_resistors.html', crate=crate, slot=slot, resistors=resistors)

@app.route('/detector-state-check')
@app.route('/detector-state-check/<int:run>')
def detector_state_check(run=None):
    if run is None:
        run = detector_state.get_run_state(None)['run']

    trig_messages, hv_messages, relay_messages, off_messages, fec_messages, channels = detector_state.get_detector_state_check(run)
    alarms = detector_state.get_alarms(run)

    if alarms is None:
        flash("unable to get alarms for run %i" % run, 'danger')

    if run == 0:
        builder_warnings = None
        warnings = None
    else:
        try:
            builder_warnings = get_builder_log_warnings(run)
        except IOError:
            flash("unable to get builder log for run %i" % run, 'danger')
            builder_warnings = None

        try:
            warnings = get_daq_log_warnings(run)
        except IOError:
            flash("unable to get daq log for run %i" % run, 'danger')
            warnings = None

    return render_template('detector_state_check.html', run=run, trig_messages=trig_messages, hv_messages=hv_messages, fec_messages=fec_messages, off_messages=off_messages, relay_messages=relay_messages, channels=channels, alarms=alarms, warnings=warnings, builder_warnings=builder_warnings)

@app.route('/channel-database')
def channel_database():
    limit = request.args.get("limit", 100, type=int)
    sort_by = request.args.get("sort-by", "timestamp")
    results = get_channels(request.args, limit, sort_by)
    return render_template('channel_database.html', results=results, limit=limit, sort_by=sort_by)

@app.template_filter('channel_status')
def filter_channel_status(row):
    status = []
    if row['pmt_removed']:
        status.append("PMT Removed")
    if row['pmt_reinstalled']:
        status.append("PMT Reinstalled")
    if row['low_occupancy']:
        status.append("Low Occ.")
    if row['zero_occupancy']:
        status.append("Zero Occ.")
    if row['screamer']:
        status.append("Screamer")
    if row['bad_discriminator']:
        status.append("Bad Disc.")
    if row['no_n100']:
        status.append("No N100")
    if row['no_n20']:
        status.append("No N20")
    if row['no_esum']:
        status.append("No ESUM")
    if row['cable_pulled']:
        status.append("Cable pulled")
    if row['bad_cable']:
        status.append("Bad Cable")
    if row['resistor_pulled']:
        status.append("Resistor pulled")
    if row['disable_n100']:
        status.append("Disable N100")
    if row['disable_n20']:
        status.append("Disable N20")
    if row['high_dropout']:
        status.append("High Dropout")
    if row['bad_base_current']:
        status.append("Bad Base Current")
    if row['bad_data']:
        status.append("Bad Data")
    if row['bad_calibration']:
        status.append("Bad Calibration")

    if len(status) == 0:
        return "Perfect!"

    return ", ".join(status)

@app.template_filter('time_from_now')
def time_from_now(dt):
    """
    Returns a human readable string representing the time duration between `dt`
    and now. The output was copied from the moment javascript library.

    See https://momentjs.com/docs/#/displaying/fromnow/
    """
    delta = total_seconds(datetime.now() - dt)

    if delta < 45:
        return "a few seconds ago"
    elif delta < 90:
        return "a minute ago"
    elif delta <= 44*60:
        return "%i minutes ago" % int(round(delta/60))
    elif delta <= 89*60:
        return "an hour ago"
    elif delta <= 21*3600:
        return "%i hours ago" % int(round(delta/3600))
    elif delta <= 35*3600:
        return "a day ago"
    elif delta <= 25*24*3600:
        return "%i days ago" % int(round(delta/(24*3600)))
    elif delta <= 45*24*3600:
        return "a month ago"
    elif delta <= 319*24*3600:
        return "%i months ago" % int(round(delta/(30*24*3600)))
    elif delta <= 547*24*3600:
        return "a year ago"
    else:
        return "%i years ago" % int(round(delta/(365.25*24*3600)))

@app.template_filter('format_cmos_rate')
def format_cmos_rate(rate):
    if rate < 1000:
        return '%i' % int(rate)
    elif rate < 10000:
        return '%.1fk' % (rate/1000)
    elif rate < 1e6:
        return '%ik' % (rate//1000)
    else:
        return '%iM' % (rate//1e6)

@app.route('/channel-status')
def channel_status():
    crate = request.args.get("crate", 0, type=int)
    slot = request.args.get("slot", 0, type=int)
    channel = request.args.get("channel", 0, type=int)
    results = get_channel_history(crate, slot, channel)
    pmt_info = get_pmt_info(crate, slot, channel)
    nominal_settings = get_nominal_settings(crate, slot, channel)
    polling_info = get_most_recent_polling_info(crate, slot, channel)
    discriminator_threshold = get_discriminator_threshold(crate, slot)
    gtvalid_lengths = get_gtvalid_lengths(crate, slot)
    fec_db_history = get_fec_db_history(crate, slot, channel)
    vmon, bad_vmon = get_vmon(crate, slot)
    test_failed = get_penn_daq_tests(crate, slot, channel)
    qhs, qhl, qlx = get_pedestals(crate, slot, channel)
    return render_template('channel_status.html', crate=crate, slot=slot, channel=channel, results=results, pmt_info=pmt_info, nominal_settings=nominal_settings, polling_info=polling_info, discriminator_threshold=discriminator_threshold, gtvalid_lengths=gtvalid_lengths, fec_db_history=fec_db_history, vmon=vmon, bad_vmon=bad_vmon, qhs=qhs, qhl=qhl, qlx=qlx, test_failed=test_failed)

@app.route('/vmon_history')
def vmon_history():
    crate = request.args.get("crate", 0, type=int)
    slot = request.args.get("slot", 0, type=int)
    keys, data = get_vmon_history(crate, slot)

    return render_template('vmon_history.html', crate=crate, slot=slot, data=data, keys=keys)

@app.route('/ecal-status')
def ecal_status():
    crate = request.args.get("crate", 0, type=int)
    slot = request.args.get("slot", 0, type=int)
    channel = request.args.get("channel", 0, type=int)
    test = request.args.get("test", "All", type=str)
    crate2 = request.args.get("crate2", -1, type=int)
    slot2 = request.args.get("slot2", -1, type=int)
    channel2 = request.args.get("channel2", -1, type=int)
    ecal_data = ecal_state(crate, slot, channel)
    ccc = penn_daq_ccc_by_test(test, crate2, slot2, channel2)
    return render_template('ecal_status.html', crate=crate, slot=slot, channel=channel, crate2=crate2, slot2=slot2, channel2=channel2, test=test, ecal_data=ecal_data, ccc=ccc)

@app.route('/update-mtca-crate-mapping', methods=["GET", "POST"])
def update_mtca_crate_mapping():

    # Get the retrigger information
    retriggers = get_mtca_retriggers()[0]
    retrigger_status = {}
    for key in retriggers:
        if key == "key" or key == "timestamp" or \
           key == 'run_begin' or key == 'run_end': continue
        if retriggers[key] <= 3:
            status = RETRIGGER_LOGIC[retriggers[key]]
        else:
            status = "Unknown retrigger logic"
        retrigger_status[str(key).upper()] = status

    # Get the retrigger information
    autoretriggers = get_mtca_autoretriggers()[0]
    autoretrigger_status = {}
    for key in autoretriggers:
        if key == "key" or key == "timestamp" or \
           key == 'run_begin' or key == 'run_end': continue
        autoretrigger_status[str(key).upper()] = autoretriggers[key]

    relay_status = None
    if request.form:
        if int(request.form['mtca']) < 4:
            form = MTCACrateMappingForm(request.form)
        else:
            form = OWLCrateMappingForm(request.form)
        mtca = form.mtca.data
    else:
        mtca = request.args.get("mtca", 0, type=int)
        relay_status = mtca_relay_status(mtca)
        form = get_mtca_crate_mapping_form(mtca)

    if request.method == "POST" and form.validate():
        try:
            upload_mtca_crate_mapping(form)
        except Exception as e:
            flash(str(e), 'danger')
            return render_template('update_mtca_crate_mapping.html', form=form)
        flash("Successfully submitted", 'success')
        return redirect(url_for('update_mtca_crate_mapping', mtca=form.mtca.data))
    return render_template('update_mtca_crate_mapping.html', form=form, relay_status=relay_status, retriggers=retrigger_status, autoretriggers=autoretrigger_status)

@app.route('/update-channel-status', methods=["GET", "POST"])
def update_channel_status():
    if request.form:
        form = ChannelStatusForm(request.form)
        crate = form.crate.data
        slot = form.slot.data
        channel = form.channel.data
    else:
        crate = request.args.get("crate", 0, type=int)
        slot = request.args.get("slot", 0, type=int)
        channel = request.args.get("channel", 0, type=int)
        try:
            form = get_channel_status_form(crate, slot, channel)
            # don't add the name, reason, or info fields if they just go to the page.
            form.name.data = None
            form.reason.data = None
            form.info.data = None
        except Exception as e:
            form = ChannelStatusForm(crate=crate, slot=slot, channel=channel)

    channel_status = get_channel_status(crate, slot, channel)

    if request.method == "POST" and form.validate():
        try:
            upload_channel_status(form)
        except Exception as e:
            flash(str(e), 'danger')
            return render_template('update_channel_status.html', form=form, status=channel_status)
        flash("Successfully submitted", 'success')
        return redirect(url_for('channel_status', crate=form.crate.data, slot=form.slot.data, channel=form.channel.data))
    return render_template('update_channel_status.html', form=form, status=channel_status)

@app.route('/ecal_state_diff')
def ecal_state_diff():
    run = request.args.get("run", 0, type=int)
    crate = request.args.get("crate", -1, type=int)
    slot = request.args.get("slot", -1, type=int)

    vthr, mbid, dbid, vbal0, vbal1, isetm, rmp = detector_state.compare_ecal_to_detector_state(run, crate, slot)

    return render_template('ecal_state_diff.html', run=run, vthr=vthr, mbid=mbid, dbid=dbid, vbal0=vbal0, vbal1=vbal1, isetm=isetm, rmp=rmp)

@app.route('/detector-state-diff')
def detector_state_diff():
    run1 = request.args.get("run1", 100000, type=int)
    run2 = request.args.get("run2", 0, type=int)

    if run1 == -1:
        run1 = detector_state.get_latest_run()

    if run2 == -1:
        run2 = detector_state.get_latest_run()

    try:
        run_state1 = detector_state.get_run_state(run1)
        run_state2 = detector_state.get_run_state(run1)

        mtc_state1 = detector_state.get_mtc_state_for_run(run1)
        mtc_state2 = detector_state.get_mtc_state_for_run(run2)

        tubii_state1 = detector_state.get_tubii_state_for_run(run1)
        tubii_state2 = detector_state.get_tubii_state_for_run(run2)

        caen_state1 = detector_state.get_caen_state_for_run(run1)
        caen_state2 = detector_state.get_caen_state_for_run(run2)

        detector_state1 = detector_state.get_detector_state(run1)
        detector_state2 = detector_state.get_detector_state(run2)
    except Exception as e:
        flash(str(e), 'danger')

    return render_template('detector_state_diff.html',
                           run1=run1,
                           run2=run2,
                           run_state1=run_state1,
                           run_state2=run_state2,
                           mtc_state1=mtc_state1,
                           mtc_state2=mtc_state2,
                           tubii_state1=tubii_state1,
                           tubii_state2=tubii_state2,
                           caen_state1=caen_state1,
                           caen_state2=caen_state2,
                           detector_state1=detector_state1,
                           detector_state2=detector_state2)

@app.route('/state')
@app.route('/state/<int:run>')
def state(run=None):
    try:
        run_state = detector_state.get_run_state(run)
        run = run_state['run']
        # Have to put these in ISO format so flask doesn't mangle it later
        run_state['timestamp'] = run_state['timestamp'].isoformat()
        # end_timestamp isn't that important. If it's not there, it's ignored
        if(run_state['end_timestamp']):
            run_state['end_timestamp'] = run_state['end_timestamp'].isoformat()
    except Exception as e:
        return render_template('state.html', err=str(e))

    detector_control_state = None
    if run_state['detector_control'] is not None:
        detector_control_state = detector_state.get_detector_control_state(run_state['detector_control'])

    mtc_state = None
    if run_state['mtc'] is not None:
        mtc_state = detector_state.get_mtc_state(run_state['mtc'])

    caen_state = None
    if run_state['caen'] is not None:
        caen_state = detector_state.get_caen_state(run_state['caen'])

    tubii_state = None
    if run_state['tubii'] is not None:
        tubii_state = detector_state.get_tubii_state(run_state['tubii'])

    crates_state = detector_state.get_detector_state(run)

    if not crates_state:
        crates_state = None

    trigger_scan = None
    if run_state['timestamp'] is not None:
        trigger_scan = detector_state.get_trigger_scan_for_run(run)

    hv_params = detector_state.get_hv_nominals()

    return render_template('state.html', run=run,
                           run_state=run_state,
                           detector_control_state=detector_control_state,
                           mtc_state=mtc_state,
                           caen_state=caen_state,
                           tubii_state=tubii_state,
                           crates_state=crates_state,
                           trigger_scan=trigger_scan,
                           hv_params=hv_params,
                           err=None)

@app.route('/l2')
def l2():
    step = request.args.get('step',3,type=int)
    height = request.args.get('height',20,type=int)
    if not request.args.get('step') or not request.args.get('height'):
        return redirect(url_for('l2',step=step,height=height,_external=True))
    return render_template('l2.html',step=step,height=height)

@app.route('/burst')
def burst():
    offset = request.args.get('offset',type=int)
    limit = request.args.get('limit',default=25,type=int)
    search = request.args.get('search',type=str)
    if search is not None:
        start = request.args.get('start')
        end = request.args.get('end')
        if offset == None:
            return redirect("burst?limit=%i&offset=0&search=%s&start=%s&end=%s" % (limit, search, start, end))
        data, total, offset, limit = burst_f.load_bursts_search(search, start, end, offset, limit)
        return render_template( 'burst.html', data=data, total=total, offset=offset, limit=limit, search=search, start=start, end=end)
    if offset == None:
        return redirect("burst?limit=25&offset=0")
    data, total, offset, limit = burst_f.load_burst_runs(offset, limit)
    return render_template( 'burst.html', data=data, total=total, offset=offset, limit=limit )

@app.route('/l3')
def l3():
    step = request.args.get('step',3,type=int)
    height = request.args.get('height',20,type=int)
    data = burst_f.burst_get_cuts()
    if not request.args.get('step') or not request.args.get('height'):
        return redirect(url_for('l3',step=step,height=height,_external=True,data=data))
    return render_template('l3.html',step=step,height=height,data=data)

@app.route('/burst_l3')
def burst_l3():
    offset = request.args.get('offset',type=int)
    limit = request.args.get('limit',default=25,type=int)
    search = request.args.get('search',type=str)
    if search is not None:
        start = request.args.get('start')
        end = request.args.get('end')
        if offset == None:
            return redirect("burst_l3?limit=%i&offset=0&search=%s&start=%s&end=%s" % (limit, search, start, end))
        data, total, offset, limit = burst_f.load_bursts_search(search, start, end, offset, limit, 3)
        return render_template( 'burst_l3.html', data=data, total=total, offset=offset, limit=limit, search=search, start=start, end=end)
    if offset == None:
        return redirect("burst_l3?limit=25&offset=0")
    data, total, offset, limit = burst_f.load_burst_runs(offset, limit, 3)
    return render_template( 'burst_l3.html', data=data, total=total, offset=offset, limit=limit )


@app.route('/presn')
def presn():
    offset = request.args.get('offset',type=int)
    limit = request.args.get('limit',default=25,type=int)
    search = request.args.get('search',type=str)
    if search is not None:
        start = request.args.get('start')
        end = request.args.get('end')
        if offset == None:
            return redirect("presn?limit=%i&offset=0&search=%s&start=%s&end=%s" % (limit, search, start, end))
        data, total, offset, limit = presn_f.load_presn_search(search, start, end, offset, limit)
        return render_template( 'presn.html', data=data, total=total, offset=offset, limit=limit, search=search, start=start, end=end)
    if offset == None:
        return redirect("presn?limit=25&offset=0")
    data, total, offset, limit = presn_f.load_presn_runs(offset, limit)
    return render_template( 'presn.html', data=data, total=total, offset=offset, limit=limit )


@app.route('/orca-session-logs')
def orca_session_logs():
    limit = request.args.get("limit", 10, type=int)
    offset = request.args.get("offset", 0, type=int)
    if offset < 0:
        offset = 0
    results = orca.get_orca_session_logs(limit, offset)

    if results is None:
	return render_template('orca_session_logs.html', error="No orca session logs.")

    return render_template('orca_session_logs.html', results=results, limit=limit, offset=offset)

@app.route('/nhit-monitor-thresholds')
def nhit_monitor_thresholds():
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)
    results = detector_state.get_nhit_monitor_thresholds(limit, offset)

    if results is None:
	return render_template('nhit_monitor_thresholds.html', error="No nhit monitor records.")

    return render_template('nhit_monitor_thresholds.html', results=results, limit=limit, offset=offset)

@app.route('/nhit-monitor/<int:key>')
def nhit_monitor(key):
    results = detector_state.get_nhit_monitor(key)

    if results is None:
	return render_template('nhit_monitor.html', error="No nhit monitor record with key %i." % key)

    return render_template('nhit_monitor.html', results=results)

@app.route('/nhit-monitor-thresholds-nearline')
def nhit_monitor_thresholds_nearline():
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)
    sort_by = request.args.get("sort_by", "run")
    run_range_low = request.args.get("run_range_low", 0, type=int)
    run_range_high = request.args.get("run_range_high", 0, type=int)
    results = detector_state.get_nhit_monitor_thresholds_nearline(limit, offset, sort_by, run_range_low, run_range_high)

    if results is None:
	return render_template('nhit_monitor_thresholds_nearline.html', error="No nhit monitor records.")

    return render_template('nhit_monitor_thresholds_nearline.html', results=results, limit=limit, offset=offset, sort_by=sort_by, run_range_low=run_range_low, run_range_high=run_range_high)

@app.route('/nhit-monitor-nearline/<int:key>')
def nhit_monitor_nearline(key):
    results = detector_state.get_nhit_monitor_nearline(key)

    if results is None:
	return render_template('nhit_monitor_nearline.html', error="No nhit monitor record with key %i." % key)

    return render_template('nhit_monitor_nearline.html', results=results)

@app.route('/trigger')
def trigger():
    results = detector_state.get_latest_trigger_scans()

    if results is None:
	return render_template('trigger.html', error="No trigger scans.")

    return render_template('trigger.html', results=results)

@app.route('/nearline')
@app.route('/nearline/<int:run>')
def nearline(run=None):
    if run is None:
        run = nearlinedb.current_run()

    reprocessed = nearlinedb.reprocessed_run(run)

    programs = nearlinedb.get_nearline_status(run)

    return render_template('nearline.html', run=run, programs=programs, reprocessed=reprocessed)

@app.route('/nearline_failures')
def nearline_failures():
    jobs = request.args.get("jobs", "All", type=str)
    limit = request.args.get("limit", 100, type=int)
    runtype = request.args.get("runtype", -1, type=int)
    run_range_low = request.args.get("run_range_low", 0, type=int)
    run_range_high = request.args.get("run_range_high", 0, type=int)
    run = nearlinedb.current_run()

    # Nearline job types and ways in which the jobs fail
    jobtypes = nearlinedb.job_types()
    runTypes = nlrat.RUN_TYPES

    # List of jobs considered "critical" for processing and nearline
    criticalJobs = nearline_settings.criticalJobs

    failure_runs, failure_jobs = nearlinedb.get_failed_runs(run - limit, run_range_low, run_range_high)

    # Allows sorting by run type
    failure_runs_with_type = []
    if runtype == -1:
        selectedType = "All"
        failure_runs_with_type = failure_runs
    else:
        selectedType = runTypes[runtype]

        if not run_range_high:
            run_list = detector_state.get_runs_with_run_type(run - limit, (1<<runtype))
        else:
            run_list = detector_state.get_runs_with_run_type(run_range_low, (1<<runtype), run_range_high)

        # Apply the run type to the failure list
        for run in failure_runs:
            if run in run_list:
                failure_runs_with_type.append(run)

    return render_template('nearline_failures.html', run=run, failure_runs=failure_runs_with_type, failure_jobs=failure_jobs, jobs=jobs, jobtypes=jobtypes, criticalJobs=criticalJobs, limit=limit, runTypes=runTypes, selectedType=selectedType, runtype=runtype, run_range_low=run_range_low, run_range_high=run_range_high)

@app.route('/get_l2')
def get_l2():
    name = request.args.get('name')

    try:
        files, times = zip(*redis.zrange('l2:%s' % name, 0, -1, withscores=True))
    except ValueError:
        # no files
        files = []
        times = []

    return jsonify(files=files,times=times)

@app.route('/get_l3')
def get_l3():
    name = request.args.get('name')

    try:
        files, times = zip(*redis.zrange('l3:%s' % name, 0, -1, withscores=True))
    except ValueError:
        # no files
        files = []
        times = []

    return jsonify(files=files,times=times)

@app.route('/get_SH')
def get_SH():
    try:
        nhit3 = redis.get('l2:nhit3')
        nhit5 = redis.get('l2:nhit5')
        nhit7 = redis.get('l2:nhit7')
        nhit10 = redis.get('l2:nhit10')
        window = redis.get('l2:window')
        xwindow = redis.get('l2:xwindow')
        ywindow = redis.get('l2:ywindow')
        ext = redis.get('l2:extwindow')
        high = redis.get('l2:highnhit')
        highEvs = redis.get('l2:highEvs')
        highSurv = redis.get('l2:highsurv')
        ibdNHitMeV = redis.get('l2:ibdnhitmev')
        ibdFirstE = redis.get('l2:ibdfirste')
        ibdTimeLow = redis.get('l2:ibdtimelow')
        ibdTimeHigh = redis.get('l2:ibdtimehigh')
        ibdCount = redis.get('l2:ibdcount')
        ibdWindow = redis.get('l2:ibdwindow')
        ibdCoinc = redis.get('l2:ibdcoinc')
        ibdExt = redis.get('l2:ibdext')
        settings = [nhit3,nhit5,nhit7,nhit10,window,xwindow,ywindow,ext,high,highEvs,highSurv,ibdNHitMeV,ibdFirstE,ibdTimeLow,ibdTimeHigh,ibdCount,ibdWindow,ibdCoinc,ibdExt]
    except ValueError:
        # no files
        settings = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
    return jsonify(settings=settings)

@app.route('/graph')
def graph():
    name = request.args.get('name')
    start = request.args.get('start')
    stop = request.args.get('stop')
    step = request.args.get('step',1,type=int)
    return render_template('graph.html',name=name,start=start,stop=stop,step=step)

@app.route('/get_status')
@nocache
def get_status():
    if 'name' not in request.args:
        return 'must specify name', 400

    name = request.args['name']

    up = redis.get('uptime:{name}'.format(name=name))

    if up is None:
        uptime = None
    else:
        uptime = int(time.time()) - int(up)

    return jsonify(status=redis.get('heartbeat:{name}'.format(name=name)),uptime=uptime)

@app.route('/view_log')
def view_log():
    name = request.args.get('name', '???')
    return render_template('view_log.html',name=name)

@app.route('/log', methods=['POST'])
def log():
    """Forward a POST request to the log server at port 8081."""
    import requests

    resp = requests.post('http://127.0.0.1:8081', headers=request.headers, data=request.form)
    return resp.content, resp.status_code, resp.headers.items()

@app.route('/tail')
def tail():
    name = request.args.get('name', None)

    if name is None:
        return 'must specify name', 400

    seek = request.args.get('seek', None, type=int)

    filename = join('/var/log/snoplus', name + '.log')

    try:
        f = open(filename)
    except IOError:
        return "couldn't find log file {filename}".format(filename=filename), 400

    if seek is None:
        # return last 100 lines
        lines = deque(f, maxlen=100)
    else:
        pos = f.tell()
        f.seek(0,2)
        end = f.tell()
        f.seek(pos)

        if seek > end:
            # log file rolled over
            try:
                prev_logfile = open(filename + '.1')
                prev_logfile.seek(seek)
                # add previous log file lines
                lines = prev_logfile.readlines()
            except IOError:
                return 'seek > log file length', 400

            # add new lines
            lines.extend(f.readlines())
        else:
            # seek to last position and readlines
            f.seek(seek)
            lines = f.readlines()

    lines = [line.decode('unicode_escape') for line in lines]

    return jsonify(seek=f.tell(), lines=lines)

@app.route('/')
def index():
    return redirect(url_for('snostream'))

@app.route('/docs/')
@app.route('/docs/<filename>')
@app.route('/docs/<dir>/<filename>')
@app.route('/docs/<dir>/<subdir>/<filename>')
def docs(dir='', subdir='', filename='index.html'):
    path = join('docs', dir, subdir, filename)
    return app.send_static_file(path)

@app.route('/cavity-temp')
def cavity_temp():
    if len(request.args) == 0:
        return redirect(url_for('cavity_temp',step=867,height=20,_external=True))
    step = request.args.get('step',1,type=int)
    height = request.args.get('height',40,type=int)
    return render_template('cavity_temp.html',step=step,height=height)

@app.route('/psup-temp')
def psup_temp():
    if len(request.args) == 0:
        return redirect(url_for('psup_temp',step=867,height=20,_external=True))
    step = request.args.get('step', 1, type=int)
    height = request.args.get('height', 40, type=int)
    return render_template('psup_temp.html', step=step, height=height)


@app.route('/remote-network-monitor')
def remote_network_monitor():
    if len(request.args) == 0:
        return redirect(url_for('remote_network_monitor',step=4,height=20,_external=True))
    step = request.args.get('step',1,type=int)
    height = request.args.get('height',40,type=int)
    return render_template('remote-network-monitor.html',step=step,height=height)

@app.route('/snostream')
def snostream():
    if len(request.args) == 0:
        return redirect(url_for('snostream',step=1,height=20,_external=True))
    step = request.args.get('step',1,type=int)
    height = request.args.get('height',40,type=int)
    return render_template('snostream.html',step=step,height=height)

@app.route('/nhit')
def nhit():
    if not request.args.get("name"):
        return redirect(url_for('nhit', name='all'))
    return render_template('nhit.html',name=request.args.get("name","all"))

@app.route('/rat')
def rathome():
    return render_template('rathome.html', runs=nlrat.available_runs())

@app.route('/rat/<int:run>')
def ratrun(run = 0):
    return render_template("ratrun.html", run=nlrat.Run(run), error= not nlrat.hists_available(run))

@app.route('/l2_filter')
def l2_filter():
    if not request.args.get('step'):
        return redirect(url_for('l2_filter',step=1,height=20,_external=True))
    step = request.args.get('step',1,type=int)
    height = request.args.get('height',40,type=int)
    return render_template('l2_filter.html', step=step, height=height)

@app.route('/detector')
def detector():
    return render_template('detector.html')

@app.route('/check_rates')
def check_rates():
    cmos_runs, base_runs = polling_runs()
    return render_template('check_rates.html', cmos_runs=cmos_runs, base_runs=base_runs)

@app.route('/check_rates_histogram')
def check_rates_histogram():
    run = request.args.get('run', 0, type=int)
    crate = request.args.get('crate', 0)
    cmos_runs, base_runs = polling_runs()

    if crate != "All":
        values = polling_info_card('cmos', run, crate)
    else:
        values = polling_info('cmos', run)
    return render_template('check_rates_histogram.html', values=values, cmos_runs=cmos_runs)

@app.route('/check_rates_summary')
def check_rates_summary():
    run = request.args.get('run',0,type=int)
    cmos_runs, base_runs = polling_runs()
    crate_average, crun, brun, messages = polling_summary(run)

    return render_template('check_rates_summary.html', run=run, crun=crun, brun=brun, cmos_runs=cmos_runs, base_runs=base_runs,crate_average=crate_average, messages=messages)

@app.route('/discriminator_info')
def discriminator_info():
    run_default = detector_state.get_latest_run()
    run1 = request.args.get('run1', run_default, type=int)
    run2 = request.args.get('run2', 0, type=int)

    values1, average1, nmax1, message1, crateavg1, slotavg1, crrange1, slrange1 = get_all_thresholds(run1)
    values2, average2, nmax2, message2, crateavg2, slotavg2, crrange2, slrange2 = get_all_thresholds(run2)
    return render_template('discriminator_info.html', run1=run1, run2=run2, values1=values1, average1=average1, nmax1=nmax1, values2=values2, average2=average2, nmax2=nmax2, message1=message1, message2=message2, crateavg1=crateavg1, slotavg1=slotavg1, crateavg2=crateavg2, slotavg2=slotavg2, crrange1=crrange1, slrange1=slrange1, crrange2=crrange2, slrange2=slrange2)

@app.route('/max_thresholds/<run_number>')
def max_thresholds(run_number):

    maxed = get_maxed_thresholds(run_number)
    return render_template('max_thresholds.html', run_number=run_number, maxed=maxed)

@app.route('/pedestals')
def pedestals():
    crate = request.args.get("crate", 0, type=int)
    slot = request.args.get("slot", -1, type=int)
    channel = request.args.get("channel", -1, type=int)
    cell = request.args.get("cell", -1, type=int)
    charge = request.args.get("charge", "qhs_avg", type=str)
    qmin = request.args.get("qmin", 300, type=int)
    qmax = request.args.get("qmax", 2000, type=int)
    limit = request.args.get("limit", 50, type=int)
    qhs = qhs_by_channel(crate, slot, channel, cell)
    bad_ped = bad_pedestals(crate, slot, channel, cell, charge, qmax, qmin, limit)
    return render_template('pedestals.html', crate=crate, slot=slot, channel=channel, cell=cell, qhs=qhs, bad_ped=bad_ped, qmin=qmin, qmax=qmax, charge=charge, limit=limit)

@app.route('/cmos_rates_check')
def cmos_rates_check():
    high_rate = request.args.get('high_rate',20000.0,type=float)
    low_rate = request.args.get('low_rate',50.0,type=float)
    pct_change = request.args.get('pct_change',200.0,type=float)

    cmos_changes, cmos_high_rates, cmos_low_rates, run_number = \
        polling_check(high_rate, low_rate, pct_change)

    return render_template('cmos_rates_check.html', cmos_changes=cmos_changes, cmos_high_rates=cmos_high_rates, cmos_low_rates=cmos_low_rates, high_rate=high_rate, low_rate=low_rate, run_number=run_number, pct_change=pct_change)

def convert_timestamp(data):

    # Convert datetime objects to strings
    for i in range(len(data)):
        data[i]['timestamp'] = data[i]['timestamp'].isoformat()

    return data

@app.route('/polling_history')
def polling_history():
    crate = request.args.get('crate',0,type=int)
    slot = request.args.get('slot',0,type=int)
    channel = request.args.get('channel',0,type=int)
    # Run when we started keeping polling data
    starting_run = request.args.get('starting_run',0,type=int)
    ending_run = request.args.get('ending_run',0,type=int)
    if ending_run == 0:
        ending_run = detector_state.get_latest_run() + 1
    if starting_run == 0:
        starting_run = ending_run - 1000

    cdata = get_cmos_rate_history(crate, slot, channel, starting_run, ending_run)
    cdata = convert_timestamp(cdata)

    bdata = get_base_current_history(crate, slot, channel, starting_run, ending_run)
    bdata = convert_timestamp(bdata)

    return render_template('polling_history.html', crate=crate, slot=slot, channel=channel, cdata=cdata, bdata=bdata, starting_run=starting_run, ending_run=ending_run)

@app.route('/dead_time_runs')
def dead_time_runs():

    data = get_dead_time_runs()

    return render_template('dead_time_runs.html', data=data)

@app.route('/dead_time')
def dead_time():

    key = request.args.get('key',0,type=int)

    dead_time_data = get_dead_time(key)
    run_data = get_dead_time_run_by_key(key)

    return render_template('dead_time.html', ddata=dead_time_data, rdata=run_data)

@app.route('/daq')
def daq():
    return render_template('daq.html')

@app.route('/alarms')
def alarms():
    return render_template('alarms.html')

CHANNELS = [crate << 9 | card << 5 | channel \
            for crate, card, channel in product(range(20),range(16),range(32))]

OWL_TUBES = [2032, 2033, 2034, 2035, 2036, 2037, 2038, 2039, 2040, 2041, 2042, 2043, 2044, 2045, 2046, 2047, 7152, 7153, 7154, 7155, 7156, 7157, 7158, 7159, 7160, 7161, 7162, 7163, 7164, 7165, 7166, 7167, 9712, 9713, 9714, 9715, 9716, 9717, 9718, 9719, 9720, 9721, 9722, 9723, 9724, 9725, 9726, 9727]

@app.route('/query_occupancy')
@nocache
def query_occupancy():
    trigger_type = request.args.get('type',0,type=int)
    run = request.args.get('run',0,type=int)

    values = occupancy.occupancy_by_trigger(trigger_type, run, False)

    return jsonify(values=values)

@app.route('/query_polling')
@nocache
def query_polling():
    polling_type = request.args.get('type','cmos',type=str)
    run = request.args.get('run',0,type=int)

    values = polling_info(polling_type, run)
    return jsonify(values=values)

@app.route('/query_polling_crate')
@nocache
def query_polling_crate():
    polling_type = request.args.get('type','cmos',type=str)
    run = request.args.get('run',0,type=int)
    crate = request.args.get('crate',0,type=int)

    values = polling_info_card(polling_type, run, crate)
    return jsonify(values=values)

@app.route('/query')
@nocache
def query():
    name = request.args.get('name','',type=str)

    if name == 'dispatcher':
        return jsonify(name=redis.get('dispatcher'))

    if 'nhit' in name:
        seconds = request.args.get('seconds',type=int)

        now = int(time.time())

        p = redis.pipeline()
        for i in range(seconds):
            p.lrange('ts:1:{ts}:{name}'.format(ts=now-i,name=name),0,-1)
        nhit = map(int,sum(p.execute(),[]))
        return jsonify(value=nhit)

    if name in ('occupancy','cmos','base'):
        now = int(time.time())
        step = request.args.get('step',60,type=int)

        interval = get_hash_interval(step)

        i, remainder = divmod(now, interval)

        def div(a,b):
            if a is None or b is None:
                return None
            return float(a)/float(b)

        if remainder < interval//2:
            # haven't accumulated enough data for this window
            # so just return the last time block
            if redis.ttl('ts:%i:%i:%s:lock' % (interval,i-1,name)) > 0:
                # if ttl for lock exists, it means the values for the last
                # interval were already computed
                values = redis.hmget('ts:%i:%i:%s' % (interval, i-1, name),CHANNELS)
                return jsonify(values=values)
            else:
                i -= 1

        if name in ('cmos', 'base'):
            # grab latest sum of values and divide by the number
            # of values to get average over that window
            sum_ = redis.hmget('ts:%i:%i:%s:sum' % (interval,i,name),CHANNELS)
            len_ = redis.hmget('ts:%i:%i:%s:len' % (interval,i,name),CHANNELS)

            values = map(div,sum_,len_)
        else:
            hits = redis.hmget('ts:%i:%i:occupancy:hits' % (interval,i), CHANNELS)
            count = int(redis.get('ts:%i:%i:occupancy:count' % (interval,i)))
            if count > 0:
                values = [int(n)/count if n is not None else None for n in hits]
            else:
                values = [None]*len(CHANNELS)

        return jsonify(values=values)

@app.route('/get_alarm')
@nocache
def get_alarm():
    try:
        count = int(redis.get('alarms:count'))
    except TypeError:
        return jsonify(alarms=[],latest=-1)

    if 'start' in request.args:
        start = request.args.get('start',type=int)

        if start < 0:
            start = max(0,count + start)
    else:
        start = max(count-100,0)

    alarms = []
    for i in range(start,count):
        value = redis.get('alarms:{0:d}'.format(i))

        if value:
            alarms.append(json.loads(value))

    return jsonify(alarms=alarms,latest=count-1)

@app.route('/owl_tubes')
@nocache
def owl_tubes():
    """Returns the time series for the sum of all upward facing OWL tubes."""
    name = request.args['name']
    start = request.args.get('start', type=parseiso)
    stop = request.args.get('stop', type=parseiso)
    now_client = request.args.get('now', type=parseiso)
    step = request.args.get('step', type=int)
    method = request.args.get('method', 'avg')

    now = int(time.time())

    # adjust for clock skew
    dt = now_client - now
    start -= dt
    stop -= dt

    start = int(start)
    stop = int(stop)
    step = int(step)

    values = []
    for i, id in enumerate(OWL_TUBES):
        crate, card, channel = id >> 9, (id >> 5) & 0xf, id & 0x1f
        values.append(get_hash_timeseries(name,start,stop,step,crate,card,channel,method))

    # transpose time series from (channel, index) -> (index, channel)
    values = zip(*values)

    # filter None values in sub lists
    values = map(lambda x: filter(lambda x: x is not None, x), values)

    # convert to floats
    values = map(lambda x: map(float, x), values)

    if method == 'max':
	# calculate max value in each time bin.
        values = map(lambda x: max(x) if len(x) else None, values)
    else:
	# calculate mean value in each time bin
        values = map(lambda x: sum(x)/len(x) if len(x) else None, values)

    return jsonify(values=values)

@app.route('/metric_hash')
@nocache
def metric_hash():
    """Returns the time series for argument `names` as a JSON list."""
    name = request.args['name']
    start = request.args.get('start', type=parseiso)
    stop = request.args.get('stop', type=parseiso)
    now_client = request.args.get('now', type=parseiso)
    step = request.args.get('step', type=int)
    crate = request.args.get('crate', type=int)
    card = request.args.get('card', None, type=int)
    channel = request.args.get('channel', None, type=int)
    method = request.args.get('method', 'avg')

    now = int(time.time())

    # adjust for clock skew
    dt = now_client - now
    start -= dt
    stop -= dt

    start = int(start)
    stop = int(stop)
    step = int(step)

    values = get_hash_timeseries(name,start,stop,step,crate,card,channel,method)
    return jsonify(values=values)

def get_metric(expr, start, stop, step):
    if expr.split('-')[0] == 'temp':
        sensor = int(expr.split('-')[1])
        values = get_cavity_temp(sensor, start, stop, step)
    elif expr.split('-')[0] == 'psuptemp':
        sensor = int(expr.split('-')[1])
        values = get_psup_temp(sensor, start, stop, step)
    elif expr in ('L2:gtid', 'L2:run'):
        values = get_timeseries(expr, start, stop, step)
    elif expr in ('gtid', 'run', 'subrun'):
        values = get_timeseries_field('trig', expr, start, stop, step)
    elif 'heartbeat' in expr:
        values = get_timeseries(expr,start,stop,step)
    elif 'packets' in expr:
        values = get_timeseries(expr,start,stop,step)
    elif expr == u"0\u03bd\u03b2\u03b2":
        import random
        total = get_timeseries('TOTAL',start,stop,step)
        values = [int(random.random() < step/315360) if i else 0 for i in total]
    elif '-' in expr:
        # e.g. PULGT-nhit, which means the average nhit for PULGT triggers
        # this is not a rate, so we divide by the # of PULGT triggers for
        # the interval instead of the interval length
        trig, value = expr.split('-')
        if trig in TRIGGER_NAMES + ['TOTAL', 'polling']:
            if value == 'Baseline':
                values = get_timeseries(expr,start,stop,step)
                counts = get_timeseries('baseline-count',start,stop,step)
            else:
                field = trig if trig in ['TOTAL', 'polling'] else TRIGGER_NAMES.index(trig)
                values = get_timeseries_field('trig:%s' % value,field,start,stop,step)
                counts = get_timeseries_field('trig',field,start,stop,step)
            values = [float(a)/int(b) if a and b else None for a, b in zip(values,counts)]
        else:
            raise ValueError('unknown trigger type %s' % trig)
    elif 'FECD' in expr:
        field = expr.split('/')[1]
        values = get_timeseries_field('trig:fecd',field,start,stop,step)

        interval = get_interval(step)

        values = map(lambda x: int(x)/interval if x else 0, values)
    else:
        if expr in TRIGGER_NAMES:
            field = TRIGGER_NAMES.index(expr)
            values = get_timeseries_field('trig',field,start,stop,step)
        elif expr == 'TOTAL':
            values = get_timeseries_field('trig','TOTAL',start,stop,step)
        elif expr == 'polling':
            values = get_timeseries_field('trig','polling',start,stop,step)
        else:
            values = get_timeseries(expr,start,stop,step)

        interval = get_interval(step)
        if expr in TRIGGER_NAMES or expr in ('TOTAL','L1','L2','ORPHANS','BURSTS', 'polling'):
            # trigger counts are zero by default
            values = map(lambda x: int(x)/interval if x else 0, values)
        else:
            values = map(lambda x: int(x)/interval if x else None, values)

    return values

@app.route('/metric')
@nocache
def metric():
    """Returns the time series for argument `expr` as a JSON list."""
    args = request.args

    expr = args['expr']
    start = args.get('start',type=parseiso)
    stop = args.get('stop',type=parseiso)
    now_client = args.get('now',type=parseiso)
    step = args.get('step',type=int)

    now = int(time.time())

    # adjust for clock skew
    dt = now_client - now
    start -= dt
    stop -= dt

    start = int(start)
    stop = int(stop)
    step = int(step)

    if ',' in expr:
        return jsonify(values=[get_metric(name, start, stop, step) for name in expr.split(',')])
    else:
        return jsonify(values=get_metric(expr, start, stop, step))

@app.route('/eca')
def eca():
    runs = redisdb.runs_after_run('eca_runs_by_number', 0)
    return render_template('eca.html', runs=runs)

@app.route('/eca_run_detail/<run_number>')
def eca_run_detail(run_number):
    run_type = redis.hget('eca-run-%i' % int(run_number),'run_type')
    return render_template('eca_run_detail_%s.html' % run_type, run_number=run_number)

@app.route('/eca_status_detail/<run_number>')
def eca_status_detail(run_number):
    run_type = redis.hget('eca-run-%i' % int(run_number),'run_type')

    def statusfmt(status_int):
        if status_int == 1:
            return 'Flag Raised'
        if status_int == 0:
            return 'Pass'

    def testBit(word, offset):
        int_type = int(word)
        offset = int(offset)
        mask = 1 << offset
        result = int_type & mask
        if result == 0:
            return 0
        if result == pow(2,offset):
            return 1

    run_status = redisdb.get_run_status(int(run_number))

    return render_template('eca_status_detail_%s.html' % run_type,
			    run_number=run_number, statusfmt=statusfmt, testBit=testBit, run_status=run_status)

@app.route('/pcatellie', methods=['GET'])
def pcatellie():

    def boolfmt(bool_string):
        bool_value = bool_string == '1'
        return "Pass" if not bool_value else "Fail"

    def boolclass(bool_string):
        bool_value = bool_string == '1'
        return "success" if not bool_value else "danger"

    start_run = request.args.get("start_run", 0)
    installed_only = request.args.get("installed_only", False)
    runs = redisdb.runs_after_run('pca_runs_by_number', start_run)
    # Deal with expired runs
    runs = [run for run in runs if (len(run) > 0)]
    # Revert the order so the last run is at top of list
    runs = runs[::-1]
    # We need to bunch runs by fiber
    fibers = list()
    for fiber in fiber_position.FIBER_POSITION:
        runs_for_fiber = [run for run in runs
                          if int(run["fiber_number"]) == fiber[0]]
        sorted_runs = sorted(runs_for_fiber,
                                  key=lambda run: (int(run["run_number"])),
                                  reverse=True)
        good_runs_for_fiber = [run for run in runs_for_fiber if (run["pca_status"] == "0")]
        sorted_runs_good = sorted(good_runs_for_fiber,
                                  key=lambda run: (int(run["run_number"])),
                                  reverse=True)
        pca_run = sorted_runs[0]["run_number"] if sorted_runs else ""
        pca_run_good = sorted_runs_good[0]["run_number"] if sorted_runs_good else ""
        pca_result = sorted_runs[0]["pca_status"] if sorted_runs else ""
        fibers.append({'fiber_number': fiber[0],
                       'node': fiber[1],
                       'ab': fiber[2],
                       'is_installed': fiber[3],
                       'is_dead': fiber[4],
                       'fiber_type': fiber[5],
                       'pca_run': pca_run,
                       'pca_run_good': pca_run_good,
                       'pca_result': pca_result})

    return render_template('pcatellie.html',
                           runs=runs,
                           boolfmt=boolfmt,
                           boolclass=boolclass,
                           fibers=fibers,
                           start_run=start_run,
                           installed_only=installed_only,
    )

@app.route('/pca_run_detail/<run_number>')
def pca_run_detail(run_number):
    run = redisdb.runs_after_run('pca_tellie_runs_by_number', int(run_number), int(run_number)+1)
    return render_template('pca_run_detail.html',
                           run_number=run_number,
                           run=run)

@app.route('/burst_run_detail/<int:run_number>/<int:subrun>/<int:sub>')
def burst_run_detail(run_number, subrun, sub):
    return render_template('burst_run_detail.html', data=burst_f.burst_run_detail(run_number, subrun, sub)[0], files=burst_f.burst_run_detail(run_number, subrun, sub)[1], runtype=burst_f.get_run_type(run_number))

@app.route('/burst_run_detail_l3/<int:run_number>/<int:subrun>/<int:sub>')
def burst_run_detail_l3(run_number, subrun, sub):
    return render_template('burst_run_detail_l3.html', data=burst_f.burst_run_detail(run_number, subrun, sub, 3)[0], files=burst_f.burst_run_detail(run_number, subrun, sub, 3)[1], runtype=burst_f.get_run_type(run_number))

@app.route('/pcatellie_processing')
def pcatellie_processing():
    return render_template('pcatellie_processing.html', data=pcaprocessing_f.load_pca_runlist(), limits=pcaprocessing_f.load_limits())

@app.route('/pca_tellie_log/<run_number>')
def pca_tellie_log(run_number):
    return render_template('pca_tellie_log.html', data=pcaprocessing_f.load_pca_log_data(run_number))

@app.route('/pca_tellie_tw/<run_number>')
def pca_tellie_tw(run_number):
    return render_template('pca_tellie_tw.html', data=pcaprocessing_f.load_pca_tw_data(run_number))

@app.route('/pca_tellie_gf/<run_number>')
def pca_tellie_gf(run_number):
    return render_template('pca_tellie_gf.html', data=pcaprocessing_f.load_pca_gf_data(run_number))

@app.route('/pca_tellie_flag/<view>/<run>/<flag>')
def pca_tellie_flag(view, run, flag):
    return render_template('pca_tellie_flag.html', data=pcaprocessing_f.load_pca_flag_data(view, run, flag))

@app.route('/pca_tellie_pmt_flags/<run>/<pmt>')
def pca_tellie_pmt_flags(run, pmt):
    return render_template('pca_tellie_pmt_flags.html', data=pcaprocessing_f.load_pca_pmt_data(run, pmt))

@app.route('/pca_set/<int:first_run>')
def pca_set(first_run):
    return render_template('pca_set.html', data=pcaprocessing_f.load_set(first_run))

@app.route('/pca_proc/<int:first_run>')
def pca_proc(first_run):
    return render_template('pca_proc.html', data=first_run, run=str(first_run))

@app.route('/pca_tellie_run_val1/<int:run>')
def pca_tellie_run_val1(run):
    o = request.args.get('o',type=int)
    return render_template('pca_tellie_run_val1.html', data=pcaprocessing_f.load_run(run, o), run=str(run))

@app.route('/pca_tellie_run_fits/<int:run>')
def pca_tellie_run_fits(run):
    o = request.args.get('o',type=int)
    return render_template('pca_tellie_run_fits.html', data=pcaprocessing_f.load_run(run, o), run=str(run))

@app.route('/pca_tellie_run_val2/<int:run>')
def pca_tellie_run_val2(run):
    o = request.args.get('o',type=int)
    return render_template('pca_tellie_run_val2.html', data=pcaprocessing_f.load_run(run, o), run=str(run))

@app.route('/pca_tellie_fibre/<string:fibre>')
def pca_tellie_fibre(fibre):
    return render_template('pca_tellie_fibre.html', data=pcaprocessing_f.load_fibre(fibre))

@app.route('/pca_tellie_table/<int:run>')
def pca_tellie_table(run):
    return render_template('pca_tellie_table.html', run=run)

@app.route('/pca_tellie_tables/')
def pca_tellie_tables():
    return render_template('pca_tellie_tables.html')

@app.route('/pca_tellie_pmt/<int:set>/<int:pmt>')
def pca_tellie_pmt(set, pmt):
    return render_template('pca_tellie_pmt.html', pmt=pmt, set=set)

@app.route('/pca_tellie_pmt_all/', methods=['GET'])
def pca_tellie_pmt_all():
    pmt = request.args.get("pmt", 5)
    return render_template('pca_tellie_pmt_all.html', pmt=pmt, data=pcaprocessing_f.load_sets())

@app.route('/pca_set_bench/<int:run>')
def pca_set_bench(run):
    return render_template('pca_set_bench.html', data=pcaprocessing_f.load_bench(run), run=str(run) )

@app.route('/burst_form')
def burst_form():
    tick = request.args.get('review',type=int)
    note = request.args.get('notes',type=str)
    summary = request.args.get('summary',type=str)
    name = request.args.get('review_by',type=str)
    run_number = request.args.get('run_number',type=int)
    subrun = request.args.get('subrun',type=int)
    sub = request.args.get('sub',type=int)
    burst_f.burst_form_upload(run_number, subrun, sub, tick, summary, note, name)
    return render_template('burst_run_detail_l3.html', data=burst_f.burst_run_detail(run_number, subrun, sub, 3)[0], files=burst_f.burst_run_detail(run_number, subrun, sub, 3)[1])

@app.route('/presn_run_detail/<int:run_number>')
def presn_run_detail(run_number):
    return render_template('presn_run_detail.html', data=presn_f.presn_run_detail(run_number)[0], files=presn_f.presn_run_detail(run_number)[1])


@app.route('/calibdq')
def calibdq():
        return render_template('calibdq.html')

@app.route('/calibdq_tellie')
def calibdq_tellie():
    run_dict = {}
    limit = request.args.get("limit", 10, type=int)
    offset = request.args.get("offset", 0, type=int)
    runs = HLDQTools.import_TELLIE_runnumbers(limit=limit, offset=offset)
    run_num, check_params, runInformation = HLDQTools.import_TELLIEDQ_ratdb(runs)
    for num in runs:
        run_dict[num] = check_params[num]
    run_numbers_sorted = sorted(run_dict.keys(),reverse=True)
    run_vals_sorted = []
    for runNum in run_numbers_sorted:
        run_vals_sorted.append(run_dict[runNum])
    return render_template('calibdq_tellie.html', run_numbers=run_numbers_sorted, run_info=run_vals_sorted, limit=limit, offset=offset)

@app.route('/calibdq_tellie/<int:run_number>/')
def calibdq_tellie_run_number(run_number):
    run_num, check_params, runInfo = HLDQTools.import_TELLIEDQ_ratdb(run_number)
    return render_template('calibdq_tellie_run.html', run_number=run_number, runInformation=runInfo[run_number])

@app.route('/calibdq_tellie/<int:run_number>/<int:subrun_number>')
def calibdq_tellie_subrun_number(run_number,subrun_number):
    run_num, check_params, runInfo = HLDQTools.import_TELLIEDQ_ratdb(run_number)
    # Find the index
    try:
        subrun_index = runInfo[run_number]["subrun_numbers"].index(subrun_number)
    except ValueError:
        subrun_index = -999
    return render_template('calibdq_tellie_subrun.html', run_number=run_number, subrun_index=subrun_index, runInformation=runInfo[run_number])

@app.route('/noise')
def noise():
    limit = request.args.get("limit", 336, type=int) # ~ 2 weeks
    offset = request.args.get("offset", 0, type=int)
    plotmask = request.args.get("plotmask", 2, type=int)
    runs = pmtnoisedb.get_noise_results(limit, offset)
    return render_template('noise.html', runs=runs,
                            limit=limit, offset=offset,
                            plotmask=plotmask)

@app.route('/noise_run_detail/<run_number>')
def noise_run_detail(run_number):
    run = pmtnoisedb.get_run_by_number(run_number)
    if len(run):
        return render_template('noise_run_detail.html', run=run[0], run_number=run_number)
    else:
        return render_template('noise_run_detail.html', run=0, run_number=run_number)

@app.route('/css-proc')
def cssProc():
    return render_template('cssProc.html',info = cssproc.Info(-1))

@app.route('/cssProc/<int:run_number>')
def cssProcIndy(run_number):
    return render_template('cssProcIndy.html', info = cssproc.Info(run_number), run= run_number)

@app.route('/occupancy_by_trigger')
def occupancy_by_trigger():
    limit = request.args.get("limit", 25, type=int)
    selected_run = request.args.get("run", 0, type=int)
    run_range_low = request.args.get("run_range_low", 0, type=int)
    run_range_high = request.args.get("run_range_high", 0, type=int)
    gold = request.args.get("gold_runs", 0, type=int)

    gold_runs = 0
    if gold:
        gold_runs = golden_run_list()

    if not selected_run:
        runs = occupancy.run_list(limit, run_range_low, run_range_high, gold_runs)
    else:
        runs = [selected_run]

    status, crates, slots = occupancy.occupancy_by_trigger_limit(limit, selected_run, run_range_low, run_range_high, gold_runs)

    # If no data for selected run
    if len(status) == 0:
        status[selected_run] = -1

    return render_template('occupancy_by_trigger.html', runs=runs, limit=limit, crates=crates, slots=slots, status=status, selected_run=selected_run, run_range_low=run_range_low, run_range_high=run_range_high, gold=gold)

@app.route('/occupancy_by_trigger_run/<run_number>')
def occupancy_by_trigger_run(run_number):

    # ESUMH is 6th trigger bit
    issues = occupancy.occupancy_by_trigger(6, run_number, True)

    return render_template('occupancy_by_trigger_run.html', run_number=run_number, issues=issues)

@app.route('/nearline_monitoring_summary')
def nearline_monitoring_summary():
    limit = request.args.get("limit", 25, type=int)
    selected_run = request.args.get("run", 0, type=int)
    run_range_low = request.args.get("run_range_low", 0, type=int)
    run_range_high = request.args.get("run_range_high", 0, type=int)
    runtype = request.args.get("runtype", -1, type=int)
    gold = request.args.get("gold_runs", 0, type=int)

    # Select only golden runs
    gold_runs = 0
    if gold:
        gold_runs = golden_run_list()

    # Get the run type and run list from the nearline database
    runTypes, runs = nearline_monitor.get_run_types(limit, selected_run, run_range_low, run_range_high, gold_runs)

    # Get the data for each of the nearline tools
    clock_jumps, ping_crates, channel_flags, occupancy, muons, crate_gain = \
        nearline_monitor.get_run_list(limit, selected_run, run_range_low, run_range_high, runs, gold_runs)

    # Allow sorting by run type
    allrunTypes = nlrat.RUN_TYPES

    displayed_runs = []
    if runtype == -1:
        selectedType = "All"
        displayed_runs = runs
    else:
        selectedType = allrunTypes[runtype]

        if run_range_high:
            run_list = detector_state.get_runs_with_run_type(run_range_low, (1<<runtype), run_range_high)
        elif selected_run:
            run_list = detector_state.get_runs_with_run_type(selected_run-1, (1<<runtype), selected_run+1)
        else:
            run = detector_state.get_latest_run()
            run_list = detector_state.get_runs_with_run_type(run - limit, (1<<runtype))

        # Apply the run type to the failure list
        for run in runs:
            if run in run_list:
                displayed_runs.append(run)

    return render_template('nearline_monitoring_summary.html', runs=displayed_runs, selected_run=selected_run, limit=limit, clock_jumps=clock_jumps, ping_crates=ping_crates, channel_flags=channel_flags, occupancy=occupancy, muons=muons, crate_gain=crate_gain, runTypes=runTypes, run_range_low=run_range_low, run_range_high=run_range_high, allrunTypes=allrunTypes, selectedType=selectedType, gold=gold)

@app.route('/physicsdq')
def physicsdq():
    limit = request.args.get("limit", 10, type=int)
    offset = request.args.get("offset", 0, type=int)
    runs = HLDQTools.import_HLDQ_runnumbers(limit=limit,offset=offset)
    run_info = HLDQTools.import_HLDQ_ratdb(runs)
    proc_results = [HLDQTools.generateHLDQProcStatus(x) if x != -1 else -1 for x in run_info]
    return render_template('physicsdq.html', physics_run_numbers=runs, proc_results=proc_results, run_info=run_info, limit=limit, offset=offset)

@app.route('/pingcrates')
def pingcrates():
    limit = request.args.get("limit", 25, type=int)
    selected_run = request.args.get("run", 0, type=int)
    run_range_low = request.args.get("run_range_low", 0, type=int)
    run_range_high = request.args.get("run_range_high", 0, type=int)
    gold = request.args.get("gold_runs", 0, type=int)

    gold_runs = 0
    if gold:
        gold_runs = golden_run_list()

    data = pingcratesdb.ping_crates_list(limit, selected_run, run_range_low, run_range_high, gold_runs)
    return render_template('pingcrates.html', data=data, limit=limit, selected_run=selected_run, run_range_low=run_range_low, run_range_high=run_range_high, gold=gold)

@app.route('/pingcrates_run/<run_number>')
def pingcrates_run(run_number):
    return render_template('pingcrates_run.html', run_number=run_number)

@app.route('/channelflags')
def channelflags():
    limit = request.args.get("limit", 25, type=int)
    selected_run = request.args.get("run", 0, type=int)
    run_range_low = request.args.get("run_range_low", 0, type=int)
    run_range_high = request.args.get("run_range_high", 0, type=int)
    gold = request.args.get("gold_runs", 0, type=int)

    gold_runs = 0
    if gold:
        gold_runs = golden_run_list()

    if not selected_run:
        runs, nsync16, nsync24, nresyncs, sync16s, sync24s, missed, missed_burst, sync16s_pr, sync24s_pr, normal, owl, other = channelflagsdb.get_channel_flags(limit, run_range_low, run_range_high, False, gold_runs)
    else:
        nsync16 = {}
        nsync24 = {}
        missed = {}
        sync16s = {}
        sync24s = {}
        sync16s_pr = {}
        sync24s_pr = {}
        nresyncs = {}
        missed_burst = {}
        runs = [selected_run]
        missed_count, cmos_sync16, cgt_sync24, cmos_sync16_pr, cgt_sync24_pr, mburst, normal, owl, other = channelflagsdb.get_channel_flags_by_run(selected_run)
        sync16s[selected_run] = len(cmos_sync16)
        sync16s_pr[selected_run] = len(cmos_sync16_pr)
        sync24s[selected_run] = len(cgt_sync24)
        sync24s_pr[selected_run] = len(cgt_sync24_pr)
        missed[selected_run] = len(missed_count)
        missed_burst[selected_run] = len(mburst)
        nsync16[selected_run], nsync24[selected_run], nresyncs[selected_run] = channelflagsdb.get_number_of_syncs(selected_run)
    return render_template('channelflags.html', runs=runs, nsync16=nsync16, nsync24=nsync24, nresyncs=nresyncs, sync16s=sync16s, sync24s=sync24s, missed=missed, sync16s_pr=sync16s_pr, sync24s_pr=sync24s_pr, limit=limit, selected_run=selected_run, run_range_low=run_range_low, run_range_high=run_range_high, normal=normal, owl=owl, other=other, gold=gold, missed_burst=missed_burst)

@app.route('/channelflagsbychannel/<run_number>')
def channelflagsbychannel(run_number):
    missed_count, cmos_sync16, cgt_sync24, cmos_sync16_pr, cgt_sync24_pr, missed_burst,_,_,_ = channelflagsdb.get_channel_flags_by_run(run_number)
    return render_template('channelflagsbychannel.html', missed_count=missed_count, cmos_sync16=cmos_sync16, cgt_sync24=cgt_sync24, cmos_sync16_pr=cmos_sync16_pr, cgt_sync24_pr=cgt_sync24_pr, missed_burst=missed_burst, run_number=run_number)

@app.route('/muon_list')
def muon_list():
    limit = request.args.get("limit", 25, type=int)
    selected_run = request.args.get("run", 0, type=int)
    run_range_low = request.args.get("run_range_low", 0, type=int)
    run_range_high = request.args.get("run_range_high", 0, type=int)
    gold = request.args.get("gold_runs", 0, type=int)
    atm = request.args.get("atm", 0, type=int)

    gold_runs = 0
    if gold:
        gold_runs = golden_run_list()

    mruns, mcount, mmcount, atmcount, livetime, mfake, time_check = muonsdb.get_muons(limit, selected_run, run_range_low, run_range_high, gold_runs, atm)

    return render_template('muon_list.html', mruns=mruns, limit=limit, selected_run=selected_run, run_range_low=run_range_low, run_range_high=run_range_high, gold=gold, mcount=mcount, mmcount=mmcount, mfake=mfake, atmcount=atmcount, livetime=livetime, atm=atm, time_check=time_check)

@app.route('/muons_by_run/<run_number>')
def muons_by_run(run_number):
    muon_info, mmuon_info, atm_info = muonsdb.get_muon_info_by_run(int(run_number))
    run_number=int(run_number)

    return render_template('muons_by_run.html', run_number=run_number, muon_info=muon_info, mmuon_info=mmuon_info, atm_info=atm_info)

@app.route('/trigger_clock_jump')
def trigger_clock_jump():
    limit = request.args.get("limit", 25, type=int)
    selected_run = request.args.get("run", 0, type=int)
    run_range_low = request.args.get("run_range_low", 0, type=int)
    run_range_high = request.args.get("run_range_high", 0, type=int)
    gold = request.args.get("gold_runs", 0, type=int)

    gold_runs = 0
    if gold:
        gold_runs = golden_run_list()

    runs, njump10, njump50, clock_status = triggerclockjumpsdb.get_clock_jumps(limit, selected_run, run_range_low, run_range_high, gold_runs)

    return render_template('trigger_clock_jump.html', runs=runs, limit=limit, njump10=njump10, njump50=njump50, clock_status=clock_status, selected_run=selected_run, run_range_low=run_range_low, run_range_high=run_range_high, gold=gold)

@app.route('/trigger_clock_jump_run/<run_number>')
def trigger_clock_jump_run(run_number):
    data10, data50 = triggerclockjumpsdb.get_clock_jumps_by_run(run_number)
    return render_template('trigger_clock_jump_run.html', run_number=run_number, data10=data10, data50=data50)

@app.route('/crate_gain_monitor')
def crate_gain_monitor():
    limit = request.args.get("limit", 25, type=int)
    selected_run = request.args.get("run", 0, type=int)
    run_range_low = request.args.get("run_range_low", 0, type=int)
    run_range_high = request.args.get("run_range_high", 0, type=int)
    gold = request.args.get("gold_runs", 0, type=int)

    gold_runs = 0
    if gold:
        gold_runs = golden_run_list()

    runs, crate_qhs, crate_array = gain_monitor.crate_gain_monitor(limit, selected_run, run_range_low, run_range_high, gold_runs)

    lower_limit = 100
    if selected_run:
        run = selected_run
    elif run_range_high:
        run = run_range_high
        if(run_range_low < run_range_high - lower_limit):
            lower_limit = run_range_low
    else:
        run = detector_state.get_latest_run()

    qhs_change = gain_monitor.crate_average(run, lower_limit)

    return render_template('crate_gain_monitor.html', runs=runs, limit=limit, selected_run=selected_run, run_range_low=run_range_low, run_range_high=run_range_high, gold=gold, crate_qhs=crate_qhs, qhs_change=qhs_change, crate_array=crate_array)

@app.route('/crate_gain_monitor_by_run/<run_number>')
def crate_gain_monitor_by_run(run_number):
    return render_template('crate_gain_monitor_by_run.html', run_number=run_number)

@app.route('/crate_gain_history')
def crate_gain_history():
    crate = request.args.get('crate',0,type=int)
    starting_run = request.args.get('starting_run',0,type=int)
    ending_run = request.args.get('ending_run',0,type=int)
    qhs_low = request.args.get('qhs_low',15.0,type=float)
    qhs_high = request.args.get('qhs_high',30.0,type=float)

    # Default to hard-coded first processed run
    if starting_run == 0:
        starting_run = 112621
    # Default to current run
    if ending_run == 0:
        ending_run = detector_state.get_latest_run()

    data = gain_monitor.crate_gain_history(starting_run, ending_run, crate, qhs_low, qhs_high)
    return render_template('crate_gain_history.html', crate=crate, data=data, starting_run=starting_run, ending_run=ending_run, qhs_low=qhs_low, qhs_high=qhs_high)

@app.route('/shifter_information', methods=["GET", "POST"])
def shifter_information():
    if request.form:
        form = ShifterInfoForm(request.form)
    else:
        form = ShifterInfoForm()

    form.expert.choices = get_experts()
    form.supernova_expert.choices = get_supernova_experts()

    if request.method == "POST" and form.validate():
        try:
            set_shifter_information(form)
        except Exception as e:
            flash(str(e), 'danger')
            return render_template('shifter_information.html', form=form)
        flash("Successfully submitted", 'success')
        return redirect(url_for("shifter_information"))

    shifter, expert, supernova_expert = get_shifter_information()
    return render_template('shifter_information.html', form=form, shifter=shifter, expert=expert, supernova_expert=supernova_expert)

@app.route('/deck_activity')
def deck_activity():
    limit = request.args.get('limit',25,type=int)
    offset = request.args.get('offset',0,type=int)

    act = activity.get_deck_activity(limit, offset)
    return render_template('deck_activity.html', act=act, limit=limit, offset=offset)

@app.route('/physicsdq/<int:run_number>')
def physicsdq_run_number(run_number):
    ratdb_dict = HLDQTools.import_HLDQ_ratdb([run_number])[0]
    return render_template('physicsdq_run_number.html', run_number=run_number, ratdb_dict=ratdb_dict)

@app.route('/calibdq_smellie')
def calibdq_smellie():
    run_dict = {}
    limit = request.args.get("limit", 10, type=int)
    offset = request.args.get("offset", 0, type=int)
    runs = HLDQTools.import_SMELLIE_runnumbers(limit=limit,offset=offset)
    run_num, check_params, runInformation = HLDQTools.import_SMELLIEDQ_ratdb(runs)
    for num in runs:
        run_dict[num] = check_params[num]
    run_numbers_sorted = sorted(run_dict.keys(),reverse=True)
    run_vals_sorted = []
    for runNum in run_numbers_sorted:
        run_vals_sorted.append(run_dict[runNum])
    return render_template('calibdq_smellie.html', run_numbers=run_numbers_sorted, run_info=run_vals_sorted, limit=limit, offset=offset)

@app.route('/calibdq_smellie/<int:run_number>')
def calibdq_smellie_run_number(run_number):
    run_num, check_dict, runInfo = HLDQTools.import_SMELLIEDQ_ratdb(int(run_number))
    return render_template('calibdq_smellie_run.html', run_number=run_number, runInfo=runInfo[run_number])

@app.route('/calibdq_smellie/<int:run_number>/<int:subrun_number>')
def calibdq_smellie_subrun_number(run_number,subrun_number):
    run_num, check_dict, runInfo = HLDQTools.import_SMELLIEDQ_ratdb(run_number)
    return render_template('calibdq_smellie_subrun.html', run_number=run_number, subrun_number=subrun_number, runInformation=runInfo[run_number])

@app.route("/dropout")
@app.route("/dropout/<int:run_number>")
def dropout_overview(run_number=None):
    if run_number is None:
        trigger_type = request.args.get("trigger_type", default='0')
        if trigger_type.isdigit():
            trigger_type = int(trigger_type)
        else:
            trigger_type = 1 if trigger_type.upper() == "N20" else 0
        trigger_type = 1 if trigger_type != 0 else 0
        return render_template("dropout.html", trigger_type=trigger_type)

    return render_template("dropout_detail.html", run_number=run_number)

@app.route("/_dropout_fits/<trigger_type>")
def _dropout_fits(trigger_type=None):
    if trigger_type is None:
        trigger_type = 0

    try:
        trigger_type = int(trigger_type)
    except ValueError:
        trigger_type = 1 if trigger_type.upper() == "N20" else 0

    trigger_type = 1 if trigger_type != 0 else 0
    run_range = request.args.get("run_range", default=500, type=int)
    run_min = request.args.get("run_min", default=-1, type=int)
    run_max = request.args.get("run_max", default=-1, type=int)

    if run_min > 0 and run_max > run_min:
        run_range = (run_min, run_max)

    try:
        return dropout.get_fits(trigger_type, run_range=run_range)
    except Exception:
        return json.dumps(None)

# TODO see if you can make this URL less long
@app.route("/dropout/_dropout_detail/N100/<int:run_number>")
def _dropout_detail_n100(run_number):
    return dropout.get_details(run_number, 1)

@app.route("/dropout/_dropout_detail/N20/<int:run_number>")
def _dropout_detail_n20(run_number):
    return dropout.get_details(run_number, 2)

@app.route('/scint_level')
def scint_level():
    run_range_low = request.args.get("run_range_low", 250000, type=int)
    run_range_high = request.args.get("run_range_high", 0, type=int)

    if run_range_high == 0:
        run_range_high = detector_state.get_latest_run()

    scint_data = scintillator_level.get_scintillator_level(run_range_low, run_range_high)
    av_data = scintillator_level.get_av_z_offset(run_range_low, run_range_high)
    rope_data = scintillator_level.get_av_rope_data(run_range_low, run_range_high)
    return render_template('scint_level.html', scint_data=scint_data, av_data=av_data, rope_data=rope_data, run_range_low=run_range_low, run_range_high=run_range_high)


@app.route('/runselection')
def runselection():
    # Get variable info from webpage (with defaults defined)
    limit = request.args.get("limit", 25, type=int)
    offset = request.args.get("offset", 0, type=int)
    result = request.args.get("result", "All", type=str)
    criteria = request.args.get("criteria", "scintillator", type=str)
    selected_run = request.args.get("selected_run", 0, type=int)
    run_range_low = request.args.get("run_range_low", 0, type=int)
    run_range_high = request.args.get("run_range_high", 0, type=int)
    year_low = request.args.get("year_low", 0, type=int)
    month_low = request.args.get("month_low", 0, type=int)
    day_low = request.args.get("day_low", 0, type=int)
    year_high = request.args.get("year_high", 0, type=int)
    month_high = request.args.get("month_high", 0, type=int)
    day_high = request.args.get("day_high", 0, type=int)

    # Use this to get run info from databases, to display in list
    run_range = [run_range_low, run_range_high]
    date_range = [[year_low, month_low, day_low], [year_high, month_high, day_high]]
    run_info, drop_down_crits = RSTools.list_runs_info(limit, offset, result, criteria, selected_run, run_range, date_range)

    # Return info to webpage
    return render_template('runselection.html', run_info=run_info, drop_down_crits=drop_down_crits, criteria=criteria, limit=limit, offset=offset, result=result, selected_run=selected_run, run_range_low=run_range_low, run_range_high=run_range_high,
                           year_low=year_low, month_low=month_low, day_low=day_low, year_high=year_high, month_high=month_high, day_high=day_high)

@app.route('/runselection_run/<int:run_number>', methods=['GET', 'POST'])
def runselection_run(run_number):
    # run_info, criteria_info = RSTools.import_RS_ratdb(run_number, 'All', 0, 0)
    general_info, display_info, run_prev_next = RSTools.format_data(run_number)
    list_history = RSTools.get_list_history(run_number)
    lists = RSTools.get_run_lists()
    list_data = RSTools.get_current_lists_run(run_number)

    if lists == False:
        lists_keys = False
    else:
        lists_keys = lists.keys()

    # Create forms
    is_pass_form = False
    if request.form:
        # Find out which form is being used: run_list or pass
        # (run_list has more elements than just: name, comment, password)
        if 'criteria' in request.form.keys():
            is_pass_form = True

        # Update relenvent form
        if is_pass_form:
            pass_form = RSTools.file_pass_form_builder(request.form, display_info)
        else:
            list_form = RSTools.file_list_form_builder(request.form, lists, list_data)
    else:
        list_form = RSTools.file_list_form_builder(-1, lists, list_data)
        pass_form = RSTools.file_pass_form_builder(-1, display_info)

    # Validate and submit forms
    if request.method == 'POST':
        succeeded = True
        error_msg = 'Unsuccessful: error submitting form'
        try:
            if 'criteria' in request.form.keys():
                # Passing run form
                if pass_form.validate():
                    result, error_msg = RSTools.pass_fail_run(pass_form, run_number)
                    if not result:
                        succeeded = False
                else:
                    succeeded = False
            else:
                # Changing run lists form
                if list_form.validate():
                    result = RSTools.update_run_lists(list_form, run_number, lists, list_data)
                    if not result:
                        succeeded = False
                else:
                    succeeded = False
        except Exception as e:
            flash(str(e), 'danger')
            return redirect(url_for('runselection_run', run_number=run_number))
        
        if succeeded:
            flash('Successfully submitted', 'success')
        else:
            flash(error_msg, 'danger')
        
        return redirect(url_for('runselection_run', run_number=run_number))

    return render_template('runselection_run.html', run_number=run_number, general_info=general_info, display_info=display_info, list_history=list_history, lists=lists_keys, list_form=list_form, pass_form=pass_form, run_prev_next=run_prev_next)


@app.route('/light_level')
def light_level():
    run_range_low = request.args.get("run_range_low", 350000, type=int)
    run_range_high = request.args.get("run_range_high", 0, type=int)
    fv = request.args.get("fv", 3000, type=int)
    nhits_select = request.args.get("nhits_select","Nhits Corrected", type=str)

    if run_range_high == 0:
        run_range_high = detector_state.get_latest_run()

    if nhits_select == "Nhits Corrected":
        light_levels = get_light_level(run_range_low, run_range_high, fv)
    else:
        light_levels = get_light_level_clean(run_range_low, run_range_high, fv)

    return render_template('light_level.html', light_levels=light_levels, run_range_low=run_range_low, run_range_high=run_range_high, fv=fv, nhits_select=nhits_select)

@app.route('/light_level_plots/<run_number>')
def light_level_plots(run_number):
    return render_template('light_level_plots.html', run_number=run_number)


@app.route('/light_level_summary')
def light_level_summary():
    run_range_low = request.args.get("run_range_low", 300000, type=int)
    run_range_high = request.args.get("run_range_high", 0, type=int)
    fiducial_volume = request.args.get("fiducial_volume", 3000, type=int)
    limit = request.args.get("limit", 100, type=int)

    if run_range_high == 0:
        run_range_high = detector_state.get_latest_run()

    light_levels = get_all_light_levels(run_range_low, run_range_high, fiducial_volume, limit)

    return render_template('light_level_summary.html', light_levels=light_levels, run_range_low=run_range_low, run_range_high=run_range_high, fiducial_volume=fiducial_volume)

@app.route('/radon_monitor')
def radon_monitor():

    year_low = request.args.get("year_low", 2021, type=int)
    month_low = request.args.get("month_low", 1, type=int)
    day_low = request.args.get("day_low", 1, type=int)
    year_high = request.args.get("year_high", 2024, type=int)
    month_high = request.args.get("month_high", 1, type=int)
    day_high = request.args.get("day_high", 1, type=int)
    yscale = request.args.get("yscale", "log", type=str)
    ylow = request.args.get("ylow", 1e-6, type=float)
    yhigh = request.args.get("yhigh", 0.6, type=float)

    pdata = get_radon_monitor(year_low, month_low, day_low, year_high, month_high, day_high)

    return render_template('radon_monitor.html', pdata=pdata, yscale=yscale, ylow=ylow, yhigh=yhigh)


@app.route('/runselection_plots')
def runselection_plots():
    datehigh = datetime.now()
    datelow = datehigh - timedelta(days=7)
    # Get variable info from webpage (with defaults defined)
    criteria = request.args.get("criteria", "scintillator_silver", type=str)
    year_low = request.args.get("year_low", datelow.year, type=int)
    month_low = request.args.get("month_low", datelow.month, type=int)
    day_low = request.args.get("day_low", datelow.day, type=int)
    year_high = request.args.get("year_high", datehigh.year, type=int)
    month_high = request.args.get("month_high", datehigh.month, type=int)
    day_high = request.args.get("day_high", datehigh.day, type=int)
    # Use this to get run info from databases, to display in list
    date_range = [[year_low, month_low, day_low], [year_high, month_high, day_high]]
    rs_plot_data, drop_down_crits = RSTools.pass_fail_plot_info(criteria, date_range)
    # Return info to webpage
    return render_template('runselection_plots.html', rs_plot_data=rs_plot_data, drop_down_crits=drop_down_crits, criteria=criteria, year_low=year_low, month_low=month_low, day_low=day_low, year_high=year_high, month_high=month_high, day_high=day_high)
