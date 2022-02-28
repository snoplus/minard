import couchdb
from . import app
from .db import engine, engine_nl

def load_pca_runlist():
    """
    Fill this in :)
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

    return results

def load_set(first_run):
    """
    Fill this in :)
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
    Fill this in :)
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
    Fill this in :)
    """
    server = couchdb.Server("http://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])
    db = server["tellie_auto"]

    results = []
    view_string = "runlist"
    for row in db.view('_design/'+view_string+'/_view/'+view_string):
        doc_id = row.id
        try:
            doc = dict(db.get(doc_id).items())
            ind = doc['fibres'].index(fibre)
            run = doc['runlist'][ind]
            results.append( run )
        except KeyError:
            app.logger.warning("Code returned KeyError searching for runlist information in the couchDB. Dod ID: %d" % doc_id)
    return results

def load_limits():
    """
    Fill this in :)
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
    Fill this in :)
    """
    server = couchdb.Server("http://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])
    db = server["tellie_auto"]

    view_string = "benchmark"
    for row in db.view('_design/'+view_string+'/_view/'+view_string):
        doc_id = row.id
        if row.key[0] == run:
            try:
                result = dict(db.get(doc_id).items())
            except KeyError:
                app.logger.warning("Code returned KeyError searching for runlist information in the couchDB. Dod ID: %d" % doc_id)
    return result
