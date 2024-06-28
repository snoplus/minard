import datetime
import grequests
import json
from . import app

MAX_ROWS_RETURNED = 2000

def getTimestamp(targetTime):
    return int(targetTime.strftime("%s")) #python2 doesn't support unix ts, but somehow this method does... on unix only

class SlowDataObject():
    def get_data_from_view_http_threaded(self, threadCount=20, server="http://couch.snopl.us", auth=(app.config['COUCH_USER'], app.config['COUCH_PASS'])):
        '''Makes a multithreaded request to the CouchDB server for data from an echolocator view.
            Returns a list of dicts with schema `{"_id": str, "key": int, "value": int}`.
            `_id` is the internal CouchDB document ID.
            `key` is the timestamp of the datapoint. `value` is the value at that time.
            :param int threadCount: The number of concurrent requests. May give a performance boost if increased/decreased.
            :param str server: The CouchDB server to request to. Override this if testing something.
            :param tuple(str, str) auth: The username/password pair to authenticate into CouchDB. Override this if testing something.'''

        interval = (self.endkey-self.startkey)//threadCount #the range of keys in each request
        intervalList = range(self.startkey, self.endkey, interval) #the breakpoints

        #the template of parameters we will pass to the request
        #we will insert the startkey and endkey in the next step
        baseThreadParams = {
            "stable": "true", # Whether to prefer returning data that has already been processed. Leave this as true unless you know what you're doing.
            "update": "lazy", #Whether to update before/after a request (if at all). Leave this as lazy unless you know what you're doing.
            "inclusive_end": "false", #avoid overlaps
            "sorted": "false", #faster to sort on our end with concurrent requests
        }

        threadParamsList = []

        #first, create many parameter dicts, with evenly-spaced start and stop keys
        for step in intervalList:
            newThreadParams = baseThreadParams.copy() #shallow copy, ie. copy by value
            newThreadParams["startkey"] = str(step)
            newThreadParams["endkey"] = str(step + interval)
            threadParamsList.append(newThreadParams)
        
        #make sure the LAST one includes the last point
        threadParamsList[-1]["inclusive_end"] = "true"
        
        startTime = datetime.datetime.now()

        #next, use grequests to submit all requests concurrently
        callList = (grequests.get(server+"/slowcontrol-data-5sec/_design/echolocator/_view/"+self.viewName,
            params=params) for params in threadParamsList) #define the requests
        responses = grequests.map(callList) #submit all requests
        responseTime = datetime.datetime.now()
        print("{0} threads returned in {1}s".format(len(responses), responseTime-startTime))

        #extract the list of "rows" from each response (the actual data)
        data = map(lambda response: response.json()['rows'], responses)
        unpackingTime = datetime.datetime.now()
        print("Unpacked threads in {0}s".format(unpackingTime-responseTime))
        
        #this is a bit tricky - the map() applies the *sort lambda* to each list in data
        #the sort lambda sorts each list of dicts by key INDIVIDUALLY of the others
        #since grequests keeps the requests in order, the data is now completely sorted
        data = map(lambda response: sorted(response, key=lambda point: point['key']), data)
        sortingTime = datetime.datetime.now()
        print("Sorted threads in {0}s".format(sortingTime-unpackingTime))

        #finally, merge each list with a reduce()
        data = reduce(lambda a, b: a+b, data)
        mergingTime = datetime.datetime.now()
        print("Merged threads in {0}s".format(mergingTime-unpackingTime))

        print("{0} rows returned in {1}s total ({2}x threaded)".format(len(data), mergingTime-startTime, threadCount))
        self.data = data

    def build_view_name(self):
        '''Constructs an echolocator view name given a datastream's ios, card, and channel.'''
        self.viewName = "{0}_{1}_{2}".format(self.ios, self.card, self.channel)
    
    def compactData(self, maxPoints=MAX_ROWS_RETURNED):
        '''Compresses the data by replacing the list with equally-spaced elements.
            :param int maxPoints: The maximal points you need/can handle.'''
        self.points = len(self.data)
        if self.points > maxPoints:
            crushFactor = int(self.points/maxPoints)
            self.data = [self.data[0]] + self.data[crushFactor:-1:crushFactor] + [self.data[-1]]

