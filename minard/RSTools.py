from wtforms import Form, BooleanField, StringField, PasswordField, validators
from .db import engine, engine_nl
from collections import OrderedDict
import psycopg2
import psycopg2.extras
from datetime import datetime
from dateutil import tz, parser
import numpy as np
import pytz
from .views import app

def file_list_form_builder(formobj, runlists, data):
    class FileListForm(Form):
        pass

    for (i, listname) in enumerate(runlists.keys()):
        listnum = runlists[listname]
        if listnum in data and formobj == -1:
            setattr(FileListForm, '%s' % listname, BooleanField(label=listname, default='checked'))
        else:
            setattr(FileListForm, '%s' % listname, BooleanField(label=listname))

        setattr(FileListForm, 'name', StringField('Name', [validators.Length(min=1), validators.InputRequired(), validators.Regexp('[A-Za-z0-9\s]{1,}', message='First and second name required.')]))
        setattr(FileListForm, 'comment', StringField('Comment', [validators.InputRequired()]))
        setattr(FileListForm, 'password', PasswordField('Password', [validators.InputRequired()]))

    if formobj != -1:
        return FileListForm(formobj)
    else:
        return FileListForm()

def get_current_lists_run(run):
    conn = engine.connect()
    result = conn.execute("SELECT list FROM evaluated_runs WHERE run={}".format(run))
    return [int(row[0]) for row in result.fetchall()]

def get_run_lists():
    conn = engine.connect()
    result = conn.execute("SELECT name, id FROM run_lists ORDER BY name ASC")
    data = OrderedDict()
    for entry in result.fetchall():
        data[str(entry[0])] = int(entry[1])
    conn.close()
    return data

def get_timestamp(local_tz=None, local=False, iso=False):
    if local_tz is None:
        local_tz = 'UTC'

    lcl_time = datetime.now(pytz.timezone(local_tz))
    utc_time = lcl_time.astimezone(pytz.utc)


    if local:
        timestamp = lcl_time
    else:
        timestamp = utc_time

    if iso:
        return timestamp.isoformat()
    else:
        return timestamp

def writeNewLists(inputTable, form, added, removed):
    newTable = inputTable
    newTable["pass"] += 1
    newTable["timestamp"] = get_timestamp(iso=True)
    newTable["name"] = form.name.data
    newTable["comment"] = form.comment.data
    if added: 
        newTable["list_added"] = [v for v in added]
    else:
        newTable["list_added"] = []
    if removed:
        newTable["list_removed"] = [v for v in removed]
    else:
        newTable["list_removed"] = []
    
    return newTable

def get_list_history(run):
    """
    Get run list history for this run.
    """
    # key | run | uploaded_to | removed_from | name | timestamp | comment
    conn = engine.connect()
    result = conn.execute("SELECT timestamp, uploaded_to, removed_from, comment, name FROM rs_history WHERE run={} ORDER BY timestamp DESC".format(int(run)))
    data = OrderedDict()
    for i, entry in enumerate(result.fetchall()):
        data[str(i)] = {}
        data[str(i)]['timestamp'] = str(entry[0])
        data[str(i)]['list_added'] = str(entry[1])
        data[str(i)]['list_removed'] = str(entry[2])
        data[str(i)]['comment'] = str(entry[3])
        data[str(i)]['name'] = str(entry[4])
    conn.close()
    return data

