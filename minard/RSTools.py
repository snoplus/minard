# -*- coding: utf-8 -*-
# Need comment above to use bullet-point character
from wtforms import Form, BooleanField, StringField, PasswordField, validators
from .db import engine, engine_nl
from collections import OrderedDict
import psycopg2
import psycopg2.extras
import json
from dateutil import parser
import datetime
from .views import app


############ FORM FUNCTIONS ############

def file_list_form_builder(formobj, runlists, data):
    if runlists == False or data == False:
        return False
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

def file_pass_form_builder(formobj, display_info):
    if display_info == False:
        return False
    class FilePassForm(Form):
        pass

    for criteria in display_info.keys():
        if display_info[criteria]['criteria_result'] and formobj == -1:
            setattr(FilePassForm, 'pass_run', BooleanField(label='Pass', default='checked'))
            setattr(FilePassForm, 'fail_run', BooleanField(label='Fail'))
        elif (not display_info[criteria]['criteria_result']) and formobj == -1:
            setattr(FilePassForm, 'pass_run', BooleanField(label='Pass'))
            setattr(FilePassForm, 'fail_run', BooleanField(label='Fail', default='checked'))
        else:
            setattr(FilePassForm, 'pass_run', BooleanField(label='Pass'))
            setattr(FilePassForm, 'fail_run', BooleanField(label='Fail'))
        setattr(FilePassForm, 'name', StringField('Name', [validators.Length(min=1), validators.InputRequired(), validators.Regexp('[A-Za-z0-9\s]{1,}', message='First and second name required.')]))
        setattr(FilePassForm, 'criteria', StringField('Criteria', [validators.InputRequired()], default=criteria))
        setattr(FilePassForm, 'comment', StringField('Comment', [validators.InputRequired()]))
        setattr(FilePassForm, 'password', PasswordField('Password', [validators.InputRequired()]))

    if formobj != -1:
        return FilePassForm(formobj)
    else:
        return FilePassForm()


def get_current_lists_run(run):
    c = False
    try:
        conn = engine.connect()
        result = conn.execute("SELECT list FROM evaluated_runs WHERE run=%s" % (run,))
        data =  [int(row[0]) for row in result.fetchall()]
    except:
        print('ERROR: Failed downloading current run lists')
        data = False

    if c:
        conn.close()
        
    return data

def get_run_lists():
    c = False
    try:
        conn = engine.connect()
        result = conn.execute("SELECT name, id FROM run_lists ORDER BY name ASC")
        data = OrderedDict()
        for entry in result.fetchall():
            data[str(entry[0])] = int(entry[1])
    except:
        print('ERROR: Failed downloading run lists')
        data = False

    if c:
        conn.close()
        
    return data

