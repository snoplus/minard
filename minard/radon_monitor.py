from .db import engine


def get_radon_monitor(run_begin, run_end):

    conn = engine.connect()

    result = conn.execute("SELECT 210po_counts, radon_monitor_run::INTEGER FROM radon_monitor WHERE radon_monitor_run >= %s AND radon_monitor_run <= %s ORDER BY radon_monitor_run DESC", (run_begin, run_end))

    keys = map(str, result.keys())
    rows = result.fetchall()

    return [dict(zip(keys, row)) for row in rows]


