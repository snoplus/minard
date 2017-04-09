import couchdb
from minard import app
import json
import os

def import_HLDQ_runnumbers():
    server = couchdb.Server("http://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])
    dqDB = server["data-quality"]
    runNumbers = []
    for row in tellieDB.view('_design/data-quality/_view/runs'):
        runNum = int(row)
        if runNum not in runNumbers:
            runNumbers.append(runNum)
    return runNumbers


#TELLIE Tools
def import_TELLIE_runnumbers():
    runNumbers = []
    imagesDir = os.path.join(app.static_folder,"hldq/TELLIE/")
    for folds in os.listdir(imagesDir):
        if not "TELLIE_DQ_IMAGES" in folds:
            continue
        runNum = int(folds.split("_")[-1])
        runNumbers.append(runNum)
    return runNumbers
                            
def import_TELLIEDQ_ratdb(runNumber):
    imagesFolder = os.path.join(app.static_folder,"hldq/TELLIE/TELLIE_DQ_IMAGES_%d"%runNumber)
    for fil in os.listdir(imagesFolder):
        if "DATAQUALITY_RECORDS" in fil:
            dqfile = os.path.join(imagesFolder,fil)
            break
    with open(dqfile,"r") as fil:
        data = json.load(fil)["checks"]["dqtellieproc"]
    
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
