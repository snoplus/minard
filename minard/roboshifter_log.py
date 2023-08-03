import os

from wtforms.fields.html5 import DateField
from wtforms import Form

from datetime import date

# TODO replace this with WHERE the log will actually be stored once deployed
# alternatively add to some type of config somewhere, don't think this is how it's done in minard through
LOG_DIR = '/home/david/alarmgui/logs/'

class RoboshifterLogDateForm(Form):
    date = DateField(label="Log Date", render_kw={"onchange": "this.form.submit()"})

def get_roboshifter_log():
    log = ""
    with open(LOG_DIR + "roboshifter.log", "r") as f:
        for line in reversed(list(f)):
            log += line
    return log

def get_historic_roboshifter_log(datestring):
    log = ""
    with open(LOG_DIR + "roboshifter.log" + "." + datestring) as f:
        for line in reversed(list(f)):
            log += line
    return log
