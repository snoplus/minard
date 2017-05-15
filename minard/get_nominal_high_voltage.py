from __future__ import print_function, division
import sqlalchemy

V_BP_DROP = 10 # voltage drop across backplane
R_PMT = 17100000 # resistance of PMT base

engine = sqlalchemy.create_engine('postgresql://%s:%s@%s:%i/%s' %
                                 ('snoplus', 'dontestopmenow',
                                  'dbug.sp.snolab.ca', 5432,
                                  'detector'))

def get_resistor_values(crate, slot):
    """
    Returns a dictionary of the resistor values for a single card in the
    detector.
    """
    conn = engine.connect()

    result = conn.execute("SELECT * FROM pmtic_calc "
        "WHERE crate = %s AND slot = %s",
        (crate,slot))

    keys = result.keys()
    row = result.fetchone()

    return dict(zip(keys,row))

def get_resistor_values_form(crate, slot):
    """
    Returns a resistor values form filled in with the current resistor values for
    a single card in the detector.
    """
    return ResistorValuesForm(**get_resistor_values(crate, slot))

def get_hv_nominal(crate, slot):
    """
    Returns the nominal HV for a given crate and slot. The slot is necessary
    since the OWL slots are actually powered from the 'B' supply on crate 16.
    """
    conn = engine.connect()

    if crate in (3,13,18) and slot == 15:
        result = conn.execute("SELECT nominal FROM hvparams WHERE crate = %s AND supply = %s", (16, 'B'))
    else:
        result = conn.execute("SELECT nominal FROM hvparams WHERE crate = %s AND supply = %s", (crate, 'A'))

    return result.fetchone()[0]

def get_resistors(crate, slot):
    """
    Returns a dictionary containing information about the PMTIC resistors
    including the actual and ideal resistors and voltages.
    """
    conn = engine.connect()

    resistors = get_resistor_values(crate, slot)

    nominal_hv = get_hv_nominal(crate, slot)

    result = conn.execute("SELECT voltage_drop FROM hv_backplane WHERE crate = %s AND supply = %s", (crate, resistors['supply']))

    voltage_drop = result.fetchone()[0]

    result = conn.execute("SELECT channel, hv FROM pmt_info WHERE crate = %s AND slot = %s ORDER BY channel", (crate, slot))

    keys = result.keys()
    rows = result.fetchall()

    # ideal voltages for each PMT. These were determined during testing by
    # finding the voltage at which the PMT had a gain of 1e7
    ideal_voltages = [row[1] for row in rows]

    # resistance of each paddle card
    pc_0 = 1/sum(1/(resistors['r%i' % r] + R_PMT) for r in [387,388,389,390,391,392,393,394])
    pc_1 = 1/sum(1/(resistors['r%i' % r] + R_PMT) for r in [395,396,397,398,399,400,401,402])
    pc_2 = 1/sum(1/(resistors['r%i' % r] + R_PMT) for r in [403,404,405,406,407,408,409,410])
    pc_3 = 1/sum(1/(resistors['r%i' % r] + R_PMT) for r in [411,412,413,414,415,416,417,418])

    r_tot = 1/sum([1/(pc_0 + resistors['r386']),1/(pc_1 + resistors['r419']),1/(pc_2 + resistors['r421']),1/(pc_3 + resistors['r420'])]) + \
        resistors['r151'] + resistors['r252']

    # total current
    pmtic_i = (nominal_hv - V_BP_DROP - voltage_drop)/r_tot

    v_to_pc = nominal_hv - V_BP_DROP - voltage_drop - (pmtic_i*(resistors['r252'] + resistors['r151']))

    # voltage across each paddle card
    v_pc0 = pc_0*v_to_pc/(pc_0 + resistors['r386'])
    v_pc1 = pc_1*v_to_pc/(pc_1 + resistors['r419'])
    v_pc2 = pc_2*v_to_pc/(pc_2 + resistors['r421'])
    v_pc3 = pc_3*v_to_pc/(pc_3 + resistors['r420'])

    # calculate actual voltages going to each PMT
    actual_voltages = []
    for channel in range(32):
        if channel < 8:
            actual_voltages.append((R_PMT/(R_PMT + resistors['r%i' % (387+channel)]))*v_pc0)
        elif channel < 16:
            actual_voltages.append((R_PMT/(R_PMT + resistors['r%i' % (387+channel)]))*v_pc1)
        elif channel < 24:
            actual_voltages.append((R_PMT/(R_PMT + resistors['r%i' % (387+channel)]))*v_pc2)
        elif channel < 32:
            actual_voltages.append((R_PMT/(R_PMT + resistors['r%i' % (387+channel)]))*v_pc3)

    ideal_resistors = []
    for channel in range(32):
        try:
            if channel < 8:
                ideal_resistors.append(R_PMT*(v_pc0 - ideal_voltages[channel])/ideal_voltages[channel])
            elif channel < 16:
                ideal_resistors.append(R_PMT*(v_pc1 - ideal_voltages[channel])/ideal_voltages[channel])
            elif channel < 24:
                ideal_resistors.append(R_PMT*(v_pc2 - ideal_voltages[channel])/ideal_voltages[channel])
            elif channel < 32:
                ideal_resistors.append(R_PMT*(v_pc3 - ideal_voltages[channel])/ideal_voltages[channel])
        except ZeroDivisionError:
            ideal_resistors.append(0)

    actual_resistors = [resistors['r%i' % r] for r in range(387,419)]

    # return a dictionary since there is a lot of info
    resistors['pc0'] = pc_0
    resistors['pc1'] = pc_1
    resistors['pc2'] = pc_2
    resistors['pc3'] = pc_3
    resistors['v_to_pc'] = v_to_pc
    resistors['v_pc0'] = v_pc0
    resistors['v_pc1'] = v_pc1
    resistors['v_pc2'] = v_pc2
    resistors['v_pc3'] = v_pc3
    resistors['r_tot'] = r_tot
    resistors['pmtic_i'] = pmtic_i
    resistors['ideal_voltages'] = ideal_voltages
    resistors['actual_voltages'] = actual_voltages
    resistors['ideal_resistors'] = ideal_resistors
    resistors['actual_resistors'] = actual_resistors
    resistors['nominal_hv'] = nominal_hv
    resistors['supply_voltage'] = nominal_hv - voltage_drop

    return resistors

if __name__ == '__main__':
    import argparse
    import numpy as np

    parser = argparse.ArgumentParser("Calculate the nominal HV for each supply")
    parser.add_argument("-c", "--crate", type=int, help="crate", required=True)
    parser.add_argument("--plot", action='store_true', help="plot results")
    args = parser.parse_args()

    differences = []
    for slot in range(16):
        if args.crate in (3,13,18) and slot == 15:
            # don't analyze owl hv
            continue

        resistors = get_resistors(args.crate, slot)
        for channel in range(32):
            difference = resistors['ideal_voltages'][channel]-resistors['actual_voltages'][channel]

            if abs(difference) < 1000:
                differences.append(difference)

    print("avg difference = %.2f" % np.mean(differences))
    print("median difference = %.2f" % np.median(differences))

    if args.plot:
        import matplotlib.pyplot as plt
        plt.hist(differences, bins=np.linspace(-200,200,1000))
        plt.xlabel("Ideal - Actual Voltage (V)")
        plt.title("Ideal - Actual Voltage for Crate %i" % args.crate)
        plt.show()