def update_run_lists(form, run, lists, data):
    """
    First update the run lists, then update the tables with new comment and timestamp, and finally
    update the rs_history tables.
    """

    # Remove troublesome characters from entries
    name = str(form.name.data).replace("'", '').replace('"', '')
    comment = str(form.comment.data).replace("'", '').replace('"', '')

    # Connect to detector database, to update run lists and run list histories
    conn = psycopg2.connect(dbname=app.config['DB_NAME'],
                            user=app.config['DB_USER_EXPERT'],
                            host=app.config['DB_HOST'],
                            password=form.password.data)
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

    cursor = conn.cursor()
    for key in dir(form):
        if key in lists:
            if (getattr(form, key).data == True and lists[key] not in data): # need new entry
                # Add run to run list
                result = cursor.execute("INSERT INTO evaluated_runs(run, list, evaluator) VALUES({},{},'{}')".format(int(run), int(lists[key]), name))
                # Update run history
                result = cursor.execute("INSERT INTO rs_history(run,uploaded_to,removed_from,name,comment) VALUES({},'{}',NULL,'{}','{}')".format(int(run), str(key), name, comment))
            elif (getattr(form, key).data == False and lists[key] in data): # need to delete entry
                # Remove run from run list
                result = cursor.execute("DELETE FROM evaluated_runs WHERE run = {} AND list = {}".format(int(run), int(lists[key])))
                # Update run history
                result = cursor.execute("INSERT INTO rs_history(run,uploaded_to,removed_from,name,comment) VALUES({},NULL,'{}','{}','{}')".format(int(run), str(key), name, comment))
    
    """
    Now, update the nearlineDB with the name and time
    """

    conn_nl = psycopg2.connect(dbname=app.config['DB_NAME_NEARLINE'],
                               user="snotdaq",
                               host=app.config['DB_HOST_NEARLINE'],
                               password=app.config['DB_EXPERT_PASS_NEARLINE'],
                               port=app.config['DB_PORT_NEARLINE'])
    conn_nl.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

    cursor_nl = conn_nl.cursor()
    result_nl = cursor_nl.execute("UPDATE run_selection SET name=%s WHERE run_min=%s AND run_max=%s AND type='RS_REPORT'", (form.name.data, run, run))

    conn_nl.close()


def decide_replace_table(first_table, second_table, version=None):
    '''Decide whether second_table should replace first_table, first based on version
    number, then on timestamp'''

    if second_table['meta_data']['version'] == first_table['meta_data']['version']:
        # Current table and saved one have the same version, so compare times
        first_time = parser.isoparse(str(first_table['timestamp']).replace(' ', 'T', 1))
        second_time = parser.isoparse(str(second_table['timestamp']).replace(' ', 'T', 1))
        if second_time > first_time:
            return True
        else:
            return False

    # Versions are different, see if any match the provided one
    if version is not None:
        if first_table['meta_data']['version'] == version:
            return False
        if second_table['meta_data']['version'] == version:
            return True
    
    # No version match provided one (or none provided), to take table with latest version
    if second_table['meta_data']['version'] > first_table['meta_data']['version']:
        return True
    else:
        return False

############ RUNSELECTION PAGE FUNCTIONS ############

def get_RS_reports(criteria=None, run_min=None, run_max=None, limit=None):
    '''Get run-selection tables in a run range. If duplicate tables, only keeps one
    (takes one with latest version, and if they have the same version, the one with
    the latest timestamp).'''

    # Get tables in descending order, with hardcoded max at 100 to avoid slow down if misused
    query = "SELECT meta_data, name, timestamp FROM run_selection WHERE type = 'RS_REPORT'".format(criteria)
    conditions = []
    if criteria is not None:
        conditions.append("criteria = '{}'".format(str(criteria)))
    if run_min is not None:
        conditions.append("run_min >= {}".format(int(run_min)))
    if run_max is not None:
        conditions.append("run_max <= {}".format(int(run_max)))

    if len(conditions) > 0:
        for i in range(0, len(conditions)):
            query += " AND " + conditions[i]

    query += " ORDER BY run_min DESC"
    if limit is not None:
        query += " LIMIT {}".format(limit)

    conn = engine_nl.connect()
    resultQuery = conn.execute(query)

    rs_tables_list = []
    for row in resultQuery.fetchall():
        tempt_dict = {}
        tempt_dict['meta_data'] = row[0]
        tempt_dict['name'] = row[1]
        tempt_dict['timestamp'] = row[2]
        rs_tables_list.append(tempt_dict)

    if len(rs_tables_list) == 0:
        print("ERROR: No RS table found for criteria tag '{}', run min {} and run_max {}, ".format(criteria, run_min, run_max))
        return False
    
    # Repackage and check for duplicates
    rs_tables = {}
    for table in rs_tables_list:
        run_number = table['meta_data']['run_range'][0]
        criteria = table['meta_data']['index']
        if run_number not in rs_tables:
            rs_tables[run_number] = {}
            rs_tables[run_number][criteria] = table
        else:
            if criteria not in rs_tables[run_number]:
                rs_tables[run_number][criteria] = table
            else:
                # There is a duplicate
                if decide_replace_table(rs_tables[run_number][criteria], table):
                    rs_tables[run_number][criteria] = table

    return rs_tables

