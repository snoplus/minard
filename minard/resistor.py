from __future__ import print_function, division
from .db import engine

V_BP_DROP = 10 # voltage drop across backplane
R_PMT = 17100000 # resistance of PMT base

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

    r_tot = 1/sum([1/(pc_0 + resistors['r386']),1/(pc_1 + resistors['r419']),1/(pc_2 + resistors['r421']),1/(pc_3 + resistors['r420']),resistors['r151'], resistors['r252']])

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

    return actual_voltage, ideal_voltage
