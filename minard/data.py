from __future__ import division
from itertools import repeat
import struct
import numpy as np
from redis import Redis
import time
from minard.redistools import hmincrby, hmincrbyfloat, hdivh, hmincr, setavgmax
from minard.timeseries import HASH_INTERVALS, HASH_EXPIRE
from snotdaq import DataStream

redis = Redis()

# number of seconds to keep CMOS records
EXPIRE = 60

def parse_cmos(rec):
    """Parse a CMOS record."""
    crate, slot_mask = struct.unpack('>II', rec[:8])
    channel_mask = np.frombuffer(rec[8:8+4*16], dtype='>u4')
    error_flags = struct.unpack('>I',rec[72:72+4])
    counts = np.frombuffer(rec[76:76+8*32*4], dtype='>u4')
    # XL3 should really send us the timestamp, but for now
    # we just use the time we receive it
    timestamp = time.time()
    return crate, slot_mask, channel_mask, error_flags, counts, timestamp

def parse_base(rec):
    """Parse a base current record."""
    crate, slot_mask = struct.unpack('>II', rec[:8])
    channel_mask = np.frombuffer(rec[8:8+4*16], dtype='>u4')
    error_flags = struct.unpack('>I',rec[72:72+4])
    counts = np.frombuffer(rec[76:76+16*32], dtype='>u1').reshape((16,-1))
    busy = np.frombuffer(rec[76+16*32:76+16*32+16*32], dtype='>u1').reshape((16,-1))
    timestamp = time.time()
    return crate, slot_mask, channel_mask, error_flags, counts, busy, timestamp

def unpack_index(index):
    """Returns (crate, card, channel) for a channel index."""
    return index >> 9, index >> 5 & 0xf, index & 0x1f

def flush_to_redis(dict_, name, time_):
    p = redis.pipeline()

    sum_keys = ['ts:%i:%i:%s:sum' % (interval, time_//interval, name)
                for interval in HASH_INTERVALS]
    len_keys = ['ts:%i:%i:%s:len' % (interval, time_//interval, name)
                for interval in HASH_INTERVALS]

    if len(dict_) > 0:
        hmincrbyfloat(sum_keys, dict_, client=p)
        hmincr(len_keys, dict_.keys(), client=p)

    for interval in HASH_INTERVALS:
        basekey = 'ts:%i:%i:%s' % (interval, time_//interval, name)
        if len(dict_) > 0:
            p.expire(basekey + ':sum', interval)
            p.expire(basekey + ':len', interval)
        prev = time_//interval - 1
        prev_key = 'ts:%i:%i:%s' % (interval, prev, name)
        if redis.incr(prev_key + ':lock') == 1:
            hdivh(prev_key, prev_key + ':sum', prev_key + ':len',
                  range(10240), format='%.2g', client=p)
            keys = setavgmax(prev_key, client=p)
            for k in keys:
                p.expire(k, HASH_EXPIRE*interval)
            p.expire(prev_key, HASH_EXPIRE*interval)
            p.expire(prev_key + ':lock', interval)
    p.execute()
