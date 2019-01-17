import couchdb
from .views import app
from itertools import groupby
from time import time
from uuid import uuid4
from wtforms import Form, IntegerField, StringField, TextAreaField, PasswordField,\
                    DecimalField, BooleanField, validators

def get_standard_runs():
    # This number should match the version used by ORCA
    COUCH_DOC_VERSION = app.config["ORCA_STANDARD_RUN_VERSION"]
    url = "https://%s:%s@%s" % ("snoplus", app.config["COUCHDB_PASSWORD"], app.config["COUCHDB_HOSTNAME"])
    couch = couchdb.Server(url)
    orca_db = couch['orca']
    sr_view = orca_db.view("standardRuns/getStandardRunsWithVersion")
    # standard run keys are [doc-version, run name, run version, timestamp]
    # I want to groupby by run name then within that group all run versions sorted
    # by timestamp
    rows = filter(lambda x: x.key[0] == COUCH_DOC_VERSION, sr_view.rows)
    rows = sorted(rows, key=lambda x: x.key[1] + x.key[2])
    groups = groupby(rows, lambda x: x.key[1] + x.key[2])
    groups = [(x, list(y)) for x, y in groups]
    runs = [max(group, key=lambda x: x.key[3]) for _, group in groups]
    runs = sorted(runs, key=lambda x: x.key[1])
    runs = [(x, list(y)) for x,y in groupby(runs, lambda x: x.key[1])]
    return runs

def get_standard_run(uuid):
    url = "https://%s:%s@%s" % ("snoplus", app.config["COUCHDB_PASSWORD"], app.config["COUCHDB_HOSTNAME"])
    couch = couchdb.Server(url)
    orca_db = couch['orca']
    return orca_db.get(uuid)

def update_standard_run(uuid, new_values):
    try:
        password = new_values.pop("password", None)
    except KeyError:
        raise RuntimeError("no password given")
    url = "https://%s:%s@%s" % (app.config["COUCH_DETECTOR_EXPERT_NAME"],
                                password,
                                app.config["COUCHDB_HOSTNAME"])
    couch = couchdb.Server(url)
    try:
        orca_db = couch['orca']
    except couchdb.http.Unauthorized:
        raise RuntimeError("Incorrect password given")

    doc = dict(orca_db.get(uuid))
    for k, v in new_values.iteritems():
        doc[k] = v
    doc["_id"] = uuid4().hex
    doc["time_stamp"] = time()

    if not doc.has_key("run_version") or not doc["run_version"]:
        raise RuntimeError("run_version must be present in new document")

    if not doc.has_key("run_type") or not doc["run_type"]:
        raise RuntimeError("run_type must be present in new document")

    doc["run_type"] = doc["run_type"].upper()
    doc["run_version"] = doc["run_version"].upper()

    # Remove revision field since we want to post a new document, not a
    # revision of an existing one.
    try:
        del doc["_rev"]
    except KeyError:
        pass

    new_uuid, _ = orca_db.save(doc)
    return new_uuid

