from wtforms import Form, BooleanField, StringField, PasswordField, validators
from .db import engine
import psycopg2
from .views import app

def file_list_form_builder(formobj, runlists, data):
    class FileListForm(Form):
        pass

    # if formobj == -1:
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
    result = conn.execute("SELECT name, id FROM run_lists")
    data = {}
    for entry in result.fetchall():
        data[str(entry[0])] = int(entry[1])
    return data

def update_run_lists(form, run, lists, data):
    """
    First update the run lists, then update the tables with new comment and timestamp
    """
    # conn = psycopg2.connect(dbname=app.config['DB_NAME'],
    #                         user=app.config['DB_EXPERT_USER'], /////////////////////////// check this!!!
    #                         host=app.config['DB_HOST'],
    #                         password=form.password.data)
    # conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

    # cursor = conn.cursor()
    # for key in dir(form):
    #     if key in lists:
    #         if (getattr(form, key).data == True and lists[key] not in data): # need new entry
    #             result = cursor.execute("INSERT INTO evaluated_runs(run, list, evaluator) VALUES({},{},{})".format(run, lists[key], form.data.name))
    #         else if(getattr(form, key).data == False and lists[key] in data): # need to delete entry
    #             result = cursor.execute("DELETE FROM evaluated_runs WHERE run = {} AND list = {}".format(run, lists[key]))
    
    # """
    # Now, update the nearlineDB with the name and time
    # """

    conn_nl = psycopg2.connect(dbname=app.config['DB_NAME_RATDB'],
                               user=app.config['DB_EXPERT_RATDB'],
                               host=app.config['DB_HOST_RATDB'],
                               password=form.password.data)
    conn_nl.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

    cursor_nl = conn_nl.cursor()
    result_nl = cursor_nl.execute("UPDATE run_selection SET name=%s, timestamp=now() WHERE run_min=%s AND run_max=%s AND type='RS_REPORT'", (form.name.data, run, run))

    conn_nl.close()

    lists_to_update = []
    for key in vars(form):
        if key in lists:
            if (getattr(form, key).data == True and lists[key] not in data) or (getattr(form, key).data == False and lists[key] in data):
                lists_to_update.append(key)

    print("Lists to be updated:")
    for i in lists_to_update:
        print(i)

def import_RS_ratdb(runs, limit, offset):
    connection_details = ''
    connection_details += 'host=' + app.config['DB_HOST_RATDB']
    connection_details += ' port=' + str(app.config['DB_PORT_RATDB'])
    connection_details += ' dbname=' + app.config['DB_NAME_RATDB']
    connection_details += ' user=' + app.config['DB_USER']
    connection_details += ' password=' + app.config['DB_PASS']
    connection_details += ' connect_timeout=20'

    if type(runs) == list:
        first_run = runs[0]

    else:
        first_run = runs

    # query_string = """
    #     SELECT d.data
    #     FROM ratdb_data AS d, ratdb_header_v2 AS h
    #     WHERE d.key = h.key
    #     AND h.run_begin <= {}
    #     AND h.type='RS_REPORT'
    #     ORDER BY h.run_begin DESC
    #     LIMIT {} OFFSET {};
    #     """.format(int(first_run), limit, offset)

    query_string = """
        SELECT meta_data, name, timestamp
        FROM run_selection
        WHERE run_min <= {}
        AND run_max <= {}
        AND type='RS_REPORT'
        ORDER BY run_min DESC
        """.format(int(first_run + offset), first_run + limit + offset)

    parameters = None
    c = None

    c = psycopg2.connect(connection_details)
    cr = c.cursor()
    query = """%s""" % query_string
    cr.execute(query, parameters)

    data = []
    names = []
    times = []
    criterialist = []
    for row in cr.fetchall():
        data.append(row[0])
        names.append([row[1]])
        times.append([row[2]])
        if data[-1]['index'] not in criterialist:
            criterialist.append(data[-1]['index'])

    info = {}

    # criterialist = ["scintillator", "partial_fill_antinu", "partial_fill", "water"] #FIXME: Make this automatically grab available criteria

    for i in range(len(data)):
        if int(data[i]['run_range'][0]) not in info.keys():
            info[int(data[i]['run_range'][0])] = {}
        info[int(data[i]['run_range'][0])][data[i]['index']] = data[i]
        info[int(data[i]['run_range'][0])][data[i]['index']]["name"] = names[i][0]
        info[int(data[i]['run_range'][0])][data[i]['index']]["time"] = times[i][0]

    if type(runs) == list:
        for number in runs:
            if int(number) not in info.keys():
                info[int(number)] = -1
            else:
                for criteria in criterialist:
                    if criteria not in info[int(number)].keys():
                        info[int(number)][criteria] = -1

    query_string = """
        SELECT meta_data
        FROM run_selection
        WHERE run_min <= {}
        AND type='CRITERIA'
        """.format(int(first_run), int(first_run))

    query = """%s""" % query_string
    cr.execute(query, parameters)

    criteriaInfo = {}

    for row in cr.fetchall():
        criteriaInfo[row[0]["index"]] = row[0]

    c.close()

    return info, criteriaInfo