def get_list_history(run):
    """
    Get run list history for this run.
    """
    # key | run | uploaded_to | removed_from | name | timestamp | comment
    c = False
    try:
        conn = engine.connect()
        c = True
        result = conn.execute("SELECT timestamp, uploaded_to, removed_from, comment, name FROM rs_history WHERE run=%s ORDER BY timestamp DESC", (run,))
        data = OrderedDict()
        for i, entry in enumerate(result.fetchall()):
            data[str(i)] = {}
            data[str(i)]['timestamp'] = str(entry[0])
            data[str(i)]['list_added'] = str(entry[1])
            data[str(i)]['list_removed'] = str(entry[2])
            data[str(i)]['comment'] = str(entry[3])
            data[str(i)]['name'] = str(entry[4])
    except:
        print('ERROR: Failed downloading run list history')
        data = False

    if c:
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
    password = str(form.password.data)

    # Check password
    if password != app.config['RS_EXPERT_PASS']:
        return False, 'WARNING: wrong password'

    c = False
    c_nl = False
    try:
        # Connect to detector database, to update run lists and run list histories
        conn = psycopg2.connect(dbname=app.config['DB_NAME'],
                                user=app.config['DB_OPERATOR'],
                                host=app.config['DB_HOST'],
                                password=app.config['DB_OPERATOR_PASS'])
        c = True
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

        cursor = conn.cursor()
        for key in dir(form):
            if key in lists:
                if (getattr(form, key).data == True and lists[key] not in data): # need new entry
                    # Add run to run list
                    cursor.execute("INSERT INTO evaluated_runs(run, list, evaluator) VALUES(%s, %s, %s)", (int(run), int(lists[key]), name))
                    # Update run history
                    cursor.execute("INSERT INTO rs_history(run,uploaded_to,removed_from,name,comment) VALUES(%s,%s,NULL,%s,%s)", (int(run), str(key), name, comment))
                elif (getattr(form, key).data == False and lists[key] in data): # need to delete entry
                    # Remove run from run list
                    cursor.execute("DELETE FROM evaluated_runs WHERE run = %s AND list = %s", (int(run), int(lists[key])))
                    # Update run history
                    cursor.execute("INSERT INTO rs_history(run,uploaded_to,removed_from,name,comment) VALUES(%s,NULL,%s,%s,%s)", (int(run), str(key), name, comment))
    
        """
        Now, update the nearlineDB with the name and time
        """

        conn_nl = psycopg2.connect(dbname=app.config['DB_NAME_NEARLINE'],
                                user=app.config['DB_OPERATOR'],
                                host=app.config['DB_HOST_NEARLINE'],
                                password=app.config['DB_OPERATOR_PASS'],
                                port=app.config['DB_PORT_NEARLINE'])
        c_nl = True
        conn_nl.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

        cursor_nl = conn_nl.cursor()
        cursor_nl.execute("UPDATE run_selection SET name=%s WHERE run_min=%s AND run_max=%s AND type='RS_REPORT'", (form.name.data, run, run))
    except Exception as e:
        print(str(e))
        return False

    if c:
        conn.close()
    if c_nl:
        conn_nl.close()
    return True

def pass_fail_run(form, run_number):
    """
    Re-upload the table, with an overall pass, then update the rs_history tables with only a comment
    about who passed the run and why.
    """

    # Remove troublesome characters from entries
    name = str(form.name.data).replace("'", '').replace('"', '')
    comment = str(form.comment.data).replace("'", '').replace('"', '')
    criteria = str(form.criteria.data).replace("'", '').replace('"', '')
    password = str(form.password.data)

    # Check password
    if password != app.config['RS_EXPERT_PASS']:
        return False, 'WARNING: wrong password'

    # Get RS table
    RS_report = get_RS_reports(criteria=criteria, run_min=run_number, run_max=run_number)[run_number][criteria]['meta_data']

    # Change result and create run list history comment
    if (getattr(form, 'pass_run').data == True) and (getattr(form, 'fail_run').data == True):
        return False, 'ERROR: tried to pass and fail run'
    elif getattr(form, 'pass_run').data == True:
        RS_report['decision']['result'] = True
        list_com =  'Passed run manually for %s crietria: %s' % (criteria, comment)
    elif getattr(form, 'fail_run').data == True:
        RS_report['decision']['result'] = False
        list_com =  'Failed run manually for %s crietria: %s' % (criteria, comment)
    else:
        return False, 'WARNING: run neither passed nor failed'
    json_report = json.dumps(RS_report)

    # Upload new RS_report
    c_nl = False
    result_nl = False
    command_ping = ("INSERT INTO run_selection (run_min, run_max, name, criteria, type, " \
                    "meta_data) VALUES (%s, %s, %s, %s, %s, %s)")
    try:
        # Connect to detector database, to update run lists and run list histories
        conn_nl = psycopg2.connect(dbname=app.config['DB_NAME_NEARLINE'],
                                user=app.config['DB_OPERATOR'],
                                host=app.config['DB_HOST_NEARLINE'],
                                password=app.config['DB_OPERATOR_PASS'],
                                port=app.config['DB_PORT_NEARLINE'])
        conn_nl.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        c_nl = True
        cursor_nl = conn_nl.cursor()
        
        cursor_nl.execute(command_ping, (int(run_number), int(run_number), name, criteria, 'RS_REPORT', json_report))
        result_nl = True
    except Exception as e:
        print('ERROR uploading:', e)
        
    # Update run history (if run was updated successfully)
    c = False
    result = False
    command_ping = ("INSERT INTO rs_history (run, uploaded_to, removed_from, name, comment) VALUES(%s, %s, %s, %s, %s)")
    if result_nl:
        try:
            # Connect to detector database, to update run lists and run list histories
            conn = psycopg2.connect(dbname=app.config['DB_NAME'],
                                    user=app.config['DB_OPERATOR'],
                                    host=app.config['DB_HOST'],
                                    password=app.config['DB_OPERATOR_PASS'])
            conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
            c = True
            cursor = conn.cursor()
            
            cursor.execute(command_ping, (int(run_number), str(None), str(None), name, list_com))
            result = True
        except Exception as e:
            print('ERROR updating run list history:', e)
    
    # Close connections
    if c_nl:
        conn_nl.close()
    if c:
        conn.close()

    error_msg = ''
    if not result_nl:
        error_msg += 'ERROR: run not passed - uploading new RS report failed.\n'
    if not result:
        error_msg += 'WARNING: run list history not updated - uploading new entry failed.\n'

    return result, error_msg