expected_fields = [
            IntegerField("CAEN_acquisitionMode", [validators.NumberRange(min=0, max=0b111)]),
            IntegerField("CAEN_channelConfigMask"),
            IntegerField("CAEN_coincidenceLevel"),
            BooleanField("CAEN_countAllTriggers"),
            IntegerField("CAEN_customSize"),
            IntegerField("CAEN_dac_0", [validators.NumberRange(min=0, max=0xFFFF)]),
            IntegerField("CAEN_dac_1", [validators.NumberRange(min=0, max=0xFFFF)]),
            IntegerField("CAEN_dac_2", [validators.NumberRange(min=0, max=0xFFFF)]),
            IntegerField("CAEN_dac_3", [validators.NumberRange(min=0, max=0xFFFF)]),
            IntegerField("CAEN_dac_4", [validators.NumberRange(min=0, max=0xFFFF)]),
            IntegerField("CAEN_dac_5", [validators.NumberRange(min=0, max=0xFFFF)]),
            IntegerField("CAEN_dac_6", [validators.NumberRange(min=0, max=0xFFFF)]),
            IntegerField("CAEN_dac_7", [validators.NumberRange(min=0, max=0xFFFF)]),
            IntegerField("CAEN_enabledMask", [validators.NumberRange(min=0, max=0xFF)]),
            IntegerField("CAEN_eventSize"),
            IntegerField("CAEN_frontPanelControlMask"),
            BooleanField("CAEN_isCustomSize"),
            IntegerField("CAEN_postTriggerSetting"),
            IntegerField("CAEN_triggerOutMask"),
            IntegerField("CAEN_triggerSourceMask"),
            IntegerField("MTC_ESUMH_Threshold", [validators.NumberRange(min=0,max=4095)]),
            IntegerField("MTC_ESUML_Threshold", [validators.NumberRange(min=0,max=4095)]),
            IntegerField("MTC_GTMask", [validators.NumberRange(min=0, max=0x3FFFFFF)]),
            IntegerField("MTC_LockoutWidth", [validators.NumberRange(min=20, max=5000)]),
            IntegerField("MTC_N100H_Threshold", [validators.NumberRange(min=0, max=4095)]),
            IntegerField("MTC_N100L_Threshold", [validators.NumberRange(min=0, max=4095)]),
            IntegerField("MTC_N100M_Threshold", [validators.NumberRange(min=0, max=4095)]),
            IntegerField("MTC_N20LB_Threshold", [validators.NumberRange(min=0, max=4095)]),
            IntegerField("MTC_N20_Threshold", [validators.NumberRange(min=0, max=4095)]),
            IntegerField("MTC_OWLEH_Threshold", [validators.NumberRange(min=0, max=4095)]),
            IntegerField("MTC_OWLEL_Threshold", [validators.NumberRange(min=0, max=4095)]),
            IntegerField("MTC_OWLN_Threshold", [validators.NumberRange(min=0, max=4095)]),
            IntegerField("MTC_PrescaleValue", [validators.NumberRange(min=2, max=65536)]),
            BooleanField("MTC_PulserEnabled"),
            BooleanField("MTC_PulserMode"),
            DecimalField("MTC_PulserRate", [validators.NumberRange(min=0.04, max=390000)]),
            IntegerField("TUBii_CaenChannelMask", [validators.NumberRange(min=0, max=255)]),
            IntegerField("TUBii_CaenGainMask", [validators.NumberRange(min=0, max=255)]),
            IntegerField("TUBii_DGT_Bits", [validators.NumberRange(min=0, max=255)]),
            IntegerField("TUBii_LO_Bits", [validators.NumberRange(min=0, max=255)]),
            IntegerField("TUBii_MTCAMimic1_ThresholdInBits", [validators.NumberRange(min=0, max=4095)]),
            IntegerField("TUBii_TUBiiPGT_Rate", [validators.NumberRange(min=0)]),
            IntegerField("TUBii_asyncTrigMask"),
            IntegerField('TUBii_controlReg', [validators.NumberRange(min=0,max=255)]),
            IntegerField('TUBii_counterMask', [validators.NumberRange(min=0)]),
            IntegerField('TUBii_speakerMask', [validators.NumberRange(min=0)]),
            IntegerField('TUBii_syncTrigMask', [validators.NumberRange(min=0)]),
            IntegerField("run_type_word", [validators.NumberRange(min=0x0, max=0xFFFFFFF)]),
            StringField("run_version", [validators.DataRequired()]),
            StringField("type", [validators.DataRequired()])
]
expected_fields = dict([(x.args[0], x) for x in expected_fields])

def create_form(fields):
    class SRSettingsForm(Form):
        name = StringField('Name', [validators.DataRequired()])
        info = TextAreaField('Info', [validators.DataRequired()])
        password = PasswordField('Password', [validators.DataRequired()])

    # First create a form for the various fields in the couchDB doc
    for key, value in fields.iteritems():
        # skip any fields that are already in the form
        if key.lower() in ["name", "info", "password"]:
            continue
        if expected_fields.has_key(key):
            field = expected_fields[key]
            setattr(SRSettingsForm, key, field)
        else:
            setattr(SRSettingsForm, key, StringField(key))
    return SRSettingsForm
