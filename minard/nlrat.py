import detector_state
import glob
import os
import re

NLRAT_DIR = "/Users/Jack/snoplus/nearline/clients/nlrat/output"

def hists_available(run):
    '''Are the histograms for this run available?
    :param int: run number
    :returns bool: true if they are
    '''
    return os.path.isfile(os.path.join(NLRAT_DIR, "r{0}_nl_th1f.root".format(run)));

def extract_run_num(file_path):
    '''Get the run number from a file path to nlrat histogram file
    :param str file_path:
    :returns int:
    '''
    mtch = re.match(r"^r(\d+)_nl_th1f.root$", file_path)
    if mtch is None:
        return None
    return mtch.group(1)

def available_run_ids():
    '''Get a list of available runs
    :returns list(int): in descending order
    '''
    nums = [extract_run_num(os.path.basename(x)) for x in glob.glob(os.path.join(NLRAT_DIR, "*"))]
    return sorted([x for x in nums if x is not None], reverse=True)
    
def run_time(run):
    '''Get the run start time using the detector state db
    :param int run:
    :returns str: "" if not found
    '''
    try:
        #        return detector_state.get_run_state(run)['timestamp'].isoformat()
        return "the time"
    except:
        return ""

class Run:
    '''Class to hold run info
    '''
    def __init__(self, id, time):
        '''
        :param int id:
        :param str time:
        '''
        self.id = id
        self.time = time
        
def available_runs():
    '''Get the runs available, IDs and start times
    :returns list(Run): reverse sorted by ID
    '''
    return [Run(id, run_time(id)) for id in available_run_ids()]