def decide_replace_table(first_table, second_table):
    '''Decide whether second_table should replace first_table, first based on version
    number, then on timestamp'''

    if second_table['meta_data']['version'] == first_table['meta_data']['version']:
        dt = second_table['timestamp'] - first_table['timestamp']
        dt_seconds = dt.days*3600*24 + dt.seconds

        if dt_seconds > 0:
            return True
        else:
            return False
    
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

    c = False
    try:
        conn = engine_nl.connect()
        c = True
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
            return OrderedDict()
        
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
        if c:
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
    if len(rs_tables) < ((offset + limit) * 2) and limit > 1000:
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

    # Get list of criteria to put in drop-down menu (in order)
    drop_down_crits = app.config['DROP_DOWN_MENU_CRITS']

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
        try:
            min_runTime = datetime.date(date_range[0][0], date_range[0][1], date_range[0][2])
        except:
            return False, drop_down_crits
    if 0 not in date_range[1]:
        try:
            max_runTime = datetime.date(date_range[1][0], date_range[1][1], date_range[1][2])
        except:
            return False, drop_down_crits

    desired_criteria = ['scintillator', 'scintillator_silver', 'scintillator_bronze', 'scintillator_nickel']

    def placeholder_record(run_number, crit_name):
        return {
            'meta_data': {
                'decision': {'result': None},
                'index': crit_name
            },
            'name': 'No Data',
            'run_start': 'No Data',
            'timestamp': 'No Data',
            'run_number': run_number,
            'missing': True
        }

    if criteria == 'scintillator':
        # All four scintillator criterias (Gold, Silver, Bronze, Nickel)
        fetch_limit = max(200, (offset + limit) * 8)
        rs_all = OrderedDict()  # run_number -> {crit: table}
        for crit in desired_criteria:
            tables = get_RS_reports(criteria=crit, run_min=run_min, run_max=run_max, limit=fetch_limit)
            if not isinstance(tables, OrderedDict):
                continue
            for rn in tables.keys():
                if rn not in rs_all:
                    rs_all[rn] = {}
                rs_all[rn][crit] = tables[rn][crit]

        if len(rs_all) == 0:
            return OrderedDict(), drop_down_crits

        def choose_precedence(run_entry):
            for crit in desired_criteria:
                if crit in run_entry:
                    return crit
            return None

        resultMapping = {'Pass': True, 'Purgatory': None, 'Fail': False}
        # Special case: all four per-metal filters set to 'None' -> all unprocessed runs
        all_none = isinstance(result, dict) and all(result.get(c, 'All') == 'None' for c in desired_criteria)
        candidate_runs = []
        if all_none:
            # Build candidate runs from run_state and exclude any run that has any scintillator variant
            # Determine fetch size and time window - only physics runs
            fetch_limit = max(500, (offset + limit) * 8)
            conditions = []
            # Physics runs only: run_type & 1 > 0
            conditions.append("(run_type & 1) > 0")
            if run_min is not None:
                conditions.append("run >= %d" % int(run_min))
            if run_max is not None:
                conditions.append("run <= %d" % int(run_max))
            if max_runTime is not None:
                conditions.append("timestamp::date <= '%s'" % (max_runTime.strftime('%Y-%m-%d')))
            if min_runTime is not None:
                conditions.append("timestamp::date >= '%s'" % (min_runTime.strftime('%Y-%m-%d')))
            query_base = "SELECT run FROM run_state"
            query_base += " WHERE " + " AND ".join(conditions)
            query_base += " ORDER BY run DESC LIMIT %d" % fetch_limit
            try:
                conn_main = engine.connect()
                res = conn_main.execute(query_base)
                seen = set(rs_all.keys())
                for row in res.fetchall():
                    rn = int(row[0])
                    if rn not in seen:
                        candidate_runs.append(rn)
            except:
                # Fallback: no data gathered, leave candidate_runs empty
                pass
            finally:
                try:
                    conn_main.close()
                except:
                    pass
        else:
            for rn in rs_all.keys():
                chosen = choose_precedence(rs_all[rn])
                if chosen is None:
                    continue
                rec = rs_all[rn][chosen]
                pass_date = True
                run_start_str = rec.get('run_start', 'No Data')
                if run_start_str != 'No Data':
                    try:
                        y, m, d = [int(x) for x in run_start_str.split(' ')[0].split('-')]
                        run_start_date = datetime.date(y, m, d)
                        if max_runTime is not None and run_start_date > max_runTime:
                            pass_date = False
                        if min_runTime is not None and run_start_date < min_runTime:
                            pass_date = False
                    except Exception:
                        pass
                pass_result = True
                if isinstance(result, dict):
                    for crit in desired_criteria:
                        sel = result.get(crit, 'All')
                        if sel != 'All':
                            if sel == 'None':
                                # Keep only runs where this variant is missing
                                if crit in rs_all[rn]:
                                    pass_result = False
                                    break
                                else:
                                    continue
                            # Otherwise require presence and exact result match
                            if crit not in rs_all[rn]:
                                pass_result = False
                                break
                            if rs_all[rn][crit].get('result') != resultMapping[sel]:
                                pass_result = False
                                break
                else:
                    if result != 'All':
                        pass_result = (rec.get('result') == resultMapping[result])
                if pass_date and pass_result:
                    candidate_runs.append(rn)

        candidate_runs = sorted(candidate_runs, reverse=True)
        page_runs = candidate_runs[offset:offset+limit]

        final_rs_tables = OrderedDict()
        for rn in page_runs:
            final_rs_tables[rn] = {}
            # If run is in rs_all, attach available variants; otherwise placeholders
            for crit in desired_criteria:
                if rn in rs_all and crit in rs_all[rn]:
                    final_rs_tables[rn][crit] = rs_all[rn][crit]
                else:
                    final_rs_tables[rn][crit] = placeholder_record(rn, crit)
            # summary: highest-precedence available or placeholder
            if rn in rs_all:
                chosen = choose_precedence(rs_all[rn])
                if chosen is not None:
                    final_rs_tables[rn]['summary'] = rs_all[rn][chosen]
                else:
                    final_rs_tables[rn]['summary'] = placeholder_record(rn, 'scintillator')
            else:
                final_rs_tables[rn]['summary'] = placeholder_record(rn, 'scintillator')

        return final_rs_tables, drop_down_crits
    else:
        # Single-criteria mode 
        filtered_rs_tables, run_numbers, no_more_tables = get_filtered_RS_tables(run_min, run_max, min_runTime, max_runTime, offset, limit, result, criteria)
        if filtered_rs_tables is False:
            return False, drop_down_crits
        run_numbers.sort(reverse=True)

        num_loops = 0
        temp_lim = limit
        while (len(run_numbers) <= (offset + limit)) and (no_more_tables == False) and (num_loops <= 100):
            if len(run_numbers) == 0:
                earliest_run = None
            else:
                earliest_run = run_numbers[-1] - 1
            new_filtered_rs_tables, new_run_numbers, no_more_tables = get_filtered_RS_tables(run_min, earliest_run, min_runTime, max_runTime, offset, temp_lim, result, criteria)
            filtered_rs_tables.update(new_filtered_rs_tables)
            run_numbers += new_run_numbers
            run_numbers.sort(reverse=True)
            num_loops += 1
            temp_lim *= 2

        final_rs_tables = OrderedDict()
        for i in range(offset, (offset+limit)):
            if i < len(run_numbers):
                rn = run_numbers[i]
                final_rs_tables[rn] = filtered_rs_tables[rn]

        # Augment with the four scintillator variants for display and set summary to selected criteria
        if len(final_rs_tables) > 0:
            runs_display = list(final_rs_tables.keys())
            run_min_disp = min(runs_display)
            run_max_disp = max(runs_display)

            # Ensure summary exists
            for rn in runs_display:
                if criteria in final_rs_tables[rn]:
                    final_rs_tables[rn]['summary'] = final_rs_tables[rn][criteria]
                else:
                    final_rs_tables[rn]['summary'] = placeholder_record(rn, criteria)

            for crit in desired_criteria:
                other = get_RS_reports(criteria=crit, run_min=run_min_disp, run_max=run_max_disp, limit=len(runs_display)*4)
                for rn in runs_display:
                    if isinstance(other, OrderedDict) and rn in other and crit in other[rn]:
                        final_rs_tables[rn][crit] = other[rn][crit]
                    else:
                        if crit not in final_rs_tables[rn]:
                            final_rs_tables[rn][crit] = placeholder_record(rn, crit)

        return final_rs_tables, drop_down_crits

