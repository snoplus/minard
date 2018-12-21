from .db import engine_nl
import json
from math import log10

def get_details(run_number, trigger_type):
    conn = engine_nl.connect()
    command = ("select f.rate, f.peak_offset, f.sigma, f.separation, p.x_vals, "
    "p.y_vals, p.fit_vals, p.chisqr, p.normalization from dropout_fits as f INNER JOIN dropout_plots as p "
    "on f.fit_plot=p.key where p.run=%s and p.trigger_type=%s")
    result = conn.execute(command, (run_number, trigger_type));
    keys = result.keys()
    data = result.fetchone()
    try:
        return json.dumps(dict(zip(keys, data)))
    except TypeError:
        return json.dumps(None)

def get_fits(trigger_type=0, run_range=None):
    """
    """
    trigger_type = 1 if trigger_type == 0 else 2
    args = (trigger_type,)
    clause = " ORDER BY plots.run DESC"
    if run_range is not None:
        if type(run_range) == int:
            clause = clause + " LIMIT %s"
            args = (trigger_type, run_range)
        else:
            try:
                clause = " AND plots.run >= %s AND plots.run < %s" + clause
                args = (trigger_type, run_range[0], run_range[1])
            except Exception as e:
                raise ValueError("Could not use given run_range, must be int or pair")
    command = ("SELECT plots.run, fit.rate, plots.chisqr FROM dropout_fits AS fit "
    "INNER JOIN dropout_plots AS plots ON "
    "fit.fit_plot=plots.key where trigger_type=%s")
    command += clause

    conn = engine_nl.connect()
    result = conn.execute(command, args)

    ret = result.fetchall()
    ret = [list(x) for x in ret]
    return json.dumps(ret)
