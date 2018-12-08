from .db import engine_test, engine

def get_deck_activity(limit=100):
    '''
    Return a dictionary of deck activity information
    '''
    conn = engine_test.connect()

    result = conn.execute("SELECT run, timestamp, direction, location, disruptive, name, comment "
                          "FROM deck_activity ORDER BY timestamp DESC LIMIT %s", (limit,))

    if result is None:
        return None

    keys = result.keys()
    rows = result.fetchall()

    return [dict(zip(keys, row)) for row in rows]