############ RUNSELECTION_RUN PAGE FUNCTIONS ############

def get_criteria_tables(runNum, crit_timestamp):
    '''
    Get criteria tables associated with run, list of criteria tags.
    crit_version is a dictionary with a key for every criteria tag, and
    the associate value is the timestamp (when table was uploaded)
    '''

    # Download criteria tables that match run number and criteria tag(s),
    # and existed at the time the RS reports were uploaded
    query = "SELECT meta_data, timestamp FROM run_selection"
    query += " WHERE run_min <= %d AND (run_max IS NULL OR run_max >= %d) AND type = 'CRITERIA'" % (int(runNum), int(runNum))
    query += " AND ("
    for criteria in crit_timestamp:
        query += "(criteria = '%s' AND timestamp <= '%s') OR " % (criteria, crit_timestamp[criteria])
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
        if criteria not in crit_tables and criteria in crit_timestamp:
            crit_tables[criteria] = table
        else:
            # There is a duplicate
            if decide_replace_table(crit_tables[criteria], table):
                crit_tables[criteria] = table

    # Check if we got a criteria table for each inputted criteria
    for crit in crit_timestamp:
        if crit not in crit_tables:
            crit_tables[crit] = False

    return crit_tables

def format_general_info(rs_tables, criteria_list):
    '''Collect information for "General Information" section of the page'''

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

