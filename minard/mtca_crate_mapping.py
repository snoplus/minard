from wtforms import Form, validators, IntegerField, SelectField, PasswordField
from .db import engine
from .views import app
import psycopg2
import psycopg2.extensions

# This dictionary maps the label numbers on the OWL trigger signals to the
# crate that they came from
OWL_LABELS = {1: 17, 2: 13, 3: 18, 4: 3}

choices = [(19, "None")] + [(i, str(i+1)) for i in range(19)]

owl_choices = [(-1, "None")]
for label, crate in OWL_LABELS.iteritems():
    owl_choices.append((crate, str(label)))

RETRIGGER_LOGIC = {
0: "No retrigger logic",
1: "Lockout",
2: "DGT",
3: "DGT and Lockout"
}

class MTCACrateMappingForm(Form):
    """
    A class for the form to update the crate map for the MTCA+s.
    """
    mtca =      IntegerField('MTCA', [validators.NumberRange(min=0,max=6)])
    channel0 =  SelectField('Channel 0', coerce=int, choices=choices)
    channel1 =  SelectField('Channel 1', coerce=int, choices=choices)
    channel2 =  SelectField('Channel 2', coerce=int, choices=choices)
    channel3 =  SelectField('Channel 3', coerce=int, choices=choices)
    channel4 =  SelectField('Channel 4', coerce=int, choices=choices)
    channel5 =  SelectField('Channel 5', coerce=int, choices=choices)
    channel6 =  SelectField('Channel 6', coerce=int, choices=choices)
    channel7 =  SelectField('Channel 7', coerce=int, choices=choices)
    channel8 =  SelectField('Channel 8', coerce=int, choices=choices)
    channel9 =  SelectField('Channel 9', coerce=int, choices=choices)
    channel10 = SelectField('Channel 10', coerce=int, choices=choices)
    channel11 = SelectField('Channel 11', coerce=int, choices=choices)
    channel12 = SelectField('Channel 12', coerce=int, choices=choices)
    channel13 = SelectField('Channel 13', coerce=int, choices=choices)
    channel14 = SelectField('Channel 14', coerce=int, choices=choices)
    channel15 = SelectField('Channel 15', coerce=int, choices=choices)
    channel16 = SelectField('Channel 16', coerce=int, choices=choices)
    channel17 = SelectField('Channel 17', coerce=int, choices=choices)
    channel18 = SelectField('Channel 18', coerce=int, choices=choices)
    channel19 = SelectField('Channel 19', coerce=int, choices=choices)
    reg0      = IntegerField('DSA', [validators.NumberRange(min=0,max=19)])
    reg1      = IntegerField('DSB', [validators.NumberRange(min=0,max=19)])
    reg2      = IntegerField('CLK', [validators.NumberRange(min=0,max=19)])
    reg3      = IntegerField('Reset Line', [validators.NumberRange(min=0,max=19)])
    dev       = IntegerField('Device', [validators.NumberRange(min=2,max=3)])
    password  = PasswordField('Password')

    def validate(self):
        if not Form.validate(self):
            return False

        result = True

        crates = {}

        for i in range(20):
            field = getattr(self, 'channel%i' % i)
            if field.data in crates:
                field.errors.append("Crate %i is already mapped to channel %i" % (field.data, crates[field.data]))
                result = False
            else:
                crates[field.data] = i

        return result

class OWLCrateMappingForm(Form):
    """
    A class for the form to update the crate map for the MTCA+s.
    """
    mtca =      IntegerField('MTCA', [validators.NumberRange(min=0,max=6)])
    channel0 =  SelectField('Channel 0', coerce=int, choices=owl_choices)
    channel1 =  SelectField('Channel 1', coerce=int, choices=owl_choices)
    channel2 =  SelectField('Channel 2', coerce=int, choices=owl_choices)
    channel3 =  SelectField('Channel 3', coerce=int, choices=owl_choices)
    channel4 =  SelectField('Channel 4', coerce=int, choices=owl_choices)
    channel5 =  SelectField('Channel 5', coerce=int, choices=owl_choices)
    channel6 =  SelectField('Channel 6', coerce=int, choices=owl_choices)
    channel7 =  SelectField('Channel 7', coerce=int, choices=owl_choices)
    channel8 =  SelectField('Channel 8', coerce=int, choices=owl_choices)
    channel9 =  SelectField('Channel 9', coerce=int, choices=owl_choices)
    channel10 = SelectField('Channel 10', coerce=int, choices=owl_choices)
    channel11 = SelectField('Channel 11', coerce=int, choices=owl_choices)
    channel12 = SelectField('Channel 12', coerce=int, choices=owl_choices)
    channel13 = SelectField('Channel 13', coerce=int, choices=owl_choices)
    channel14 = SelectField('Channel 14', coerce=int, choices=owl_choices)
    channel15 = SelectField('Channel 15', coerce=int, choices=owl_choices)
    channel16 = SelectField('Channel 16', coerce=int, choices=owl_choices)
    channel17 = SelectField('Channel 17', coerce=int, choices=owl_choices)
    channel18 = SelectField('Channel 18', coerce=int, choices=owl_choices)
    channel19 = SelectField('Channel 19', coerce=int, choices=owl_choices)
    reg0      = IntegerField('DSA', [validators.NumberRange(min=0,max=19)])
    reg1      = IntegerField('DSB', [validators.NumberRange(min=0,max=19)])
    reg2      = IntegerField('CLK', [validators.NumberRange(min=0,max=19)])
    reg3      = IntegerField('Reset Line', [validators.NumberRange(min=0,max=19)])
    dev       = IntegerField('Device', [validators.NumberRange(min=2,max=3)])
    password  = PasswordField('Password')

    def validate(self):
        if not Form.validate(self):
            return False

        result = True

        crates = {}

        for i in range(20):
            field = getattr(self, 'channel%i' % i)

            if field.data == -1:
                continue

            if field.data in crates:
                field.errors.append("Crate %i is already mapped to channel %i" % (field.data, crates[field.data]))
                result = False
            else:
                crates[field.data] = i

        return result


