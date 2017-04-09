import couchdb
from minard import app
import os
import json

#
def import_HLDQ_runnumbers():
    runNumbers = []
    DQHL_DIR = os.path.join(app.static_folder,"hldq/DQHL")
    for folds in os.listdir(DQHL_DIR):
        runNum = int(folds.split("_")[-1])
        runNumbers.append(runNum)
    
    return runNumbers

def import_HLDQ_ratdb(runNumber):
    runFolder = os.path.join(app.static_folder,"hldq/DQHL")
    runFolder = os.path.join(runFolder,"DQHL_%s" % runNumber)
    ratdbFile = ""
    for fil in os.listdir(runFolder):
        if fil.endswith(".ratdb") and "DATAQUALITY_RECORDS" in fil:
            ratdbFile = os.path.join(runFolder,fil)
            break
    ratDBDict = json.load(open(ratdbFile,"r"))
    print(ratDBDict)
    return ratDBDict


#TELLIE Tools
def import_TELLIE_runnumbers():
    server = couchdb.Server("http://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])
    tellieDB = server["telliedb"]
    runNumbers = []
    for row in tellieDB.view('_design/ratdb/_view/select_time'):
        if row.key[0] != "TELLIE_RUN":
            continue
        runDocId = row['id']
        #Skip TELLIE runs where TELLIE hasn't been fired.
        if len(tellieDB.get(runDocId)["sub_run_info"]) == 0:
            continue
        runNum = int(row.key[1])
        if runNum not in runNumbers:
            runNumbers.append(runNum)
    return runNumbers

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