def result_logic(obj):
    '''
    Return result (True, False, None) of object.
    Checks inside object recursively.
    If any element is False, return False,
    else if any any element is None, return None,
    else return True (i.e. if all are True).
    '''

    result = True
    if isinstance(obj, list):
        for sub_obj in obj:
            res = result_logic(sub_obj)
            if res == False:
                return False
            elif res == None:
                result = None
    elif isinstance(obj, dict):
        for key in obj:
            res = result_logic(obj[key])
            if res == False:
                return False
            elif res == None:
                result = None
    elif obj == True or obj == False:
        result = obj
    else:
        result = None

    return result

def format_rs_results(rs_tables, crit_tables):
    '''Collect information for the "Run Selection Results" section of the page'''

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
                    overall_res = result_logic(results[check])
                    if overall_res == True:
                        display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Result'] = "Pass"
                    elif overall_res == False:
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
                        for i in notes[check]:
                            notes_to_print =  i + '\n'
                        display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Value'] = notes_to_print
                    elif isinstance(notes[check], dict):
                        display_info[criteria]['rs_modules'][rs_module]['checks'][check]['Value'] = OrderedDict()
                        for subcheck in notes[check]:
                            if isinstance(notes[check][subcheck], float):
                                string = ('%.2f' % notes[check][subcheck])
                            else:
                                string = notes[check][subcheck]
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

    c = False
    try:
        conn = engine_nl.connect()
        c = True

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
        if c:
            conn.close()
    

