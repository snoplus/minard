from redis import Redis

redis = Redis()

def add_run_to_db(key_index, run_dict):
    '''
    Creates Redis entries for a run. Requires run_number and time keys in 
    run_dict
    '''
    key = '%s%s' % (key_index, run_dict['run_number'])
    p = redis.pipeline()
    p.hmset(key, run_dict)
    p.expire(key, 604800)
    p.zadd(RUN_INDEX, key, float(run_dict['run_number']))
    p.zadd(TIME_INDEX, key, float(run_dict['run_time']))
    return p.execute()  
    
def runs_after_time(TIME_INDEX, time, maxtime = '+inf'):
    '''
    Returns Redis entries for all runs between time and maxtime. 
    Requires Redis instance, start-time and maximum time.
    '''
    keys = redis.zrangebyscore(TIME_INDEX, time, maxtime)
    p = redis.pipeline()
    for key in keys:
        p.hgetall(key)
    return p.execute()    
        
def runs_after_run(RUN_INDEX, run, maxrun = '+inf'):
    '''
    Returns Redis entries for all runs between run and maxrun. 
    Requires Redis instance, start-run and maximum run.
    '''
    keys = redis.zrangebyscore(RUN_INDEX, run, maxrun)
    p = redis.pipeline()
    for key in keys:
        p.hgetall(key)
    return p.execute()    

def get_run_by_number(RUN_INDEX, runnum):
    '''
    Returns Redis entries for specific run by run number
    Requires Redis instance, and run number.
    '''
    keys = redis.zrangebyscore(RUN_INDEX, runnum, runnum)
    p = redis.pipeline()
    for key in keys:
        p.hgetall(key)
    return p.execute()    

def get_run_status(key_index, runnum):
    '''
    Returns run status for specific run by run number
    Requires Redis instance, and run number.
    '''
    return redis.hget("%s%i" % (key_index, int(runnum)), "run_status")

def del_run_from_db(key_index, run_number):
    '''
    Delete run from Redis. Requires Redis instance and run number. 
    '''
    key = '%s%s' % (key_index, run_number)
    p = redis.pipeline()
    p.delete(key)
    p.zrem(RUN_INDEX, key)
    p.zrem(TIME_INDEX, key)
    return p.execute()
 
