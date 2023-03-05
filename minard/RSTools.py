# -*- coding: utf-8 -*-
# Need comment above to use bullet-point character
from wtforms import Form, BooleanField, StringField, PasswordField, validators
from .db import engine, engine_nl
from collections import OrderedDict
import psycopg2
import psycopg2.extras
from dateutil import parser
import datetime
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
    result = conn.execute("SELECT list FROM evaluated_runs WHERE run=%s" % (run,))
    return [int(row[0]) for row in result.fetchall()]

def get_run_lists():
    conn = engine.connect()
    result = conn.execute("SELECT name, id FROM run_lists ORDER BY name ASC")
    data = OrderedDict()
    for entry in result.fetchall():
        data[str(entry[0])] = int(entry[1])
    conn.close()
    return data

def get_list_history(run):
    """
    Get run list history for this run.
    """
    # key | run | uploaded_to | removed_from | name | timestamp | comment
    conn = engine.connect()
    result = conn.execute("SELECT timestamp, uploaded_to, removed_from, comment, name FROM rs_history WHERE run=%s ORDER BY timestamp DESC", (run,))
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
                            user=app.config['DB_OPERATOR'],
                            host=app.config['DB_HOST'],
                            password=form.password.data)
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

    cursor = conn.cursor()
    for key in dir(form):
        if key in lists:
            if (getattr(form, key).data == True and lists[key] not in data): # need new entry
                # Add run to run list
                result = cursor.execute("INSERT INTO evaluated_runs(run, list, evaluator) VALUES(%s, %s, %s)", (int(run), int(lists[key]), name))
                # Update run history
                result = cursor.execute("INSERT INTO rs_history(run,uploaded_to,removed_from,name,comment) VALUES(%s,%s,NULL,%s,%s)", (int(run), str(key), name, comment))
            elif (getattr(form, key).data == False and lists[key] in data): # need to delete entry
                # Remove run from run list
                result = cursor.execute("DELETE FROM evaluated_runs WHERE run = %s AND list = %s", (int(run), int(lists[key])))
                # Update run history
                result = cursor.execute("INSERT INTO rs_history(run,uploaded_to,removed_from,name,comment) VALUES(%s,NULL,%s,%s,%s)", (int(run), str(key), name, comment))
    
    """
    Now, update the nearlineDB with the name and time
    """

    conn_nl = psycopg2.connect(dbname=app.config['DB_NAME_NEARLINE'],
                               user=app.config['DB_OPERATOR'],
                               host=app.config['DB_HOST_NEARLINE'],
                               password=form.password.data,
                               port=app.config['DB_PORT_NEARLINE'])
    conn_nl.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

    cursor_nl = conn_nl.cursor()
    result_nl = cursor_nl.execute("UPDATE run_selection SET name=%s WHERE run_min=%s AND run_max=%s AND type='RS_REPORT'", (form.name.data, run, run))

    conn_nl.close()


def decide_replace_table(first_table, second_table, version=None):
    '''Decide whether second_table should replace first_table, first based on version
    number, then on timestamp'''

    if second_table['meta_data']['version'] == first_table['meta_data']['version']:
        first_time = first_table['timestamp']
        second_time = second_table['timestamp']
        dt = second_table['timestamp'] - first_table['timestamp']
        dt_seconds = dt.days*3600*12 + dt.seconds

        if dt_seconds > 0:
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
    query = "SELECT meta_data, name, timestamp, run_min FROM run_selection WHERE type = 'RS_REPORT'"
    conditions = []
    if criteria is not None:
        conditions.append("criteria = '%s'" % str(criteria))
    if run_min is not None:
        conditions.append("run_min >= %d" % int(run_min))
    if run_max is not None:
        conditions.append("run_max <= %d" % int(run_max))

    if len(conditions) > 0:
        for i in range(0, len(conditions)):
            query += " AND " + conditions[i]

    query += " ORDER BY run_min DESC"
    if limit is not None:
        query += " LIMIT %d" % (limit)

    try:
        conn = engine_nl.connect()
        resultQuery = conn.execute(query)

        rs_tables_list = []
        for row in resultQuery.fetchall():
            tempt_dict = {}
            tempt_dict['meta_data'] = row[0]
            tempt_dict['name'] = row[1]
            tempt_dict['timestamp'] = row[2]
            tempt_dict['run_number'] = row[3]
            if 'notes' in row[0]['run_time']:
                tempt_dict['run_start'] = row[0]['run_time']['notes']['dt']['timestamp'].split('.')[0]
            else:
                tempt_dict['run_start'] = 'No Data'
            tempt_dict['result'] = row[0]['decision']['result']
            rs_tables_list.append(tempt_dict)

        if len(rs_tables_list) == 0:
            return False
        
        # Repackage and check for duplicates
        rs_tables = OrderedDict()
        for table in rs_tables_list:
            run_number = table['run_number']
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
    except:
        return False
    
    finally:
        conn.close()