def format_data(runNum):
    '''Format information to be used easily by runselection_run.html template
    Essentially we want a set of collapsable to look at the results, values
    and criteria threshold for each rs_module, and for each criteria tag.'''

    # Download Tables
    failed = False
    rs_tables = get_RS_reports(run_min=runNum, run_max=runNum, limit=50)
    if rs_tables == False:
        failed = True
    else:
        rs_tables = rs_tables[runNum]
    if rs_tables == False:
        failed = True

    if not failed:
        crit_version = {}
        criteria_list = []
        for criteria in rs_tables: # Get criteria tag and version number for each table
            crit_version[criteria] = rs_tables[criteria]['timestamp']
            criteria_list.append(criteria)
        crit_tables = get_criteria_tables(runNum, crit_version)


        # Get formatted info
        general_info = format_general_info(rs_tables, criteria_list)
        display_info = format_rs_results(rs_tables, crit_tables)
    else:
        general_info = False
        display_info = False

    # Get previous and next run numbers
    run_prev_next = get_neighbouring_runs(runNum)

    return general_info, display_info, run_prev_next



############ PLOT_RUNSELECTION PAGE FUNCTIONS ############

def pass_fail_plot_info(criteria, date_range):
    ''' calculates the cumulative number of days of physics, passed, failed and purgatory runs 
        based on input criteria and date range '''

    # Get list of criteria to put in drop-down menu (in order)
    drop_down_crits = app.config['DROP_DOWN_MENU_CRITS']

    # Get date limits
    min_runTime = None
    max_runTime = None
    if isinstance(date_range[0], datetime.datetime):
        min_runTime = date_range[0]
    else:
        return False, drop_down_crits, None, None
    if isinstance(date_range[1], datetime.datetime):
        max_runTime = date_range[1]
        max_runTime = max_runTime.replace(hour=23, minute=59, second=59)
        max_runTime = min(max_runTime, datetime.datetime.now())
    else:
        return False, drop_down_crits, min_runTime, None

    # Create hourly buckets for the entire time range
    num_hours = int((max_runTime - min_runTime).total_seconds() / 3600) + 1
    data = []
    for i in range(num_hours):
        hour_start = min_runTime + datetime.timedelta(hours=i)
        data.append({
            'timestamp': hour_start.isoformat(),
            'pass_time': 0.0,  # hours spent in passing state
            'fail_time': 0.0,  # hours spent in failing state
            'purg_time': 0.0,  # hours spent in purgatory state
            'idle_time': 1.0   # hours with no run (default to full hour)
        })

    # Download physics runs in given date range
    rstables = get_RS_reports_date_range(criteria=criteria, min_date=min_runTime, max_date=max_runTime)
    if rstables is False:
        return False, drop_down_crits, min_runTime, max_runTime

    # Track run counts
    run_counts = {
        'pass_runs': 0,
        'fail_runs': 0,
        'purg_runs': 0,
        'phys_runs': 0
    }

    # Process each run and allocate its time to the appropriate hourly buckets
    for run_number in rstables.keys():
        if rstables[run_number][criteria]['run_duration'] == 'No Data':
            continue
        if rstables[run_number][criteria]['run_start'] == 'No Data':
            continue

        # Parse run start time
        run_start_str = rstables[run_number][criteria]['run_start']
        try:
            # Handle both formats: with and without microseconds
            if '.' in run_start_str:
                run_start = datetime.datetime.strptime(run_start_str, '%Y-%m-%d %H:%M:%S.%f')
            else:
                run_start = datetime.datetime.strptime(run_start_str, '%Y-%m-%d %H:%M:%S')
        except:
            continue

        # Get run duration in seconds
        run_duration_seconds = rstables[run_number][criteria]['run_duration']
        run_end = run_start + datetime.timedelta(seconds=run_duration_seconds)

        # Skip runs outside our time range
        if run_end < min_runTime or run_start > max_runTime:
            continue

        # Clip run to our time range
        run_start_clipped = max(run_start, min_runTime)
        run_end_clipped = min(run_end, max_runTime)

        # Get result (pass=True, fail=False, purgatory=None)
        result = rstables[run_number][criteria]['result']

        # Count this run
        run_counts['phys_runs'] += 1
        if result == True:
            run_counts['pass_runs'] += 1
        elif result == False:
            run_counts['fail_runs'] += 1
        else:  # None = purgatory
            run_counts['purg_runs'] += 1

        # Distribute run time across the hours it spans
        current_time = run_start_clipped
        while current_time < run_end_clipped:
            # Find which hour bucket this time falls into
            hours_from_start = (current_time - min_runTime).total_seconds() / 3600
            hour_index = int(hours_from_start)
            
            if hour_index >= len(data):
                break

            # Calculate how much of this hour the run occupies
            hour_start = min_runTime + datetime.timedelta(hours=hour_index)
            hour_end = hour_start + datetime.timedelta(hours=1)
            
            segment_start = max(current_time, hour_start)
            segment_end = min(run_end_clipped, hour_end)
            segment_duration_hours = (segment_end - segment_start).total_seconds() / 3600

            # Add to appropriate category and subtract from idle
            if result == True:
                data[hour_index]['pass_time'] += segment_duration_hours
            elif result == False:
                data[hour_index]['fail_time'] += segment_duration_hours
            else:  # None = purgatory
                data[hour_index]['purg_time'] += segment_duration_hours
            
            data[hour_index]['idle_time'] -= segment_duration_hours

            # Move to next hour
            current_time = hour_end

    # Ensure idle_time doesn't go negative due to overlapping runs
    for hour_data in data:
        hour_data['idle_time'] = max(0.0, hour_data['idle_time'])

    # Add run counts to the data structure
    summary = {
        'data': data,
        'run_counts': run_counts
    }

    return summary, drop_down_crits, min_runTime, max_runTime

