import detector_state
import glob
import os
import re
from redis import Redis
from .views import app

REDIS_SET = "nlrat-runs"
redis = Redis()

RUN_TYPES = {
    0:"Maintenance",
    1:"Transition",
    2:"Physics",
    3:"Deployed Source",
    4:"External Source",
    5:"ECA",
    6:"Diagnostic",
    7:"Experimental",
    8:"Supernova",
    }

@app.template_filter('run_type')
def extract_run_type(run_word):
    '''Get the run type from the run word using RUN_TYPES
    :param int run_word:
    :returns string:
    '''
    for k, v in RUN_TYPES.iteritems():
        if (run_word & (1 << k)):
            return v
    return "Unknown"

def hists_available(run):
    '''Are the histograms for this run available?
    :param int: run number
    :returns bool: true if they are
    '''
    return redis.sismember(REDIS_SET, run)

def available_run_ids():
    '''Get a list of available runs from the redis server
    :returns list(int): in ascending order
    '''
    return sorted([int(x) for x in redis.smembers(REDIS_SET)], reverse=True)
    
def run_time(run):
    '''Get the run start time using the detector state db
    :param int run:
    :returns str: "-" if not found
    '''
    try:
        return detector_state.get_run_state(run)['timestamp'].strftime("%m-%d-%y %H:%M:%S")
    except:
        return "-"

def run_type_word(run):
    '''Get the run start time using the detector state db
    :param int run:
    :returns str: "-" if not found
    '''
    try:
        return detector_state.get_run_state(run)['run_type']
    except:
        return "-"

class Run:
    '''Class to hold run info
    '''
    def __init__(self, id):
        '''
        :param int id:
        :param str time:
        '''
        self.id = id
        self.time = run_time(id)
        self.type = extract_run_type(run_type_word(id))

def available_runs():
    '''Get the runs available, IDs and start times
    :returns list(Run): reverse sorted by ID
    '''
    return [Run(id) for id in available_run_ids()]