def get_filtered_RS_tables(run_min, run_max, min_runTime, max_runTime, offset, limit, result, criteria):
    '''Download run-selection tables in range, and keep only ones with desired result'''

    # Download a few more runs than limit, in case some don't meet conditions
    rs_tables = get_RS_reports(criteria=criteria, run_min=run_min, run_max=run_max, limit = (offset + limit) * 2)
    if rs_tables is False:
        return False, False, True
    # Remove nanoseconds and timezone info from timestamps
    for run in rs_tables:
        for crit in rs_tables[run]:
            rs_tables[run][crit]['timestamp'] = str(rs_tables[run][crit]['timestamp']).split('.')[0]

    no_more_tables = False
    if len(rs_tables) < ((offset + limit) * 2):
        no_more_tables = True

    ### Check conditions ###

    # In RS tables, the final result is written as True if it passed,
    # False if it failed, and None if it was purgatoried.
    resultMapping = {'Pass': True, 'Purgatory': None, 'Fail': False}

    # We only want to display runs with the specified result

    run_numbers = []
    if min_runTime is None and max_runTime is None and result == 'All':
        # Easiest case: they all pass
        filtered_rs_tables = rs_tables
        for run_number in filtered_rs_tables:
            run_numbers.append(run_number)
    else:
        # Initialise values
        filtered_rs_tables = OrderedDict()
        before_max = False
        if max_runTime is None:
            # No max time, all runs pass this filter
            before_max = True

        # Loop through RS tables
        for run_number in rs_tables.keys():
            if rs_tables[run_number][criteria]['run_start'] != 'No Data':
                # Get run time
                run_start_lst = rs_tables[run_number][criteria]['run_start'].split(' ')[0].split('-')
                run_start = datetime.date(int(run_start_lst[0]), int(run_start_lst[1]), int(run_start_lst[2]))
                
                # Apply time filter: only keep if before max run time, and before min run time
                # (+ break loop if before min run time, since there will be no more relevant runs)
                if not before_max:
                    before_max = (run_start <= max_runTime)
                if min_runTime is not None:
                    if run_start < min_runTime:
                        no_more_tables = True
                        break
            
            # Apply result filter
            if result == 'All':
                result_check = True
            else:
                result_check = (rs_tables[run_number][criteria]['result'] == resultMapping[result])

            # Only keep table if it passes filters
            if result_check and before_max:
                filtered_rs_tables[run_number] = rs_tables[run_number]
                run_numbers.append(run_number)

    return filtered_rs_tables, run_numbers, no_more_tables

def list_runs_info(limit, offset, result, criteria, selected_run, run_range, date_range):
    '''Want a list of runs that satisfy condition from (latest run - offset)
    to (latest run - offset - limit). Where the runs considered here are only
    those that satisfy the conditions (i.e. we always want to display a number
    of runs = limit, no matter the conditions.'''

    # Get run number limits
    run_min = None
    run_max = None
    if selected_run != 0:
        run_min = selected_run
        run_max = selected_run
    else:
        if run_range[0] != 0:
            run_min = run_range[0]
        if run_range[1] != 0:
            run_max = run_range[1]

    # Get date limits
    min_runTime = None
    max_runTime = None
    if 0 not in date_range[0]:
        min_runTime = datetime.date(date_range[0][0], date_range[0][1], date_range[0][2])
    if 0 not in date_range[1]:
        max_runTime = datetime.date(date_range[1][0], date_range[1][1], date_range[1][2])

    # Get filtered runs (download twice as many runs as needed, then filter by result)
    filtered_rs_tables, run_numbers, no_more_tables = get_filtered_RS_tables(run_min, run_max, min_runTime, max_runTime, offset, limit, result, criteria)
    if filtered_rs_tables is False:
        return False
    run_numbers.sort(reverse=True)

    # If there aren't enough, keep downloading more runs until we get enough. Either until enough
    # are downloaded, or there are no more tables to download, or reach a hard cap in number of loops (just in case).
    num_loops = 0
    while (len(run_numbers) <= (offset + limit)) and (no_more_tables == False) and (num_loops <= 100):
        earliest_run = run_numbers[-1]
        new_filtered_rs_tables, new_run_numbers, no_more_tables = get_filtered_RS_tables(run_min, earliest_run-1, min_runTime, max_runTime, offset, limit, result, criteria)
        filtered_rs_tables.update(new_filtered_rs_tables)
        run_numbers += new_run_numbers
        run_numbers.sort(reverse=True)
        num_loops += 1

    # Only keep the runs that will be listed on the page
    final_rs_tables = OrderedDict()
    for i in range(offset, (offset+limit)):
        if i < len(run_numbers):
            final_rs_tables[run_numbers[i]] = filtered_rs_tables[run_numbers[i]]

    return final_rs_tables