def get_RS_reports_date_range(criteria=None, run_max=None, min_date=None, max_date=None):
    '''Get run-selection tables in a run range. If duplicate tables, only keeps one
    (takes one with latest version, and if they have the same version, the one with
    the latest timestamp).'''
    # Get tables within given data range and for given criteria in ascending order
    query = "SELECT meta_data, run_min, timestamp FROM run_selection WHERE type = 'RS_REPORT'"
    conditions = []
    if criteria is not None:
        conditions.append("criteria = '%s'" % str(criteria))
    if run_max is not None:
        conditions.append("run_max < %d" % int(run_max))
    
    # Add date range filtering using the meta_data field
    if min_date is not None:
        conditions.append("(meta_data->'run_time'->'notes'->'dt'->>'timestamp')::timestamp >= '%s'" % min_date.strftime('%Y-%m-%d %H:%M:%S'))
    if max_date is not None:
        conditions.append("(meta_data->'run_time'->'notes'->'dt'->>'timestamp')::timestamp <= '%s'" % max_date.strftime('%Y-%m-%d %H:%M:%S'))
    
    if len(conditions) > 0:
        for i in range(0, len(conditions)):
            query += " AND " + conditions[i]
    query += " ORDER BY run_min DESC"
    
    c = False
    try:
        conn = engine_nl.connect()
        c = True
        resultQuery = conn.execute(query)
        rs_tables_list = []
        for row in resultQuery.fetchall():
            tempt_dict = {}
            tempt_dict['meta_data'] = row[0]
            tempt_dict['result'] = row[0]['decision']['result']
            if 'notes' in row[0]['run_time']:
                tempt_dict['run_duration'] = row[0]['run_time']['notes']['dt']['orca_duration']
                tempt_dict['run_start'] = row[0]['run_time']['notes']['dt']['timestamp']
            else:
                tempt_dict['run_duration'] = 'No Data'
            tempt_dict['run_number'] = row[1]
            tempt_dict['timestamp'] = row[2]
            rs_tables_list.append(tempt_dict)
        if len(rs_tables_list) == 0:
            return OrderedDict()
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
        if c:
            conn.close()
