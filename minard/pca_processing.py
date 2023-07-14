import couchdb
import json
import os
import functools
import ratdbloader
import pca_flags
import detectorviz
from . import app
from .db import engine, engine_nl

scratch = os.getcwd() + "/minard/static/pcatellie/scratch"

def load_pca_runlist():
    """
    Connects to couchdb and loads run list.
    Also parses PCA log file for status: overall, TW, GF.
    Returns: an array composed of the couchdb doc with the status appended.
    """
    server = couchdb.Server("http://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])
    db = server["tellie_auto"]
    view_string = "runlist"

    results = []
    for row in db.view('_design/'+view_string+'/_view/'+view_string):
        doc_id = row.id
        try:
            results.append(dict(db.get(doc_id).items()))
        except KeyError:
            app.logger.warning("Code returned KeyError searching for runlist information in the couchDB. Dod ID: %d" % doc_id)

    for i in range (0, len(results)):
        run_start = results[i]['runrange'][0]
        status = parse_log_file(str(run_start))
        results[i]['status'] = status

    return results

def parse_log_file(run):
    """
    Loads and parses PCA log ratdb file.
    Returns: the status of the PCA calibration, from file.
    If the file does not exist, returns negative value that is handled in html.
    """
    file_path = os.getcwd() + "/minard/static/pcatellie/pca_constants/PCA_log_" + run + "_0.ratdb"
    try:
        with open(file_path, 'r') as input_file:
            log = json.load(input_file)
            return bin(log['PCA_status']).replace("0b", "")
    except:
        return bin(-222).replace("0b", "")

def load_set(first_run):
    """
    Loads all relevant data for a singe PCA dataset, from couchdb.
    This includes: list of fibres, runlist, run-fibre pairs, validation bitwords, fits. Matches data together into array.
    Returs: big array for the set, including relevant per-fibre data.
    """
    server = couchdb.Server("http://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])
    db = server["tellie_auto"]

    # load list of fibres first
    view_string = "fibres"

    fibres = []
    for row in db.view('_design/'+view_string+'/_view/'+view_string):
        doc_id = row.id
        try:
            fibres.append(dict(db.get(doc_id).items()))
        except KeyError:
            app.logger.warning("Code returned KeyError searching for runlist information in the couchDB. Dod ID: %d" % doc_id)

    # then road run list
    view_string = "runlist"

    results = []
    for row in db.view('_design/'+view_string+'/_view/'+view_string):
        doc_id = row.id
        if row.value[1][0] == first_run:
            try:
                results.append(dict(db.get(doc_id).items()))
            except KeyError:
                app.logger.warning("Code returned KeyError searching for runlist information in the couchDB. Dod ID: %d" % doc_id)

    # then assign run to fibre
    sorted_runs = []
    real_runs = []
    for fibre in fibres[0]['fibres']:
            run = "N/A"
            for fibre_run in results[0]['fibres']:
                if fibre == fibre_run:
                    i = results[0]['fibres'].index(fibre)
                    run = results[0]['runlist'][i]
                    real_runs.append( run )
            sorted_runs.append( run )

    # for each existing run, get bitwords and fits
    view_string1 = "val1"
    view_string2 = "fits"
    view_string3 = "val2"
    real_runs.sort()
    startkey = real_runs[0]
    endkey = real_runs[-1]

    bitword_val1 = []
    for row in db.view('_design/'+view_string1+'/_view/'+view_string1, startkey=startkey, endkey=endkey):
        bitword_val1.append( row['value'][2] )

    ang_fit = []
    injection_fit = []
    for row in db.view('_design/'+view_string2+'/_view/'+view_string2, startkey=startkey, endkey=endkey):
        ang_fit.append( row['value'][2] )
        injection_fit.append( row['value'][3] )

    bitword_val2 = []
    for row in db.view('_design/'+view_string3+'/_view/'+view_string3, startkey=startkey, endkey=endkey):
        bitword_val2.append( row['value'][1] )

    final_bitword_val1 = []
    final_ang_fit = []
    final_injection_fit = []
    final_bitword_val2 = []
    # finally match
    for run in sorted_runs:
        if run == "N/A":
            final_bitword_val1.append( "N/A" )
            final_ang_fit.append( "N/A" )
            final_injection_fit.append( "N/A" )
            final_bitword_val2.append( "N/A" )
        else:
            for rrun in real_runs:
                if run == rrun:
                    i = real_runs.index(rrun)
                    final_bitword_val1.append( bitword_val1[i] )
                    final_ang_fit.append( ang_fit[i] )
                    final_injection_fit.append( injection_fit[i] )
                    final_bitword_val2.append( bitword_val2[i] )

    return fibres[0], sorted_runs, final_bitword_val1, final_ang_fit, final_injection_fit, final_bitword_val2

def load_run(run, o):
    """
    Connects to couchdb and loads either: validation1, fits, or validation2 data for specific run.
    Returns: couchdb document as array.
    """
    server = couchdb.Server("http://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])
    db = server["tellie_auto"]

    starkey = [run, {}]
    endkey = [run, {}]

    # val1
    if o == 1:
        view_string = "val1"
        for row in db.view('_design/'+view_string+'/_view/'+view_string):
            doc_id = row.id
            if row.value[0] == run:
                try:
                    results = dict(db.get(doc_id).items())
                except KeyError:
                    app.logger.warning("Code returned KeyError searching for runlist information in the couchDB. Dod ID: %d" % doc_id)
        return results

    # fits
    elif o == 2:
        view_string = "fits"
        for row in db.view('_design/'+view_string+'/_view/'+view_string):
            doc_id = row.id
            if row.value[0] == run:
                try:
                    results = dict(db.get(doc_id).items())
                except KeyError:
                    app.logger.warning("Code returned KeyError searching for runlist information in the couchDB. Dod ID: %d" % doc_id)
        return results

    # val2
    elif o == 3:
        view_string = "val2"
        for row in db.view('_design/'+view_string+'/_view/'+view_string):
            doc_id = row.id
            if row.value[0] == run:
                try:
                    results = dict(db.get(doc_id).items())
                except KeyError:
                    app.logger.warning("Code returned KeyError searching for runlist information in the couchDB. Dod ID: %d" % doc_id)
        return results

def load_fibre(fibre):
    """
    Connects to couchdb and obtains index (position) for specific fibre.
    Returns: run number for particular fibre in a dataset.
    """
    server = couchdb.Server("http://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])
    db = server["tellie_auto"]

    results = []
    view_string = "runlist"
    for row in db.view('_design/'+view_string+'/_view/'+view_string):
        doc_id = row.id
        try:
            doc = dict(db.get(doc_id).items())
            try:
                ind = doc['fibres'].index(fibre)
            except:
                continue
            run = doc['runlist'][ind]
            results.append( run )
        except KeyError:
            app.logger.warning("Code returned KeyError searching for runlist information in the couchDB. Dod ID: %d" % doc_id)
    return results

def load_limits():
    """
    Connects to couchdb and loads environment variables (stored as doc).
    Returns: contents of couchdb doc holding env variables.
    """
    server = couchdb.Server("http://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])
    db = server["tellie_auto"]

    view_string = "env"
    for row in db.view('_design/'+view_string+'/_view/'+view_string):
        doc_id = row.id
        try:
            results = dict(db.get(doc_id).items())
        except KeyError:
            app.logger.warning("Code returned KeyError searching for runlist information in the couchDB. Dod ID: %d" % doc_id)
    return results

def load_bench(run):
    """
    Connects to couchdb, loads benchmark document for particular run.
    Returns: contents of specific couchdb document (benchmark).
    """
    server = couchdb.Server("http://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])
    db = server["tellie_auto"]

    view_string = "benchmark"
    for row in db.view('_design/'+view_string+'/_view/'+view_string):
        doc_id = row.id
        if int(row.key[0]-1) == int(run):
            try:
                result = dict(db.get(doc_id).items())
            except KeyError:
                app.logger.warning("Code returned KeyError searching for runlist information in the couchDB. Dod ID: %d" % doc_id)
    return result

def load_sets():
    """
    Connects to couchdb, loads runlist document for particular run.
    Returns: contents of specific couchdb document (runlist).
    """
    server = couchdb.Server("http://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])
    db = server["tellie_auto"]
    view_string = "runlist"

    result = []
    for row in db.view('_design/'+view_string+'/_view/'+view_string):
        first_run = row.key[0]
        result.append( first_run )
    return result

class FuzzyDict(dict):
    """
    A dict subclass that gives case-insensitive "x in y" substring key lookup
    when unambiguous matches can be found. fixme: word this better

    For example, in a dict:
    record = FuzzyDict({"ProductStandardName": 'apple',
                        "ProductColor": 'red',
                        "ProductKind": 'fruit'})
    >>> record['name']
    'apple'
    >>> record['product']
    KeyError: 'Fuzzy key "product" is ambiguous; matches: ProductStandardName,
     ProductKind, ProductColor'

    Designed to be used with dicts that don't change much after creation.
    There is an internal search cache that never invalidates
    """
    keyview = None
    cache = None

    def __init__(self, *args, **kwargs):
        super(FuzzyDict, self).__init__(*args, **kwargs)
        self.keyview = self.viewkeys()
        self.cache = dict()


    def __missing__(self, fuzzy_key):
        cache = self.cache
        if fuzzy_key in cache:
            return self[cache[fuzzy_key]]

        lc_fuzzy_key = fuzzy_key.lower()
        matching_keys = [key for key in self.keyview
                         if lc_fuzzy_key in key.lower()]
        match_count = len(matching_keys)

        if match_count > 1:
            # ambiguous match
            raise KeyError('Fuzzy key "{}" is ambiguous; matches: {}'.format(
                fuzzy_key, ", ".join(matching_keys)))
        elif match_count < 1:
            raise KeyError('Fuzzy key "{}" did not match any keys'.format(
                fuzzy_key))

        # it worked
        match = matching_keys[0]
        cache[fuzzy_key] = match
        return self[match]

def get_pca_log(run_name):
    """ Return the run object LOG for the given pca run """
    return ratdbloader.load_ratdb(os.getcwd() + "/minard/static/pcatellie/pca_constants/PCA_log_" + run_name + "_0.ratdb")

def get_pca_tw(run_name):
    """ Return the run object TW for the given pca run """
    data = FuzzyDict(ratdbloader.load_ratdb(os.getcwd() + "/minard/static/pcatellie/pca_constants/PCATW_" + run_name + "_0.ratdb"))
    data['name'] = run_name
    data['path'] = "/pcatellie/"
    data['status'] = data.pop('PCATW_status')
    return data

def get_pca_gf(run_name):
    """ Return the run object GF for the given pca run """
    data = FuzzyDict(ratdbloader.load_ratdb(os.getcwd() + "/minard/static/pcatellie/pca_constants/PCAGF_" + run_name + "_0.ratdb"))
    data['name'] = run_name
    data['path'] = "/pcatellie/"
    data['status'] = data.pop('PCAGF_status')
    return data

def ccc_from_lcn(lcn):
    """ Return a (crate, card, channel) tuple from the given lcn argument """
    subbits = lambda data, start, count: (data >> start) & ((1 << count) - 1)
    ilcn = int(lcn)
    crate = subbits(ilcn, 9, 5)
    card = subbits(ilcn, 5, 4)
    channel = subbits(ilcn, 0, 5)
    if not ilcn == (512 * crate) + (32 * card) + channel:
        raise ValueError('Unable to parse given LCN "{}"'.format(ilcn))
    return (crate, card, channel)

def load_pca_log_data(run_number):
    """
    Parses PCA LOG file. Creates associated flags. Also created dynamic image for PMTs.
    """
    subview = "log"
    run = get_pca_log(run_number)
    flags = pca_flags.flags[subview]
    status_int = run['status']
    hits = [flag for flag_num, flag in enumerate(flags)
            if status_int & 2**flag_num]

    dynimage = functools.partial(detectorviz.image_for_run_mode_flag,
                                scratch, run, subview, scale=4)
    return run, flags, status_int, hits, dynimage

def load_pca_tw_data(run_number):
    """
    Parses PCA TW file. Creates associated flags. Also created dynamic image for PMTs.
    """
    subview = "tw"
    run = get_pca_tw(run_number)
    flags = pca_flags.flags[subview]
    hits = dict([(flag['bit'], len([None for status
                                    in run['status']
                                    if status & 2**flag['bit'] ]))
                                    for flag in flags])
    dynimage = functools.partial(detectorviz.image_for_run_mode_flag,
                                scratch, run, subview, scale=4)
    return run, flags, hits, dynimage, run_number, subview

def load_pca_gf_data(run_number):
    """
    Parses PCA GF file. Creates associated flags. Also created dynamic image for PMTs.
    """
    subview = "gf"
    run = get_pca_gf(run_number)
    flags = pca_flags.flags[subview]
    hits = dict([(flag['bit'], len([None for status
                                    in run['status']
                                    if status & 2**flag['bit'] ]))
                                    for flag in flags])
    dynimage = functools.partial(detectorviz.image_for_run_mode_flag,
                                scratch, run, subview, scale=4)

    return run, flags, hits, dynimage, run_number, subview

def load_pca_flag_data(view, run_num, flag_i):
    """
    Helper function, creates PCA flag data for specific PCA set.
    Loops through PMTs to obtain status.
    Creates dynamic image.
    """
    flag_num = int(flag_i)
    subview = view
    if view == "gf":
        run = get_pca_gf(run_num)
    else:
        run = get_pca_tw(run_num)
    flag = pca_flags.flags[subview][flag_num]
    pmts = [lcn for lcn, status in enumerate(run['status'])
            if status & 2**flag_num]
    dynimage = functools.partial(detectorviz.image_for_run_mode_flag,
                                 scratch, run, subview, scale=4)
    pmt_ccc = []
    for pmt in pmts:
        pmt_ccc.append( ccc_from_lcn(pmt) )

    return flag, pmts, dynimage, view, run_num, flag_i, pmt_ccc

def load_pca_pmt_data(run, pmt):
    """
    Helper function, creates PMT flag data for specific PCA set.
    Loops through flags to obtain status for particular PMT.
    """
    tw_data = get_pca_tw(run)
    gf_data = get_pca_gf(run)
    tw_status = tw_data['status'][int(pmt)]
    gf_status = gf_data['status'][int(pmt)]
    tw_flags = [flag for flag_num, flag in enumerate(pca_flags.flags['tw'])
                if tw_status & 2**flag_num]
    gf_flags = [flag for flag_num, flag in enumerate(pca_flags.flags['gf'])
                if gf_status & 2**flag_num]
    ccc = ccc_from_lcn(pmt)
    return run, pmt, tw_flags, gf_flags, ccc