class SupplyDataObject(SlowDataObject):
    def __init__(self, datelow, datehigh, rack, voltage):
        '''Initializes a SupplyDataObject. Automatically gets specified data if valid.
            :param datetime datelow: The start date/time of the query.
            :param datetime datehigh: The end date/time of the query.
            :param int|str rack: Rack value from 1-11 or "timing".
            :param int|str voltage: Voltage value valid for that rack.'''
        self.startkey = getTimestamp(datelow)
        self.endkey = getTimestamp(datehigh)

        self.handle_input_channel(rack, voltage)
        
        self.calc_view_name()
        self.get_data_from_view_http_threaded()

        self.compactData()

    def handle_input_channel(self, rack, voltage):
        '''Verifies and sanitizes the input rack and voltage data.
            rack and voltage are not assigned to self until verified.
            Also sets the baseline value and line caption (friendly name).
            :param int|str rack: Rack value from 1-11 or "timing".
            :param int|str voltage: Voltage value valid for that rack.'''
        try: #verify rack is int OR the string "timing"
            rack = int(rack)
            self.caption = "Rack {0}: {1}V".format(voltage, rack)
        except ValueError:
            if rack == "timing":
                if voltage == "mtcd":
                    self.caption = "MTCD -2V"
                else: #0-400nhits 
                    self.caption = "Timing Rack: {0}V".format(voltage)
            else:
                raise Exception("Rack {0}was invalid.".format(rack))

        try: 
            voltage = int(voltage)
            self.baseline = voltage
        except ValueError:
            if voltage != "mtcd":
                raise Exception("Voltage {0}was invalid.".format(voltage))
            self.baseline = -2
        
        self.rack = rack
        self.voltage = voltage
    
    def calc_view_name(self):
        '''Gets the view name for a specified rack and voltage channel.
            :param int|str self.rack: Integer from 1 to 11 or "timing".
            :param int self.voltage: Valid voltage channels: 24, -24, 8, 5, -5.'''
        RACKS = list(range(1, 11+1)) + ["timing"]
        VOLTAGES = [24, -24, 8, 5, -5]
        VOLTAGES_TIMING = [24, -24, 5, -5, 6, "mtcd"]
        CARDS = ['A', 'B', 'C', 'D']
        rack = self.rack
        voltage = self.voltage
        ios = 2

        if rack not in RACKS:
            raise Exception("Rack {0} is invalid.".format(rack))
        if voltage not in VOLTAGES + VOLTAGES_TIMING: 
            raise Exception("Voltage {0} is invalid.".format(voltage))

        if rack == "timing":
            card = 'D'
            channel = VOLTAGES_TIMING.index(voltage)
            if voltage == 'mtcd':
                channel = 7
        else:
            raw_channel = 5 * RACKS.index(rack) + VOLTAGES.index(voltage)
            card = CARDS[raw_channel // 20]
            channel = raw_channel % 20

        self.ios = ios
        self.card = card
        self.channel = channel
        
        self.build_view_name()

class BaselineDataObject(SlowDataObject):
    def __init__(self, datelow, datehigh, crate, trigger):
        '''Initializes a BaselineDataObject. Automatically gets specified data if valid.
            :param datetime datelow: The start date/time of the query.
            :param datetime datehigh: The end date/time of the query.
            :param int|str crate: Crate value from 0-18.
            :param int|str trigger: Trigger value, either 20 or 100.'''
        self.startkey = getTimestamp(datelow)
        self.endkey = getTimestamp(datehigh)

        self.handle_input_channel(crate, trigger)
        
        self.calc_view_name()
        self.get_data_from_view_http_threaded()
        
        self.compactData()
    
    def handle_input_channel(self, crate, trigger):
        '''Verifies and sanitizes the input crate and trigger data.
            crate and trigger are not assigned to self until verified.
            Also sets the baseline value and line caption (friendly name).
            :param int|str crate: Crate value from 0-18.
            :param int|str trigger: Trigger value, either 20 or 100.'''
        try: #verify crate, trigger is int - this SUCKS prob just returns string always anyways
            self.crate = int(crate)
        except ValueError:
            raise Exception("Crate ({0}) was invalid.".format(crate))

        try:
            self.trigger = int(trigger)
        except ValueError:
            raise Exception("Trigger ({0}) was invalid.".format(trigger))

        self.baseline = 0 #TODO? is this correct?       
        self.caption = "Crate {0}: N{1}_BL".format(trigger, crate)

    def calc_view_name(self):
        '''Gets the view name for a specified crate and trigger baseline voltage.
            :param int self.crate: Integer from 0 to 18.
            :param int self.trigger: Integers 100, 20. (N100_BL, N20_BL)'''
        CRATES = range(0, 18+1)
        TRIGGERS = [100, 20]
        CARDS = ['A', 'B', 'C', 'D']
        crate = self.crate
        trigger = self.trigger
        ios = 4

        if crate not in CRATES: raise Exception("Crate {0} is invalid.".format(crate))
        if trigger not in TRIGGERS: raise Exception("Trigger {0} is invalid.".format(trigger))

        card = CARDS[crate // 6]
        channel = (crate % 6) * 3 + TRIGGERS.index(trigger)
        if channel >= 12: channel += 1

        self.ios = ios
        self.card = card
        self.channel = channel

        self.build_view_name()