############ RUNSELECTION_RUN PAGE FUNCTIONS ############

def get_criteria_tables(runNum, crit_version):
    '''Get criteria tables associated with run, list of criteria tags.
    crit_version is a dictionary with a key for every criteria tag, and
    the associate value is the preferred version number'''

    # Download criteria tables that match run number and criteria tag(s)
    query = "SELECT meta_data, timestamp FROM run_selection"
    query += " WHERE run_min <= %d AND (run_max IS NULL OR run_max >= %d) AND type = 'CRITERIA'" % (int(runNum), int(runNum))
    query += " AND ("
    for criteria in crit_version:
        query += "criteria = '%s' OR " % criteria
    query = query[:-4]  # Remove last ' OR '
    query += ") ORDER BY timestamp DESC LIMIT 50"

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
            crit_tables[crit] = False

    return crit_tables

def format_general_info(rs_tables, criteria_list):
    general_info = OrderedDict()
    first_table = rs_tables[criteria_list[0]]  # Take first table for general information (no particular reason)

    general_info['Run'] = first_table['meta_data']['run_range'][0]
    if 'notes' in first_table['meta_data']['run_time']:
        general_info['Start timestamp'] = str(first_table['meta_data']['run_time']['notes']['dt']['timestamp']).split('.')[0]  # Remove nanoseconds
        general_info['Duration'] = first_table['meta_data']['run_time']['notes']['dt']['orca_duration']
    else:
        general_info['Start timestamp'] = 'No Data'
        general_info['Duration'] = 'No Data'

    crit_str = ''
    for i in range(len(criteria_list) - 1):
        crit_str += criteria_list[i] + ', '
    crit_str += criteria_list[-1]
    general_info['Criteria'] = crit_str

    for criteria in criteria_list:
        if rs_tables[criteria]['meta_data']['decision']['result'] == True:
            general_info[criteria + ' result'] = "Pass"
        elif rs_tables[criteria]['meta_data']['decision']['result'] == False:
            general_info[criteria + ' result'] = "Fail"
        else:
            general_info[criteria + ' result'] = "Purgatory"

    general_info['Last reviewed'] = first_table['timestamp']
    general_info['Last reviewer'] = first_table['name']

    return general_info

