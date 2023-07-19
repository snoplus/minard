import os

# TODO replace this with WHERE the log will actually be stored once deployed
# alternatively add to some type of config somewhere, don't think this is how it's done in minard through
LOG_DIR = '/home/david/alarmgui/logs/'


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

def get_roboshifter_log_dates():
    dates = []
    logfiles = os.listdir(LOG_DIR)
    for l in logfiles:
        if l != "roboshifter.log":
            dates.append(l[len(l) - 13:])
    return dates