def get_mtca_retriggers():

    conn = engine.connect()

    result = conn.execute("SELECT * FROM mtca_retriggers ORDER BY timestamp DESC LIMIT 1")

    keys = result.keys()
    rows = result.fetchall()

    return [dict(zip(keys, row)) for row in rows]


def get_mtca_autoretriggers():

    conn = engine.connect()

    result = conn.execute("SELECT * FROM mtca_auto_retriggers ORDER BY timestamp DESC LIMIT 1")

    keys = result.keys()
    rows = result.fetchall()

    return [dict(zip(keys, row)) for row in rows]


def get_mtca_crate_mapping(mtca):
    """
    Returns a dictionary of the channel status for a single channel in the
    detector.
    """
    conn = engine.connect()

    result = conn.execute("SELECT * FROM current_mtca_crate_mapping WHERE mtca = %s",
                          (mtca,))

    if result is None:
        return None

    keys = result.keys()
    row = result.fetchone()

    return dict(zip(keys,row))

def get_mtca_crate_mapping_form(mtca):
    """
    Returns a MTCA+ crate mapping form filled in with the current crate mapping
    for a single MTCA+.
    """
    current_map = get_mtca_crate_mapping(mtca)
    formdata = {}
    formdata['mtca'] = current_map['mtca']

    for crate, channel in enumerate(current_map['crate_to_cable']):
        formdata['channel%i' % channel] = crate

    for i, value in enumerate(current_map['reg']):
        formdata['reg%i' % i] = value

    formdata['dev'] = current_map['dev']

    if mtca < 4:
        return MTCACrateMappingForm(**formdata)
    else:
        return OWLCrateMappingForm(**formdata)

def upload_mtca_crate_mapping(form):
    """
    Upload a new MTCA+ crate mapping record in the database.
    """
    conn = psycopg2.connect(dbname=app.config['DB_NAME'],
                            user=app.config['DB_EXPERT_USER'],
                            host=app.config['DB_HOST'],
                            password=form.password.data)
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

    crate_to_cable = [-1]*20

    for i in range(20):
        crate = form.data['channel%i' % i]
        if crate is not None:
            crate_to_cable[crate] = i

    reg = [form.data['reg%i' % i] for i in range(4)]

    cursor = conn.cursor()
    cursor.execute("INSERT INTO mtca_crate_mapping (mtca, crate_to_cable, reg, dev) "
        "VALUES (%s, %s, %s, %s)",
        (form.data['mtca'],
        crate_to_cable,
        reg,
        form.data['dev']))

def mtca_relay_status(mtca):
    """
    Return a list of MTC/A+ relay status of the form
    [[0, True], [1, False], ...] where the first index
    if the crate number and the second is whether or
    not the relay is stuck closed (False is stuck closed).
    Currently there is no automated way to distinguish between
    the relay being broken (or stuck open) and the channel on
    the MTC/A+ (or the CTC) being broken, so that information
    is not in the mtca_relay_status table.
    """
    conn = engine.connect()

    result = conn.execute("SELECT * FROM mtca_relay_status WHERE mtca = %s "
                          "ORDER BY timestamp DESC LIMIT 1" % (mtca,))

    keys = result.keys()
    rows = result.fetchone()

    if rows is None:
        return rows

    values = dict(zip(keys, rows))
    relay_working = []
    for crate in range(20):
        crate_str = 'crate'+str(crate)
        relay_working.append((crate, values[crate_str]))

    return relay_working
