import couchdb
from . import app
from datetime import datetime, timedelta

def load_presn_runs(offset, limit):
    """
    Returns a dictionary with the pre-supernova runs loaded from couchdb. 
    The dummy itterator is used as key
    to keep the ordering from the couchdb query. The content of the couchdb document is 
    stored as values.
    This loads ALL the documents in pre-supernova database, ordered by run logic, 
    but only documents with dates within 100 hours of the search time are shown.
    The logic to limit and split the results per page was implemented.
    """
    now_local = datetime.now()
    timelimit = timedelta(hours=100)
    server = couchdb.Server("http://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])
    db = server["pre-supernova"]
    results = []
    skip = offset
    all = db.view('_design/presn/_view/presn_by_date_run', descending=True, skip=skip)
    total = all.total_rows
    offset = all.offset
    for row in db.view('_design/presn/_view/presn_by_date_run', descending=True, limit=limit, skip=skip):
        year = row.key[0]
        mon = row.key[1]
        day = row.key[2]
        hour = row.key[3]
        minute = row.key[4]
        sec = row.key[5]
        run = row.value
        run_id = row.id
        runtime=datetime(year, mon, day, hour, minute, sec)
        timediff = now_local - runtime
        if timediff<timelimit:
            try:
                results.append(dict(db.get(run_id).items()))
            except KeyError:
                app.logger.warning("Code returned KeyError searching for presn information in the couchDB. Run Number: %d" % run)
    results.sort(reverse=True)
    return results, total, offset, limit

def load_presn_search(search, start, end, offset, limit):
    """
    Returns a dictionary with the pre-supernova runs loaded from couchdb.
    The returned dictionary is given by one of the search conditions on the page:
    either by run or date. There is a time limit such that tables for runs beyond 
    100 hours of the current time cannot be accessed by minard.
    """
    now_local = datetime.now()
    timelimit = timedelta(hours=100)
    server = couchdb.Server("http://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])
    db = server["pre-supernova"]
    
    results = []
    skip = offset

    if search == "run":
        startkey = [int(start)]
        endkey = [int(end)]
        view = '_design/presn/_view/presn_by_run_date'

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
        view = '_design/presn/_view/presn_by_date_run'
      
    if search == "run":
        try:
            all = db.view(view, startkey=startkey, endkey=endkey, descending=False)
            total = len(all.rows)
            print "OK, run gives us", total
            print all
        except:
            app.logger.warning("Code returned KeyError searching for presn information in the couchDB.")

        for row in db.view(view, startkey=startkey, endkey=endkey, descending=False, skip=skip, limit=limit):
            try:
                year = row.value[0]
                mon = row.value[1]
                day = row.value[2]
                hour = row.value[3]
                minute = row.value[4]
                sec = row.value[5]
                runtime=datetime(year, mon, day, hour, minute, sec)
                timediff = now_local - runtime
                run = row.key
                run_id = row.id
                if timediff<timelimit:
                    results.append(dict(db.get(run_id).items()))
            except KeyError:
                app.logger.warning("Code returned KeyError searching for presn information in the couchDB. Run Number: %d" % run)

    elif search == "date":
        try:
            all = db.view(view, startkey=startkey, endkey=endkey, descending=False)
            total = len(all.rows)
        except:
            app.logger.warning("Code returned KeyError searching for presn information in the couchDB.")

        for row in db.view(view, startkey=startkey, endkey=endkey, descending=False, skip=skip, limit=limit):
            try:
                year = row.key[0]
                mon = row.key[1]
                day = row.key[2]
                hour = row.key[3]
                minute = row.key[4]
                sec = row.key[5]
                runtime=datetime(year, mon, day, hour, minute, sec)
                timediff = now_local - runtime
                run = row.value
                run_id = row.id
                if timediff<timelimit:
                    results.append(dict(db.get(run_id).items()))
            except KeyError:
                app.logger.warning("Code returned KeyError searching for presn information in the couchDB. Run Number: %d" % run)
    return results, total, offset, limit

def presn_run_detail(run_number):
    """
    Returns a dictionary that is a copy of the couchdb document for a specific run.
    """
    server = couchdb.Server("http://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])
    db = server["pre-supernova"]

    startkey = run_number
    endkey = run_number
    rows = db.view('_design/presn/_view/presn_by_run_only', startkey=startkey, endkey=endkey, descending=False, include_docs=True)
    for row in rows:
        run_id = row.id
        try:
            result = dict(db.get(run_id).items())
        except KeyError:
            app.logger.warning("Code returned KeyError searching for presn_details information in the couchDB. Run Number: %d" % run_number)
        files = "%i" %(run_number)
        
    return result, files