def get_filtered_RS_tables(run_max, offset, limit, result, criteria):
    '''Download run-selection tables in range, and keep only ones with desired result'''

    # Download a few more runs than limit, in case some don't meet conditions
    rs_tables = get_RS_reports(criteria=criteria, run_max=run_max, limit = (offset + limit) * 2, table_type='RS_REPORT')
    if rs_tables is False:
        return False, True

    no_more_tables = False
    if len(rs_tables) < ((offset + limit) * 2):
        no_more_tables = True

    ### Check conditions ###

    # In RS tables, the final result is written as True if it passed,
    # False if it failed, and None if it was purgatoried.
    resultMapping = {'Pass': True, 'Purgatory': None, 'Fail': False}

    # We only want to display runs with the specified result
    if result != 'All':
        filtered_rs_tables = rs_tables
    else:
        filtered_rs_tables = {}
        for run_number in rs_tables:
            if rs_tables[run_number][criteria]['meta_data']['decision']['result'] == resultMapping[result]:
                filtered_rs_tables[run_number] = rs_tables[run_number]

    return filtered_rs_tables, no_more_tables

def list_runs_info(limit, offset, result, criteria):
    '''Want a list of runs that satisfy condition from (latest run - offset)
    to (latest run - offset - limit). Where the runs considered here are only
    those that satisfy the conditions (i.e. we always want to display a number
    of runs = limit, no matter the conditions.'''

    # Get filtered runs (download twice as many runs as needed, then filter by result)
    filtered_rs_tables, no_more_tables = get_filtered_RS_tables(None, offset, limit, result, criteria)
    if filtered_rs_tables is False:
        print('WARNING: No runs found for limit {}, offset {}, result {} and criteria {}'.format(limit, offset, result, criteria))
        return False

    # If there aren't enough, keep downloading more runs until we get enough. Either until enough
    # are downloaded, or there are no more tables to download, or reach a hard cap in number of loops (just in case).
    num_loops = 0
    while (len(filtered_rs_tables) <= (offset + limit)) and (no_more_tables == False) and (num_loops <= 100):
        earliest_run = filtered_rs_tables[-1]['meta_data']['run_range'][0]
        new_filtered_rs_tables, no_more_tables = get_filtered_RS_tables(earliest_run-1, offset, limit, result, criteria)
        filtered_rs_tables += new_filtered_rs_tables
        num_loops += 1

    return new_filtered_rs_tables[offset:(offset+limit)]

############ RUNSELECTION_RUN PAGE FUNCTIONS ############

def get_criteria_tables(runNum, crit_version):
    '''Get criteria tables associated with run, list of criteria tags.
    crit_version is a dictionary with a key for every criteria tag, and
    the associate value is the preferred version number'''

    # Download criteria tables that match run number and criteria tag(s)
    query = "SELECT meta_data, timestamp FROM run_selection"
    query += "WHERE run_min <= {} AND (run_max IS NULL OR run_max >= {}) AND type = 'CRITERIA'".format(int(runNum), int(runNum))
    query += " AND ("
    for criteria in crit_version:
        query += "criteria = '{}' OR ".format(criteria)
    query = query[:-5]  # Remove last ' OR '
    query += " ORDER BY timestamp DESC LIMIT 50"

    conn = engine_nl.connect()
    resultQuery = conn.execute(query)

    table_list = []
    for row in resultQuery.fetchall():
        tempt_dict = {}
        tempt_dict['meta_data'] = row[0]
        tempt_dict['timestamp'] = row[1]
        table_list.append(tempt_dict)

    # Repackage and check for duplicates
    crit_tables = {}
    for table in table_list:
        criteria = table['meta_data']['index']
        if criteria not in crit_tables and criteria in crit_version:
            crit_tables[criteria] = table
        else:
            # There is a duplicate
            if decide_replace_table(crit_tables[criteria], table, crit_version[criteria]):
                crit_tables[criteria] = table

    # Check if we got a criteria table for each inputted criteria
    for crit in crit_version:
        if crit not in crit_tables:
            print('WARNING: No criteria table found for {} criteria.'.format(crit))
            crit_tables[crit] = False

    return crit_tables

