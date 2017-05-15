from __future__ import division
from itertools import repeat
import struct
import zmq
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

def cmos_consumer(port):
    pull_context = zmq.Context()
    pull = pull_context.socket(zmq.PULL)
    pull.connect('tcp://127.0.0.1:%s' % port)

    cmos_rates = {}

    then = None
    while True:
        now = int(time.time())

        try:
            id, rec = pull.recv_pyobj(zmq.NOBLOCK)
        except zmq.ZMQError:
            # timeout
            id = None

        if now > then and len(cmos_rates) > 0:
            # flush results to database once a second
            flush_to_redis(cmos_rates, 'cmos', then)
            then = None
            cmos_rates.clear()

        if id is None:
            time.sleep(0.1)
            continue

        if id != 'CMOS':
            raise ValueError('Expected CMOS record, got record %i' % id)

        if then is None:
            then = now

        crate, slotmask, channelmask, error_flags, counts, timestamp = \
            parse_cmos(rec)

	if slotmask == 0:
	    continue

        cards = np.array([i for i in range(16) if (slotmask >> i) & 1])
        indices = (crate << 9 | cards[:,np.newaxis] << 5 | np.arange(32)).flatten()

        # set new times/counts
        p = redis.pipeline()
        p.hmget('cmos:count:%i' % crate, indices)
        p.hmget('cmos:timestamp:%i' % crate, indices)
        p.hmset('cmos:count:%i' % crate, dict(zip(indices, counts)))
        p.hmset('cmos:timestamp:%i' % crate, dict(zip(indices, repeat(timestamp))))
        last_counts, last_timestamps, _, _ = p.execute()

        for index, count, last_count, last_timestamp in \
                zip(indices, counts, last_counts, last_timestamps):
            _, card, channel = unpack_index(index)

            if (not channelmask[card] & (1 << channel)
                or count >> 31
                or last_count is None):
                continue

            # time delta between cmos counts (seconds)
            dt = timestamp - float(last_timestamp)

            if 0 < dt < 10 and count > int(last_count):
                rate = (count-int(last_count))/dt
                # time series
                cmos_rates[index] = rate

def base_consumer(port):
    pull_context = zmq.Context()
    pull = pull_context.socket(zmq.PULL)
    pull.connect('tcp://127.0.0.1:%s' % port)

    base_currents = {}

    then = None
    while True:
        now = int(time.time())
        try:
            id, rec = pull.recv_pyobj(zmq.NOBLOCK)
        except zmq.ZMQError:
            # timeout
            id = None

        if now > then and len(base_currents) > 0:
            flush_to_redis(base_currents, 'base', then)
            then = None
            base_currents.clear()

        if id is None:
            time.sleep(0.1)
            continue

        if id != 'BASE':
            raise ValueError("Expected base current record got id %i" % id)

        if then is None:
            then = now

        crate, slotmask, channelmask, error_flags, counts, busy, timestamp = \
            parse_base(rec)

        for i, slot in enumerate(i for i in range(16) if (slotmask >> i) & 1):
            for j, value in enumerate(map(int,counts[slot])):
                if not channelmask[slot] & (1 << j) or value >> 31:
                    continue

                index = crate << 9 | slot << 5 | j

                base_currents[index] = value - 127

def data_producer(host, port=4000):
    """
    Pushes CMOS and base current records to a ZMQ Push/Pull socket
    to be parsed by other workers. CMOS rates and base currents are
    pushed to ports 5557 and 5558 respectively.
    See `zeromq.org <http://zeromq.org>`_ for more information.
    """
    data = DataStream(host, port=port, subscriptions=['CMOS','BASE'],
		      timeout=None)
    data.connect()

    cmos_context = zmq.Context()
    cmos = cmos_context.socket(zmq.PUSH)
    cmos.bind('tcp://127.0.0.1:5557')

    base_context = zmq.Context()
    base = base_context.socket(zmq.PUSH)
    base.bind('tcp://127.0.0.1:5558')

    while True:
        id, rec = data.recv_record()
        if id == 'CMOS':
            cmos.send_pyobj((id,rec))

        if id == 'BASE':
            base.send_pyobj((id,rec))
