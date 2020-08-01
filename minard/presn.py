import couchdb
from . import app

def load_presn_runs(offset, limit):
    """
    Returns a dictionary with the burst runs loaded from couchdb. The dummy itterator is used as key
    to keep the ordering from the couchdb query. The content of the couchdb document is stored as values.
    This loads ALL the documents in burst database, ordered by run_subrun_burst logic.
    The logic to limit and split the results per page was implemented.
    """
    #server = couchdb.Server("http://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])
    server = couchdb.Server("http://admin:janetscouchdbpassword@127.0.0.1:5984")
    #db = server["burst"]
    db = server["pre-supernova"]

    results = []
    skip = offset
    #all = db.view('_design/burst/_view/burst_by_run', descending=True, skip=skip)
    all = db.view('_design/presn/_view/presn_by_run', descending=True, skip=skip)
    total = all.total_rows
    offset = all.offset
    for row in db.view('_design/presn/_view/presn_by_run', descending=True, limit=limit, skip=skip):
        run = row.key[0]
        run_id = row.id
        try:
            results.append(dict(db.get(run_id).items()))
        except KeyError:
            app.logger.warning("Code returned KeyError searching for burst information in the couchDB. Run Number: %d" % run)

    return results, total, offset, limit

#def presn_run_detail(run_number, subrun, sub):
def presn_run_detail(run_number, subrun):
    """
    Returns a dictionary that is a copy of the couchdb document for specific run_subrun_burst.
    """
    #server = couchdb.Server("http://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])
    #db = server["burst"]
    server = couchdb.Server("http://admin:janetscouchdbpassword@127.0.0.1:5984")
    db = server["pre-supernova"]

    startkey = [run_number, subrun]
    endkey = [run_number, subrun]
    rows = db.view('_design/presn/_view/presn_by_run', startkey=startkey, endkey=endkey, descending=False, include_docs=True)
    for row in rows:
        run_id = row.id
        try:
            result = dict(db.get(run_id).items())
        except KeyError:
            app.logger.warning("Code returned KeyError searching for burst_details information in the couchDB. Run Number: %d" % run_number)
        #files = "%i_%i" % (run_number,subrun)
        files = "%i" %(run_number)
        
    return result, files

def load_presn_search(search, start, end, offset, limit):
    """
    Returns a dictionary with the burst runs loaded from couchdb.
    The returned dictionary is given by one of the search conditions on the page:
    either by run, date or GTID which all use corresponding couchdb views.
    """
    #server = couchdb.Server("http://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])
    #db = server["burst"]
    server = couchdb.Server("http://admin:janetscouchdbpassword@127.0.0.1:5984")
    db = server["pre-supernova"]
    
    results = []
    skip = offset

    if search == "run":

        startkey = [int(start), 0, {}]
        endkey = [int(end), {}]

        view = '_design/presn/_view/presn_by_run'

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

        view = '_design/presn/_view/presn_by_date'
    # Not yet implemented gtid search
    elif search == "gtid":

        view = '_design/burst/_view/burst_by_date_GTID'

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
    # Not yet implemented gtid for preSN
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