def format_data(runNum):
    '''Format information to be used easilt by runselection_run.html template
    Essentially we want a set of collapsable to look at the results, values
    and criteria threshold for each rs_module, and for each criteria tag.'''

    ### Download Tables ###
    rs_tables = get_RS_reports(run_min=runNum, run_max=runNum, limit=50)[runNum]
    if rs_tables == False:
        return False
    crit_version = {}
    criteria_list = []
    for criteria in rs_tables: # Get criteria tag and version number for each table
        crit_version[criteria] = int(rs_tables[criteria]['meta_data']['version'])
        criteria_list.append(criteria)
    crit_tables = get_criteria_tables(runNum, crit_version)


    ### General Information ###
    general_info = OrderedDict()
    first_table = rs_tables[criteria_list[0]]  # Take first table for general information (no particular reason)

    general_info['Run'] = first_table['meta_data']['run_range'][0]
    general_info['Start timestamp'] = first_table['meta_data']['run_time']['notes']['dt']['timestamp']
    general_info['Duration'] = first_table['meta_data']['run_time']['notes']['dt']['orca_duration']

    crit_str = ''
    for i in range(len(criteria_list) - 1):
        crit_str += criteria_list[i] + ', '
    crit_str += criteria_list[-1]
    general_info['Criteria'] = crit_str

    for criteria in criteria_list:
        if rs_tables[criteria]['meta_data']['decision']['result'] == True:
            general_info[criteria + ' result'] = "Pass"
        elif rs_tables[criteria]['meta_data']['decision']['result'] == None:
            general_info[criteria + ' result'] = "Fail"
        else:
            general_info[criteria + ' result'] = "Purgatory"

    general_info['Last reviewed'] = first_table['timestamp']
    general_info['Last reviewer'] = first_table['name']


    ### Run Selection Results ###
    display_info = {}
    for criteria in rs_tables:
        # A collapsable header for each criteria tag
        if criteria not in crit_tables:
            continue
        rs_table = rs_tables[criteria]['meta_data']
        rs_modules = rs_table['decision']['rs_modules']
        crit_table = crit_tables[criteria]['meta_data']

        display_info[criteria] = {}
        display_info[criteria]['criteria_result'] = rs_table['decision']['result']
        display_info[criteria]['rs_modules'] = {}
        for rs_module in rs_modules:
            # A (sub)collapsable header for each rs_module
            if rs_module == 'dqll':  # obsolete
                continue
            results = rs_table[rs_module]['results']
            notes = rs_table[rs_module]['notes']
            crits = crit_table[rs_module]

            display_info[criteria]['rs_modules'][rs_module] = {}
            display_info[criteria]['rs_modules'][rs_module]['checks'] = {}
            for check in results:
                # A line for each check (except overall rs_module result)
                if check == 'and_result':
                    display_info[criteria]['rs_modules'][rs_module]['module_result'] = results[check]

                else:
                    display_info[criteria]['rs_modules'][rs_module]['checks'][check] = {}
                    display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Result'] = results[check]

                    if check not in crits:  # (Deck activity special case, but keeping it general in case)
                        thresh_str = ''
                        for deck_activity in crits:
                            if crits[deck_activity] is not None:  # If it is None, it will not fail the run
                                thresh_str += '• ' + deck_activity + '\n'
                        display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Threshold'] = thresh_str[:-3]  # Remove last '\n'
                    elif isinstance(crits[check], dict):  # (Alarms check special case, but keeping it general in case)
                        thresh_str = ''
                        for alarm in crits[check]:
                            thresh_str += '• ' + alarm + '\n'
                        display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Threshold'] = thresh_str[:-3]  # Remove last '\n'
                    else:
                        display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Threshold'] = crits[check]

                    if check not in notes:
                        display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Value'] = 0
                    elif isinstance(notes[check], list):
                        display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Value'] = len(notes[check])
                    else:
                        display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Value'] = notes[check]


    ### Return Data ###

    return general_info, display_info


