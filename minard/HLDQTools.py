import couchdb
from minard import app
from .db import engine

#
def import_HLDQ_runnumbers(limit=10, offset=0):
    #Returns the latest TELLIE runs.
    conn = engine.connect()
    # select all runs which are physics or supernovae runs
    result = conn.execute("SELECT run FROM run_state WHERE (run_type & 4) = 4 OR (run_type & 256) = 256 ORDER BY run DESC LIMIT %s OFFSET %s", (limit,offset))
    return [row[0] for row in result.fetchall()]

def import_HLDQ_ratdb(runNumber):
    server = couchdb.Server("http://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])
    dqDB = server["data-quality"]
    ratDBDict = -1 
    for row in dqDB.view('_design/data-quality/_view/runs'):
        if(int(row.key) == runNumber):
            runDocId = row['id']
            try:
                ratDBDict = dict(dqDB.get(runDocId))
            except KeyError:
                app.logger.warning("Code returned KeyError searching for dqtellie proc information in the couchDB. Run Number: %d" % runNumber)
    return ratDBDict

#Method to generate pass/fail flags for all processors 
#Code will return a dict of bools indexed by processor name 
#Values will be logical & of all checks.
def generateHLDQProcStatus(ratdbDict):
    procNames = ["dqrunproc","dqtimeproc","dqtriggerproc","dqpmtproc"]
    outDict = {}
    for proc in procNames:
        checkDict = ratdbDict["checks"][proc]
        outDict[proc] = 1
        for entry in checkDict.keys():
            if type(checkDict[entry]) is not dict:
#If a run fails set flag to 0 and break
                if checkDict[entry] == 0:
                    outDict[proc] = 0
                    break
    return outDict



#TELLIE Tools
def import_TELLIE_runnumbers(limit=10, offset=0):
    #Returns the latest TELLIE runs.
    conn = engine.connect()
    # select all runs which have the external source and tellie bits checked
    result = conn.execute("SELECT run FROM run_state WHERE (run_type & 2064) = 2064 ORDER BY run DESC LIMIT %s OFFSET %s", (limit,offset))
    return [row[0] for row in result.fetchall()]

def import_TELLIEDQ_ratdb(runNumber):
    server = couchdb.Server("http://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])
    dqDB = server["data-quality"]
    data = None
    for row in dqDB.view('_design/data-quality/_view/runs'):
        if(int(row.key) == runNumber):
            runDocId = row['id']
            try:
                data = dqDB.get(runDocId)["checks"]["dqtellieproc"]
            except KeyError:
                app.logger.warning("Code returned KeyError searching for dqtellie proc information in the couchDB. Run Number: %d" % runNumber)
                return runNumber, -1, -1 
    if data==None:
        return runNumber, -1, -1 
    
    checkDict = {}
    checkDict["fibre"] = data["fibre"]
    checkDict["pulse_delay"] = data["pulse_delay"]
    checkDict["avg_nhit"] = data["avg_nhit"]
    checkDict["peak_amplitude"] = data["peak_amplitude"]
    checkDict["max_nhit"] = data["max_nhit"]
    checkDict["trigger"] = data["trigger"]
    checkDict["run_length"] = data["run_length"]
    checkDict["peak_number"] = data["peak_number"]
    checkDict["prompt_time"] = data["prompt_time"]
    checkDict["peak_time"] = data["peak_time"]

    #Get the runinformation from the tellie dq output
    runInformation = {}
    runInformation["expected_tellie_events"] = data["check_params"]["expected_tellie_events"]
    runInformation["actual_tellie_events"] = data["check_params"]["actual_tellie_events"]
    runInformation["average_nhit"] = data["check_params"]["average_nhit"]
    runInformation["greaterThanMaxNHitEvents"] = data["check_params"]["more_max_nhit_events"]
    runInformation ["fibre_firing"] = data["check_params"]["fibre_firing"]
    runInformation["fibre_firing_guess"] = data["check_params"]["fibre_firing_guess"]
    runInformation["peak_number"] = data["check_params"]["peak_numbers"]
    runInformation["prompt_peak_adc_count"] = data["check_params"]["prompt_peak_adc_count"]
    runInformation["pre_peak_adc_count"] = data["check_params"]["pre_peak_adc_count"]
    runInformation["late_peak_adc_count"] = data["check_params"]["late_peak_adc_count"]
    runInformation["subrun_run_times"] = data["check_params"]["subrun_run_times"]
    runInformation["pulse_delay_correct_proportion"]  = data["check_params"]["pulse_delay_efficiency"]

    #Run Information for the subruns
    runInformation["subrun_numbers"] = data["check_params"]["subrun_numbers"]
    runInformation["avg_nhit_check_subruns"] = data["check_params"]["avg_nhit_check"]
    runInformation["max_nhit_check_subruns"] = data["check_params"]["max_nhit_check"]
    runInformation["peak_number_check_subruns"] = data["check_params"]["peak_number_check"]
    runInformation["prompt_peak_amplitude_check_subruns"] = data["check_params"]["prompt_peak_amplitude_check"]
    runInformation["prompt_peak_adc_count_check_subruns"] = data["check_params"]["prompt_peak_adc_count_check"]
    runInformation["adc_peak_time_spacing_check_subruns"] = data["check_params"]["adc_peak_time_spacing_check"]
    runInformation["pulse_delay_efficiency_check_subruns"] = data["check_params"]["pulse_delay_efficiency_check"]
    runInformation["subrun_run_length_check"] = data["check_params"]["subrun_run_length_check"]
    runInformation["correct_fibre_check_subruns"] = data["check_params"]["correct_fibre_check"]
    runInformation["trigger_check_subruns"] = data["check_params"]["trigger_check"]

    return runNumber, checkDict, runInformation

#SMELLIE Tools
def import_SMELLIE_runnumbers(limit=10,offset=0):
    #Returns the latest SMELLIE runs.
    conn = engine.connect()
    # select all runs which have the external source and tellie bits checked
    result = conn.execute("SELECT run FROM run_state WHERE (run_type & 4112) = 4112 ORDER BY run DESC LIMIT %s OFFSET %s", (limit,offset))
    return [row[0] for row in result.fetchall()]

def import_SMELLIEDQ_ratdb(runNumber):
    server = couchdb.Server("http://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])
    dqDB = server["data-quality"]
    data = None
    for row in dqDB.view('_design/data-quality/_view/runs'):
        if(int(row.key) == runNumber):
            runDocId = row['id']
            try:
                data = dqDB.get(runDocId)["checks"]["DQSmellieProc"]
            except KeyError:
                app.logger.warning("Code returned KeyError searching for dqsmellie proc information in the couchDB. Run Number: %d" % runNumber)
                return runNumber, -1, -1 
    if data==None:
        return runNumber, -1, -1 
    
    checkDict = {}
    checkDict["fibre"] = data["smellieCorrectFibre"]
    checkDict["frequency"] = data["smellieFrequencyCheck"]
    checkDict["intensity"] = data["smellieIntensityCheck"]
    checkDict["number_of_events"] = data["smellieNumberOfEventsCheck"]

    #Get the runinformation from the tellie dq output
    runInformation = {}
    runInformation["smellie_number_of_events_check_subrun"] = data["check_params"]["smellieNumberOfEventsCheckSubrun"]
    runInformation["expected_smellie_events"] = data["check_params"]["number_events_expected_subrun"]
    runInformation["actual_smellie_events"] = data["check_params"]["events_passing_nhit_and_trigger"]
    
    runInformation["smellie_fibre_bool_subrun"] = data["check_params"]["smellieFibreCheckSubrun"]
    runInformation["smellie_calculated_fibre"] = data["check_params"]["fibre_calculated_subrun"]
    runInformation["smellie_actual_fibre"] = data["check_params"]["fibre_expected_subrun"]
    
    runInformation["frequency_actual_subrun"] = data["check_params"]["frequency_actual_subrun"]
    runInformation["frequency_expected_subrun"] = data["check_params"]["frequency_expected_subrun"]
    runInformation["smellie_frequency_check_subrun"] = data["check_params"]["smellieFrequencyCheckSubrun"]
   
    runInformation["smellie_laser_type"] = data["check_params"]["laser_type"]
    runInformation["smellie_laser_intensity"] = data["check_params"]["laser_intensities"]
    runInformation["smellie_laser_wavelength"] = data["check_params"]["laser_wavelengths"]
    runInformation["smellie_intensity_check_subrun"] = data["check_params"]["smellieIntensityCheckSubrun"]
    runInformation["mean_nhit_smellie_events"] = data["check_params"]["mean_nhit_smellie_trigger_subrun"]
    
    runInformation["nhit_event_no_adjacent_trigger"] = data["check_params"]["nhit_event_no_adjacent_trigger"]
    runInformation["trigger_event_no_adjacent_nhit"] = data["check_params"]["trigger_event_no_adjacent_nhit"]
    runInformation["nhit_event_next_to_trigger_event"] = data["check_params"]["nhit_event_next_to_trigger_event"]
    runInformation["events_failing_nhit_passing_trigger"] = data["check_params"]["events_failing_nhit_passing_trigger"]
    return runNumber, checkDict, runInformation
