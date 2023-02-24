import psycopg2
from .db import engine
from .views import app
from wtforms import Form, StringField, SelectField, validators
from wtforms.fields.html5 import EmailField
from wtforms.validators import ValidationError

VALID_COUNTRIES = [
    ('',''), # Optional empty choice
    ('usa', 'USA'),
    ('canada', 'Canada'),
    ('portugal', 'Portugal'),
    ('uk', 'UK'),
    ('germany', 'Germany'),
    ('mexico', 'Mexico')
]
FORM_KEYS = ['firstname', 'lastname', 'expert', 'supernova_expert', 'email']

class ShifterInfoForm(Form):

    firstname = StringField('First Name', [validators.DataRequired()])
    lastname = StringField('Last Name', [validators.DataRequired()])
    expert = SelectField('Expert', choices=[])
    supernova_expert = SelectField('Supernova Expert', choices=[])
    email = EmailField('Email', [validators.Email()])

def get_experts():
    """
    Returns a list of the names of all on-call experts.
    """
    conn = engine.connect()
    result = conn.execute("SELECT firstname, lastname FROM experts")
    row = result.fetchall()
    names = []
    for first, last in row:
        name = first + " " + last
        names.append((name, name))

    return names

def get_supernova_experts():
    """
    Returns a list of the names of all on-call experts.
    """
    conn = engine.connect()
    result = conn.execute("SELECT firstname, lastname FROM supernova_experts")
    row = result.fetchall()
    names = []
    for first, last in row:
        name = first + " " + last
        names.append((name, name))

    return names

def get_shifter_information():
    """
    Get some of the information about the current shifter.

    Returns the first/last name of the current shifter and the first name of
    the on-call expert.
    """
    conn = engine.connect()

    result = conn.execute("SELECT firstname, lastname, email, expert, supernova_expert "
                          "FROM current_shifter_information")

    row = result.fetchone()
    if row is None:
        return None, None, None

    email = row[2]

    shifter = ""
    expert = ""
    supernova_expert = ""

    shifter_firstname = row[0]
    shifter_lastname = row[1]
    if shifter_firstname and shifter_lastname:
        shifter = "%s %s" % \
                  (shifter_firstname.capitalize(), shifter_lastname.capitalize())

    expert_name = row[3]
    supernova_expert_name = row[4]

    return shifter, expert_name, supernova_expert_name

def set_shifter_information(form):
    """
    Update the database with the current shift information.
    """
    conn = psycopg2.connect(dbname=app.config['DB_NAME'],
                            user=app.config['DB_OPERATOR'],
                            host=app.config['DB_HOST'],
                            password=app.config['DB_OPERATOR_PASS'])
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

    cursor = conn.cursor()

    result = cursor.execute("INSERT INTO shifter_information (firstname, "
                 "lastname, email, expert, supernova_expert) "
                 "VALUES (%(firstname)s, %(lastname)s, "
                 "%(email)s, %(expert)s, %(supernova_expert)s)", form.data)