def format_rs_results(rs_tables, crit_tables):
    display_info = OrderedDict()
    for criteria in rs_tables:
        # A collapsable header for each criteria tag
        if criteria not in crit_tables:
            continue
        rs_table = rs_tables[criteria]['meta_data']
        rs_modules = rs_table['decision']['rs_modules']
        crit_table = crit_tables[criteria]['meta_data']

        display_info[criteria] = OrderedDict()
        display_info[criteria]['criteria_result'] = rs_table['decision']['result']
        display_info[criteria]['rs_modules'] = OrderedDict()
        for rs_module in rs_modules:
            # A (sub)collapsable header for each rs_module
            if rs_module == 'dqll':  # obsolete
                continue
            elif 'error' in rs_table[rs_module]:
                display_info[criteria]['rs_modules'][rs_module] = "NO DATA"
                continue

            results = rs_table[rs_module]['results']
            if 'notes' in rs_table[rs_module]:
                notes = rs_table[rs_module]['notes']
            else:
                notes = OrderedDict()
            crits = crit_table[rs_module]

            display_info[criteria]['rs_modules'][rs_module] = OrderedDict()
            display_info[criteria]['rs_modules'][rs_module]['checks'] = OrderedDict()
            for check in results:
                # A line for each check (except overall rs_module result)
                # WARNING: This is a mess since RS_reports have a messy inconsistent structure that
                # doesn't necessarily line up perfectly with the criteria table used to produce them.
                if check == 'and_result':
                    display_info[criteria]['rs_modules'][rs_module]['module_result'] = results[check]
                else:
                    display_info[criteria]['rs_modules'][rs_module]['checks'][check] = OrderedDict()
                    # Get check and overall result
                    display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Check'] = check
                    if results[check] == True:
                        display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Result'] = "Pass"
                    elif results[check] == False:
                        display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Result'] = "Fail"
                    else:
                        display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Result'] = "Purgatory"

                    # How to display the values depends on if there of subchecks, or it's the number of entries in a list that matter, etc
                    if check not in notes:
                        if results[check]:
                            display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Value'] = 0
                        else:
                            display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Value'] = 1
                    elif isinstance(notes[check], list):
                        display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Value'] = len(notes[check])
                    elif isinstance(notes[check], dict):
                        display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Value'] = OrderedDict()
                        for subcheck in notes[check]:
                            string = subcheck
                            if isinstance(notes[check][subcheck], float):
                                string += (': %.2f' % notes[check][subcheck])
                            else:
                                string += (': %s' % (notes[check][subcheck]))
                            display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Value'][subcheck] = string
                    else:
                        display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Value'] = notes[check]

                    # How to display the thresholds depends on if there are subchecks, what it is, etc
                    if check not in crits:
                        if isinstance(display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Value'], dict):  # DQHL has subchecks grouped into processors in RS table, but not in criteria table...
                            display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Threshold'] = OrderedDict()
                            for subcheck in display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Value']:
                                if subcheck in crits:
                                    string = subcheck
                                    if isinstance(crits[subcheck], float):
                                        string += ': %.2f' % (crits[subcheck])
                                    else:
                                        string += ': %s' % (crits[subcheck])
                                    display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Threshold'][subcheck] = string
                            if len(display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Threshold']) == 0:
                                display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Threshold'] = ''
                        else:
                            display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Threshold'] = ''
                    elif isinstance(crits[check], dict):
                        display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Threshold'] = OrderedDict()
                        for subcheck in crits[check]:
                            if check == 'alarms':
                                display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Threshold'][subcheck] = subcheck
                            else:
                                string = subcheck
                                if isinstance(crits[check][subcheck], float):
                                    string += (': %.2f' % (crits[check][subcheck]))
                                else:
                                    string += (': %s' % (crits[check][subcheck]))
                                display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Threshold'][subcheck] = string
                    else:
                        display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Threshold'] = crits[check]

    return display_info

def get_neighbouring_runs(runNum):
    '''Return the run numbers of the previous and next runs'''

    # Get tables in descending order, with hardcoded max at 100 to avoid slow down if misused
    query_next = "SELECT run_min FROM run_selection WHERE type = 'RS_REPORT' AND run_min >= %d" % int(runNum + 1)
    query_next += " ORDER BY run_min ASC LIMIT 1"
    query_prev = "SELECT run_min FROM run_selection WHERE type = 'RS_REPORT' AND run_max <= %d" % int(runNum - 1)
    query_prev += " ORDER BY run_min DESC LIMIT 1"

    run_neighbours = [False, False]

    try:
        conn = engine_nl.connect()

        resultQuery_prev = conn.execute(query_prev)
        for row in resultQuery_prev.fetchall():
            run_neighbours[0] = row[0]
            break
        resultQuery_next = conn.execute(query_next)
        for row in resultQuery_next.fetchall():
            run_neighbours[1] = row[0]
            break

        return run_neighbours
    except:
        return run_neighbours
    
    finally:
        conn.close()
    

def format_data(runNum):
    '''Format information to be used easily by runselection_run.html template
    Essentially we want a set of collapsable to look at the results, values
    and criteria threshold for each rs_module, and for each criteria tag.'''

    # Download Tables
    rs_tables = get_RS_reports(run_min=runNum, run_max=runNum, limit=50)
    if rs_tables == False:
        return False, False
    else:
        rs_tables = rs_tables[runNum]
    if rs_tables == False:
        return False
    crit_version = {}
    criteria_list = []
    for criteria in rs_tables: # Get criteria tag and version number for each table
        crit_version[criteria] = int(rs_tables[criteria]['meta_data']['version'])
        criteria_list.append(criteria)
    crit_tables = get_criteria_tables(runNum, crit_version)


    # Get formatted info
    general_info = format_general_info(rs_tables, criteria_list)
    display_info = format_rs_results(rs_tables, crit_tables)

    # Get previous and next run numbers
    run_prev_next = get_neighbouring_runs(runNum)

    return general_info, display_info, run_prev_next
