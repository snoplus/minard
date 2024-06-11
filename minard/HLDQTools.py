import couchdb
from minard import app
from .db import engine

#TELLIE Tools
def import_TELLIE_runnumbers(limit=10, offset=0):
    """
    Returns the latest TELLIE runs.
    """
    conn = engine.connect()
    # select all runs which have the external source and tellie bits checked
    result = conn.execute("SELECT run FROM run_state WHERE (run_type & 2064) = 2064 ORDER BY run DESC LIMIT %s OFFSET %s", (limit,offset))
    return [row[0] for row in result.fetchall()]

def import_TELLIEDQ_ratdb(runs):
    if type(runs) == int:
        runs = [runs]

    server = couchdb.Server("http://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])
    db = server["data-quality"]
    data = {}
    checkDict = {}
    runInformationDict = {}
    for row in db.view('_design/data-quality/_view/runs'):
        run = row.key
        if run in runs:
            runDocId = row['id']
            try:
                data[run] = dict(db.get(runDocId)["checks"]["dqtellieproc"])
            except KeyError:
                app.logger.warning("Code returned KeyError searching for dqtellie proc information in the couchDB. Run number: %d" % run)

    if len(data) == 0:
        for i in runs:
            checkDict[i] = -1
            runInformationDict[i] = -1
        return runs, checkDict, runInformationDict

    for run in runs:
        run_dict = {}
        runInformation = {}
        
        try:
            run_dict["fibre"] = data[run]["fibre"]
            #Parameter pulse_delay was renamed to pulse_separation in RAT release 6.16.9
            try:
                run_dict["pulse_delay"] = data[run]["pulse_delay"]
            except KeyError:
                run_dict["pulse_delay"] = data[run]["pulse_separation"]
            run_dict["avg_nhit"] = data[run]["avg_nhit"]
            run_dict["peak_amplitude"] = data[run]["peak_amplitude"]
            run_dict["max_nhit"] = data[run]["max_nhit"]
            run_dict["trigger"] = data[run]["trigger"]
            run_dict["run_length"] = data[run]["run_length"]
            run_dict["peak_number"] = data[run]["peak_number"]
            run_dict["prompt_time"] = data[run]["prompt_time"]
            run_dict["peak_time"] = data[run]["peak_time"]

            checkDict[run] = run_dict

            #Get the runinformation from the tellie dq output
            runInformation["expected_tellie_events"] = data[run]["check_params"]["expected_tellie_events"]
            runInformation["actual_tellie_events"] = data[run]["check_params"]["actual_tellie_events"]
            runInformation["average_nhit"] = data[run]["check_params"]["average_nhit"]
            runInformation["greaterThanMaxNHitEvents"] = data[run]["check_params"]["more_max_nhit_events"]
            runInformation["fibre_firing"] = data[run]["check_params"]["fibre_firing"]
            runInformation["fibre_firing_guess"] = data[run]["check_params"]["fibre_firing_guess"]
            runInformation["peak_number"] = data[run]["check_params"]["peak_numbers"]
            runInformation["prompt_peak_adc_count"] = data[run]["check_params"]["prompt_peak_adc_count"]
            runInformation["pre_peak_adc_count"] = data[run]["check_params"]["pre_peak_adc_count"]
            runInformation["late_peak_adc_count"] = data[run]["check_params"]["late_peak_adc_count"]
            runInformation["subrun_run_times"] = data[run]["check_params"]["subrun_run_times"]
            #Parameter pulse_delay was renamed to pulse_separation in RAT release 6.16.9
            try:
                runInformation["pulse_delay_correct_proportion"]  = data[run]["check_params"]["pulse_delay_efficiency"]
            except KeyError:
                runInformation["pulse_delay_correct_proportion"]  = data[run]["check_params"]["pulse_separation_efficiency"]

            #Run Information for the subruns
            runInformation["subrun_numbers"] = data[run]["check_params"]["subrun_numbers"]
            runInformation["avg_nhit_check_subruns"] = data[run]["check_params"]["avg_nhit_check"]
            runInformation["max_nhit_check_subruns"] = data[run]["check_params"]["max_nhit_check"]
            runInformation["peak_number_check_subruns"] = data[run]["check_params"]["peak_number_check"]
            runInformation["prompt_peak_amplitude_check_subruns"] = data[run]["check_params"]["prompt_peak_amplitude_check"]
            runInformation["prompt_peak_adc_count_check_subruns"] = data[run]["check_params"]["prompt_peak_adc_count_check"]
            runInformation["adc_peak_time_spacing_check_subruns"] = data[run]["check_params"]["adc_peak_time_spacing_check"]
            #Parameter pulse_delay was renamed to pulse_separation in RAT release 6.16.9
            try:
                runInformation["pulse_delay_efficiency_check_subruns"] = data[run]["check_params"]["pulse_delay_efficiency_check"]
            except KeyError:
                runInformation["pulse_delay_efficiency_check_subruns"] = data[run]["check_params"]["pulse_separation_efficiency_check"]
            runInformation["subrun_run_length_check"] = data[run]["check_params"]["subrun_run_length_check"]
            runInformation["correct_fibre_check_subruns"] = data[run]["check_params"]["correct_fibre_check"]
            runInformation["trigger_check_subruns"] = data[run]["check_params"]["trigger_check"]
            runInformationDict[run] = runInformation
        except KeyError as kErr:
            app.logger.warning("When trying to parse the TELLIE HLDQ table could not find the key %s" % kErr.args[0])
            checkDict[run] = -1
            runInformationDict[run] = -1

    return runs, checkDict, runInformationDict

#SMELLIE Tools
def import_SMELLIE_runnumbers(limit=10,offset=0):
    #Returns the latest SMELLIE runs.
    conn = engine.connect()
    # select all runs which have the external source and smellie bits checked
    result = conn.execute("SELECT run FROM run_state WHERE (run_type & 4112) = 4112 ORDER BY run DESC LIMIT %s OFFSET %s", (limit,offset))
    return [row[0] for row in result.fetchall()]

def import_SMELLIEDQ_ratdb(runs):
    if type(runs) == int:
        runs = [runs]

    server = couchdb.Server("http://snoplus:"+app.config["COUCHDB_PASSWORD"]+"@"+app.config["COUCHDB_HOSTNAME"])
    dqDB = server["data-quality"]
    data = {}
    checkDict = {}
    runInformationDict = {}
    for row in dqDB.view('_design/data-quality/_view/runs'):
        run = row.key
        if run in runs:
            runDocId = row['id']
            try:
                data[run] = dict(dqDB.get(runDocId)["checks"]["DQSmellieProc"])
            except KeyError:
                app.logger.warning("Code returned KeyError searching for dqsmellie proc information in the couchDB. Run number: %d" % run)
    if len(data) == 0:
        for i in runs:
            checkDict[i] = -1
            runInformationDict[i] = -1
        return runs, checkDict, runInformationDict

    for run in runs:
        try:
            run_dict = {}
            run_dict["fibre"] = data[run]["smellieCorrectFibre"]
            run_dict["frequency"] = data[run]["smellieFrequencyCheck"]
            run_dict["intensity"] = data[run]["smellieIntensityCheck"]
            run_dict["number_of_events"] = data[run]["smellieNumberOfEventsCheck"]

            checkDict[run] = run_dict

            #Get the runinformation from the smellie dq output
            runInformation = {}
            runInformation["smellie_number_of_events_check_subrun"] = data[run]["check_params"]["smellieNumberOfEventsCheckSubrun"]
            runInformation["expected_smellie_events"] = data[run]["check_params"]["number_events_expected_subrun"]
            runInformation["actual_smellie_events"] = data[run]["check_params"]["events_passing_nhit_and_trigger"]
            
            runInformation["smellie_fibre_bool_subrun"] = data[run]["check_params"]["smellieFibreCheckSubrun"]
            runInformation["smellie_calculated_fibre"] = data[run]["check_params"]["fibre_calculated_subrun"]
            runInformation["smellie_actual_fibre"] = data[run]["check_params"]["fibre_expected_subrun"]
            
            runInformation["frequency_actual_subrun"] = data[run]["check_params"]["frequency_actual_subrun"]
            runInformation["frequency_expected_subrun"] = data[run]["check_params"]["frequency_expected_subrun"]
            runInformation["smellie_frequency_check_subrun"] = data[run]["check_params"]["smellieFrequencyCheckSubrun"]
           
            runInformation["smellie_laser_type"] = data[run]["check_params"]["laser_type"]
            runInformation["smellie_laser_intensity"] = data[run]["check_params"]["laser_intensities"]
            runInformation["smellie_laser_wavelength"] = data[run]["check_params"]["laser_wavelengths"]
            runInformation["smellie_intensity_check_subrun"] = data[run]["check_params"]["smellieIntensityCheckSubrun"]
            runInformation["mean_nhit_smellie_events"] = data[run]["check_params"]["mean_nhit_smellie_trigger_subrun"]
            
            runInformation["nhit_event_no_adjacent_trigger"] = data[run]["check_params"]["nhit_event_no_adjacent_trigger"]
            runInformation["trigger_event_no_adjacent_nhit"] = data[run]["check_params"]["trigger_event_no_adjacent_nhit"]
            runInformation["nhit_event_next_to_trigger_event"] = data[run]["check_params"]["nhit_event_next_to_trigger_event"]
            runInformation["events_failing_nhit_passing_trigger"] = data[run]["check_params"]["events_failing_nhit_passing_trigger"]

            runInformationDict[run] = runInformation
        except KeyError as kErr:
            app.logger.warning("When trying to parse the SMELLIE HLDQ table could not find the key %s" % kErr.args[0])
            checkDict[run] = -1
            runInformationDict[run] = -1

    return runs, checkDict, runInformationDict
