# TODO replace this with WHERE the log will actually be stored once deployed
# alternatively add to some type of config somewhere, don't think this is how it's done in minard through

def get_roboshifter_log():
    log = ""
    with open("/home/david/alarmgui/logs/roboshifter.log", "r") as f:
        for line in reversed(list(f)):
            log += line
    return log