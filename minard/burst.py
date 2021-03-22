import couchdb
from . import app
from .db import engine, engine_nl
from time import strftime
from datetime import datetime
import calendar

def load_burst_runs(offset, limit, level=2):
    """
    Returns a dictionary with the burst runs loaded from couchdb. The dummy itterator is used as key
    to keep the ordering from the couchdb query. The content of the couchdb document is stored as values.
    This loads ALL the documents in burst database, ordered by run_subrun_burst logic.
    The logic to limit and split the results per page was implemented.
    """
    server = couchdb.Server("http://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])
    if level==3:
        db = server["burst_cleaning"]
        view_string = "burst_cleaning"
    else:
        db = server["burst"]
        view_string = "burst"

    results = []
    skip = offset
    all = db.view('_design/'+view_string+'/_view/burst_by_run', descending=True, skip=skip)
    total = all.total_rows
    offset = all.offset
    for row in db.view('_design/'+view_string+'/_view/burst_by_run', descending=True, limit=limit, skip=skip):
        run = row.key[0]
        run_id = row.id
        try:
            results.append(dict(db.get(run_id).items()))
        except KeyError:
            app.logger.warning("Code returned KeyError searching for burst information in the couchDB. Run Number: %d" % run)

    return results, total, offset, limit

def burst_run_detail(run_number, subrun, sub, level=2):
    """
    Returns a dictionary that is a copy of the couchdb document for specific run_subrun_burst.
    """
    server = couchdb.Server("http://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])
    if level==3:
        db = server["burst_cleaning"]
        view_string = "burst_cleaning"
    else:
        db = server["burst"]
        view_string = "burst"

    startkey = [run_number, subrun, sub]
    endkey = [run_number, subrun, sub]
    rows = db.view('_design/'+view_string+'/_view/burst_by_run', startkey=startkey, endkey=endkey, descending=False, include_docs=True)
    for row in rows:
        run_id = row.id
        try:
            result = dict(db.get(run_id).items())
        except KeyError:
            app.logger.warning("Code returned KeyError searching for burst_details information in the couchDB. Run Number: %d" % run_number)
        files = "%i_%i_%i" % (run_number,subrun,sub)

    return result, files

def load_bursts_search(search, start, end, offset, limit, level=2):
    """
    Returns a dictionary with the burst runs loaded from couchdb.
    The returned dictionary is given by one of the search conditions on the page:
    either by run, date or GTID which all use corresponding couchdb views.
    """
    server = couchdb.Server("http://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])

    if level==3:
        db = server["burst_cleaning"]
        view_string = "burst_cleaning"
    else:
        db = server["burst"]
        view_string = "burst"

    results = []
    skip = offset

    if search == "run":

        startkey = [int(start), 0, 0]
        endkey = [int(end), {}]
        view = '_design/'+view_string+'/_view/burst_by_run'

    elif search == "date":

        start_year = start[0:4]
        start_month = start[5:7]
        start_day = start[8:10]
        end_year = end[0:4]
        end_month = end[5:7]
        end_day = end[8:10]
        if start_month[0] == "0":
            start_month = start_month[1]
        if end_month[0] == "0":
            end_month = end_month[1]
        if start_day[0] == "0":
            start_day = start_day[1]
        if end_day[0] == "0":
            end_day = end_day[1]
        startkey = [int(start_year), int(start_month), int(start_day)]
        endkey = [int(end_year), int(end_month), int(end_day)]

        view = '_design/'+view_string+'/_view/burst_by_date'

    elif search == "gtid":
        view = '_design/'+view_string+'/_view/burst_by_date_GTID'

    if search == "run" or search == "date":
        try:
            all = db.view(view, startkey=startkey, endkey=endkey, descending=False)
            total = len(all.rows)
        except:
            app.logger.warning("Code returned KeyError searching for burst information in the couchDB.")

        for row in db.view(view, startkey=startkey, endkey=endkey, descending=False, skip=skip, limit=limit):
            if search == "run":
                run = row.key[0]
            elif search == "date":
                run = row.value[0]
            run_id = row.id
            try:
                results.append(dict(db.get(run_id).items()))
            except KeyError:
                app.logger.warning("Code returned KeyError searching for burst information in the couchDB. Run Number: %d" % run)

        return results, total, offset, limit

    elif search == "gtid": ### this needs to loop through all documents (no start-end key) because we want GTID in range of start/end GTID

        for row in db.view(view, descending=True, limit=1000):   ### limiting search to last 1000 entries by date
            startgtid = int(row.value[3])
            endgtid = int(row.value[4])

            if endgtid < startgtid: ### case for gtid roll-over
                if ( (int(start) >= startgtid) and (int(start) <= pow(2,24)) ) or ( (int(end) <= endgtid) and (int(end) >= 0 ) ):
                    run = row.value[0]
                    run_id = row.id

                    try:
                        results.append(dict(db.get(run_id).items()))
                    except KeyError:
                        app.logger.warning("Code returned KeyError searching for burst information in the couchDB. Run Number: %d" % run)
            else:
                if (int(start) >= startgtid) and (int(end) <= endgtid):
                    run = row.value[0]
                    run_id = row.id

                    try:
                        results.append(dict(db.get(run_id).items()))
                    except KeyError:
                        app.logger.warning("Code returned KeyError searching for burst information in the couchDB. Run Number: %d" % run)
            total = len(results)

        return results, total, 0, 100

def burst_get_cuts():
    """
    Returns a dictionary of cleaning cuts that are applied, loaded from specific couchdb document.
    """
    data=[[],[]]
    server = couchdb.Server("http://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])
    db = server["burst_cleaning"]

    rows = db.view('_design/burst_cleaning/_view/cuts', descending=False, include_docs=True)
    for row in rows:
        doc_id = row.id
        try:
            result = dict(db.get(doc_id).items())
            key_list = list(result.keys())
            val_list = list(result.values())
            for i in range (0,len(key_list)-1):
                if key_list[i] not in ["_rev", "_id", "type"]:
                    if val_list[i] == 1:
                        data[0].append( key_list[i] )
                    else:
                        data[1].append( key_list[i] )

        except KeyError:
            app.logger.warning("Code returned KeyError searching for cut document in the couchDB.")

    return data

def burst_form_upload(run_number, subrun, sub, tick, summary, note, name):
    """
    Uploads checkbox value and note field to appropriate couchdb document - this is for SN burst review.
    """
    server = couchdb.Server("http://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])
    db = server["burst_cleaning"]

    startkey = [run_number, subrun, sub]
    endkey = [run_number, subrun, sub]
    rows = db.view('_design/burst_cleaning/_view/burst_by_run', startkey=startkey, endkey=endkey, descending=False, include_docs=True)
    for row in rows:
        run_id = row.id
        try:
            doc = dict(db.get(run_id).items())
        except KeyError:
            app.logger.warning("Code returned KeyError searching for burst_details information in the couchDB. Run Number: %d" % run_number)
        try:
            doc["checked"] = tick
            doc["summary"] = summary
            doc["note"] = note
            doc["reviewed_by"] = name
            date = datetime.today().strftime("%d-%m-%Y")
            time = datetime.today().strftime("%H:%M:%S")
            month = calendar.month_abbr[int(date.split('-')[1])]
            final_date = date.split('-')[0] + "-" + month + "-" + date.split('-')[2]
            doc["review_date"] = final_date
            doc["review_time"] = time
            db.save(doc)
        except KeyError:
            app.logger.warning("Code returned KeyError appending to couchDB document. Doc ID: %s" % run_id)

    return 1

def get_run_type(run):
    """
    Tries to retrieve run type from postgresql, then manipulates into user readable strings.
    Returns array of strings for Run type, Calibration type, Bits.
    """
    trans_map = {
        0: "Maintenance",
        1: "Transition",
        2: "Physics",
        3: "Deployed Source",
        4: "External Source",
        5: "ECA",
        6: "Diagnostic",
        7: "Experimental",
        8: "Supernova",
        11:"TELLIE",
        12:"SMELLIE",
        13:"AMELLIE",
        14:"PCA",
        15:"ECA Pedestal",
        16:"ECA Time Slope",
        21:"DCR Activity",
        22:"Compensation Coils Off",
        23:"PMTS Off",
        24:"Bubblers On",
        25:"Cavity Recirculation ON",
        26:"SL Assay",
        27:"Unusual Activity",
        28:"AV Recirculation ON",
        29:"Scint. Fill"
    }

    conn = engine.connect()
    run_string = ""
    try:
        result = conn.execute("SELECT run_type FROM run_state WHERE run = %s", run)
        runtype = result.fetchone()
        run_string = ""

        if runtype is not None:
            runtype = runtype[0]
            for i in range(30):
                if (runtype & (1<<i)):
                    if i not in trans_map:
                        run_string += "SPARE"
                    else:
                        run_string += str(trans_map[i])
                    run_string += ", "
            run_string = run_string[:-2]
    except KeyError:
        run_string = ""

    return run_string
