import couchdb
from itertools import groupby
from .views import app
from uuid import uuid4

def get_standard_runs():
    couch = couchdb.Server("https://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])
    orca_db = couch['orca']
    sr_view = orca_db.view("standardRuns/getStandardRunsWithVersion")
    # standard run keys are [doc-version, run name, run version, timestamp]
    # I want to groupby by run name then within that group all run versions sorted
    # by timestamp
    rows = sorted(sr_view.rows, key=lambda x: x.key[1] + x.key[2])
    groups = groupby(rows, lambda x: x.key[1] + x.key[2])
    groups = [(x, list(y)) for x, y in groups]
    runs = [max(group, key=lambda x: x.key[3]) for _, group in groups]
    runs = sorted(runs, key=lambda x: x.key[1])
    runs = [(x, list(y)) for x,y in groupby(runs, lambda x: x.key[1])]
    return runs

def get_standard_run(uuid):
    couch = couchdb.Server("https://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])
    orca_db = couch['orca']
    return orca_db.get(uuid)

def update_standard_run(uuid, new_values):
    couch = couchdb.Server("https://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])
    orca_db = couch['orca']
    doc = dict(orca_db.get(uuid))
    for k, v in new_values.iteritems():
        doc[k] = v
    doc["_id"] = uuid4().hex
    del doc["_rev"]
    new_uuid, _ = orca_db.save(doc)
    return new_uuid