# def import_RS_ratdb(runs, result, limit, offset):

#     if type(runs) == list:
#         first_run = runs[0]
#     else:
#         first_run = runs

#     query = """
#         SELECT meta_data, name, timestamp
#         FROM run_selection
#         WHERE run_min <= {}
#         AND run_max <= {}
#         AND type='RS_REPORT'
#         ORDER BY run_min DESC
#         """.format(int(first_run + offset), first_run + limit + offset)

#     conn = engine_nl.connect()
#     resultQuery = conn.execute(query)

#     data = []
#     names = []
#     times = []
#     criterialist = []
#     for row in resultQuery.fetchall():
#         data.append(row[0])
#         names.append([row[1]])
#         times.append([row[2]])
#         if data[-1]['index'] not in criterialist:
#             criterialist.append(data[-1]['index'])

#     info = {}

#     resultMapping = {'Pass': True, 'Purgatory': None, 'Fail': False, 'All': True}

#     for i in range(len(data)):
#         if (result == 'All' or data[i]['decision']['result'] == resultMapping[result]) and data[i]['version'] > 2:
#             if int(data[i]['run_range'][0]) not in info.keys():
#                 info[int(data[i]['run_range'][0])] = {}
#             info[int(data[i]['run_range'][0])][data[i]['index']] = data[i]
#             info[int(data[i]['run_range'][0])][data[i]['index']]["name"] = names[i][0]
#             info[int(data[i]['run_range'][0])][data[i]['index']]["time"] = times[i][0]

#     if type(runs) == list:
#         for number in runs:
#             if int(number) not in info.keys():
#                 info[int(number)] = -1
#             else:
#                 for criteria in criterialist:
#                     if criteria not in info[int(number)].keys():
#                         info[int(number)][criteria] = -1

#     query = """
#         SELECT meta_data
#         FROM run_selection
#         WHERE run_min <= {}
#         AND type='CRITERIA'
#         """.format(int(first_run), int(first_run))

#     resultQuery = conn.execute(query)

#     criteriaInfo = {}

#     for row in resultQuery.fetchall():
#         criteriaInfo[row[0]["index"]] = row[0]

#     conn.close()

#     criteriaInfo = OrderedDict(sorted(criteriaInfo.items()))
#     for v in criteriaInfo:
#         criteriaInfo[v] = OrderedDict(sorted(criteriaInfo[v].items()))
#         for k in criteriaInfo[v]:
#             if isinstance(criteriaInfo[v][k], dict):
#                 criteriaInfo[v][k] = OrderedDict(sorted(criteriaInfo[v][k].items()))

#     try:
#         info = OrderedDict(sorted(info.items()))
#         for v in info: #FIXME: Surely a more elegant way of doing this?
#             info[v] = OrderedDict(sorted(info[v].items()))
#             for k in info[v]:
#                 if isinstance(info[v][k], dict):
#                     info[v][k] = OrderedDict(sorted(info[v][k].items()))
#                 for l in info[v][k]:
#                     if isinstance(info[v][k][l], dict): #decision here!
#                         info[v][k][l] = OrderedDict(sorted(info[v][k][l].items()))
#                         for m in info[v][k][l]:
#                             if isinstance(info[v][k][l][m], dict):
#                                 info[v][k][l][m] = OrderedDict(sorted(info[v][k][l][m].items()))
#                                 for n in info[v][k][l][m]:
#                                     if isinstance(info[v][k][l][m][n], dict):
#                                         info[v][k][l][m][n] = OrderedDict(sorted(info[v][k][l][m][n].items()))
#                                         for o in info[v][k][l][m][n]:
#                                             if isinstance(info[v][k][l][m][n][o], dict):
#                                                 info[v][k][l][m][n][o] = OrderedDict(sorted(info[v][k][l][m][n][o].items())) 
#                             elif isinstance(info[v][k][l][m], list):
#                                 info[v][k][l][m] = sorted(info[v][k][l][m])
#     except:
#         pass

#     return info, criteriaInfo