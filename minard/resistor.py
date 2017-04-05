from __future__ import print_function, division
from .db import engine
from wtforms import Form, DecimalField, validators, IntegerField, PasswordField

V_BP_DROP = 10 # voltage drop across backplane
R_PMT = 17100000 # resistance of PMT base

class ResistorValuesForm(Form):
    """
    A class for the form to update the PMTIC resistors.
    """
    crate =              IntegerField('crate', [validators.NumberRange(min=0,max=19)])
    slot =               IntegerField('slot', [validators.NumberRange(min=0,max=15)])
    r252 =               DecimalField('R252', places=2, [validators.required()])
    r151 =               IntegerField('R151', [validators.NumberRange(min=0)])
    r386 =               IntegerField('R386', [validators.NumberRange(min=0)])
    r387 =               IntegerField('R387', [validators.NumberRange(min=0)])
    r388 =               IntegerField('R388', [validators.NumberRange(min=0)])
    r389 =               IntegerField('R389', [validators.NumberRange(min=0)])
    r390 =               IntegerField('R390', [validators.NumberRange(min=0)])
    r391 =               IntegerField('R391', [validators.NumberRange(min=0)])
    r392 =               IntegerField('R392', [validators.NumberRange(min=0)])
    r393 =               IntegerField('R393', [validators.NumberRange(min=0)])
    r394 =               IntegerField('R394', [validators.NumberRange(min=0)])
    r395 =               IntegerField('R395', [validators.NumberRange(min=0)])
    r396 =               IntegerField('R396', [validators.NumberRange(min=0)])
    r397 =               IntegerField('R397', [validators.NumberRange(min=0)])
    r398 =               IntegerField('R398', [validators.NumberRange(min=0)])
    r399 =               IntegerField('R399', [validators.NumberRange(min=0)])
    r400 =               IntegerField('R400', [validators.NumberRange(min=0)])
    r401 =               IntegerField('R401', [validators.NumberRange(min=0)])
    r402 =               IntegerField('R402', [validators.NumberRange(min=0)])
    r403 =               IntegerField('R403', [validators.NumberRange(min=0)])
    r404 =               IntegerField('R404', [validators.NumberRange(min=0)])
    r405 =               IntegerField('R405', [validators.NumberRange(min=0)])
    r406 =               IntegerField('R406', [validators.NumberRange(min=0)])
    r407 =               IntegerField('R407', [validators.NumberRange(min=0)])
    r408 =               IntegerField('R408', [validators.NumberRange(min=0)])
    r409 =               IntegerField('R409', [validators.NumberRange(min=0)])
    r410 =               IntegerField('R410', [validators.NumberRange(min=0)])
    r411 =               IntegerField('R411', [validators.NumberRange(min=0)])
    r412 =               IntegerField('R412', [validators.NumberRange(min=0)])
    r413 =               IntegerField('R413', [validators.NumberRange(min=0)])
    r414 =               IntegerField('R414', [validators.NumberRange(min=0)])
    r415 =               IntegerField('R415', [validators.NumberRange(min=0)])
    r416 =               IntegerField('R416', [validators.NumberRange(min=0)])
    r417 =               IntegerField('R417', [validators.NumberRange(min=0)])
    r418 =               IntegerField('R418', [validators.NumberRange(min=0)])
    password =           PasswordField('Password')

def calculate_resistors(crate, slot):
    conn = engine.connect()

    result = conn.execute("SELECT * FROM pmtic_calc WHERE crate = %s AND slot = %s", (crate, slot))

    keys = result.keys()
    row = result.fetchone()

    resistors = dict(zip(keys, row))

    result = conn.execute("SELECT channel, hv FROM pmt_info WHERE crate = %s AND slot = %s ORDER BY channel", (crate, slot))

    keys = result.keys()
    rows = result.fetchall()

    # ideal voltage
    ideal_voltage = [row[1] for row in rows]

    # resistance of each paddle card
    pc_0 = 1/sum(1/(resistors['r%i' % r] + R_PMT) for r in [387,388,389,390,391,392,393,394])
    pc_1 = 1/sum(1/(resistors['r%i' % r] + R_PMT) for r in [395,396,397,398,399,400,401,402])
    pc_2 = 1/sum(1/(resistors['r%i' % r] + R_PMT) for r in [403,404,405,406,407,408,409,410])
    pc_3 = 1/sum(1/(resistors['r%i' % r] + R_PMT) for r in [411,412,413,414,415,416,417,418])

    r_tot = 1/sum([1/(pc_0 + resistors['r386']),1/(pc_1 + resistors['r419']),1/(pc_2 + resistors['r421']),1/(pc_3 + resistors['r420'])]) + \
        resistors['r151'] + resistors['r252']

    # total current
    pmtic_i = (resistors['hv_slot'] - V_BP_DROP)/r_tot

    v_to_pc = resistors['hv_slot'] - V_BP_DROP - (pmtic_i*(resistors['r252'] + resistors['r151']))

    # voltage across each paddle card
    v_pc0 = pc_0*v_to_pc/(pc_0 + resistors['r386'])
    v_pc1 = pc_1*v_to_pc/(pc_1 + resistors['r419'])
    v_pc2 = pc_2*v_to_pc/(pc_2 + resistors['r421'])
    v_pc3 = pc_3*v_to_pc/(pc_3 + resistors['r420'])

    # calculate actual voltages going to each PMT
    actual_voltage = []
    for channel in range(32):
        if channel < 8:
            actual_voltage.append((R_PMT/(R_PMT + resistors['r%i' % (387+channel)]))*v_pc0)
        elif channel < 16:
            actual_voltage.append((R_PMT/(R_PMT + resistors['r%i' % (387+channel)]))*v_pc1)
        elif channel < 24:
            actual_voltage.append((R_PMT/(R_PMT + resistors['r%i' % (387+channel)]))*v_pc2)
        elif channel < 32:
            actual_voltage.append((R_PMT/(R_PMT + resistors['r%i' % (387+channel)]))*v_pc3)

    ideal_resistors = []
    for channel in range(32):
        try:
            if channel < 8:
                ideal_resistors.append(R_PMT*(v_pc0 - ideal_voltage[channel])/ideal_voltage[channel])
            elif channel < 16:
                ideal_resistors.append(R_PMT*(v_pc1 - ideal_voltage[channel])/ideal_voltage[channel])
            elif channel < 24:
                ideal_resistors.append(R_PMT*(v_pc2 - ideal_voltage[channel])/ideal_voltage[channel])
            elif channel < 32:
                ideal_resistors.append(R_PMT*(v_pc3 - ideal_voltage[channel])/ideal_voltage[channel])
        except ZeroDivisionError:
            ideal_resistors.append(0)

    actual_resistors = [resistors['r%i' % r] for r in range(387,419)]

    return actual_voltage, ideal_voltage, ideal_resistors, actual_resistors, resistors
