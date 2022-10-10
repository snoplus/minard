#!/usr/bin/python
"""
classes and functions for loading ratdb files

These methods return a dict subclass that supports case-insensitive substring
key searches.

For example:
>>> from calib import ratdb
>>> run = ratdb.load_run_directory("data/run6708")
>>> run.keys()
['path', 'PCAGF_20000_20', 'PCA_log_20000_20', 'PCATW_20000_20', 'name']
>>> run['PCATW_20000_20'].keys()
[u'run_range', u'twinter', u'name', u'twinterrms', u'PCATW_status',
 u'tw_npoints', u'is_sno']
>>> # The following command takes advantage of the fuzzy key matching and is a
>>> # shortcut for len(run['PCATW_20000_20']['PCATW_status'])
>>> len(run['tw']['status'])
9728
>>> [lcn for lcn, status in enumerate(run['tw']['status']) if status > 5]
[720, 722, ..., 9690, 9691]

"""
import json
import os


class FuzzyDict(dict):
    """
    A dict subclass that gives case-insensitive "x in y" substring key lookup
    when unambiguous matches can be found. fixme: word this better

    For example, in a dict:
    record = FuzzyDict({"ProductStandardName": 'apple',
                        "ProductColor": 'red',
                        "ProductKind": 'fruit'})
    >>> record['name']
    'apple'
    >>> record['product']
    KeyError: 'Fuzzy key "product" is ambiguous; matches: ProductStandardName,
     ProductKind, ProductColor'

    Designed to be used with dicts that don't change much after creation.
    There is an internal search cache that never invalidates
    """
    keyview = None
    cache = None

    def __init__(self, *args, **kwargs):
        super(FuzzyDict, self).__init__(*args, **kwargs)
        self.keyview = self.viewkeys()
        self.cache = dict()


    def __missing__(self, fuzzy_key):
        cache = self.cache
        if fuzzy_key in cache:
            return self[cache[fuzzy_key]]

        lc_fuzzy_key = fuzzy_key.lower()
        matching_keys = [key for key in self.keyview
                         if lc_fuzzy_key in key.lower()]
        match_count = len(matching_keys)

        if match_count > 1:
            # ambiguous match
            raise KeyError('Fuzzy key "{}" is ambiguous; matches: {}'.format(
                fuzzy_key, ", ".join(matching_keys)))
        elif match_count < 1:
            raise KeyError('Fuzzy key "{}" did not match any keys'.format(
                fuzzy_key))

        # it worked
        match = matching_keys[0]
        cache[fuzzy_key] = match
        return self[match]


def load_ratdb(file_path):
    """
    Return the result of json.load on the given .ratdb file. They result
    should typically be a dict
    """
    print file_path
    with open(file_path, 'r') as input_file:
        try:
            print 'Input File: ', input_file
            return FuzzyDict(json.load(input_file))
        except:
            raise RuntimeError("Failed in {}".format(file_path))



def load_run_directory(run_directory):
    """
    Return a fuzzydict of {"filename": load_ratdb(filename)} items, for each
    ratdb file found in the specified run_directory. The result dict is also
    enhanced with some hint keys and a "directory" item for easier use.

    A {"path": run_directory} item is added for convenience.
    A {"name": basename(run_directory)} item is added for convenience.
    """
    dirfiles = lambda path: [dirent for dirent in os.listdir(path)
                             if os.path.isfile(os.path.join(path, dirent))]
    for i in dirfiles(run_directory):
	if i.endswith(".ratdb"):
	  print i
    data = FuzzyDict([(os.path.splitext(filename)[0],
                       load_ratdb(os.path.join(run_directory, filename)))
                      for filename in dirfiles(run_directory)
                      if filename.endswith(".ratdb")])

    data['path'] = run_directory
    data['name'] = os.path.basename(run_directory)
#    data['number'] = os.path.basename(run_directory).lstrip('run')
    data['in_rat'] = os.path.exists(os.path.join(run_directory, 'IN_RAT'))

    return data


###Not used###
def load_eca_logfiles(run_directory):
    """
    Return a fuzzydict of {"filename": load_ratdb(filename)} items, for each
    Analysis_log* file found in the specified run_directory. The result dict is also
    enhanced with some hint keys and a "directory" item for easier use.

    A {"path": run_directory} item is added for convenience.
    A {"name": basename(run_directory)} item is added for convenience.
    """
    dirfiles = lambda path: [dirent for dirent in os.listdir(path)
                             if os.path.isfile(os.path.join(path, dirent))]

    data = FuzzyDict([(os.path.splitext(filename)[0],
                       load_ratdb(os.path.join(run_directory, filename)))
                      for filename in dirfiles(run_directory)
                      if filename.startswith("Analysis_log") ])

    data['path'] = run_directory
    data['name'] = os.path.basename(run_directory)
#    data['number'] = os.path.basename(run_directory).lstrip('run')
    data['in_rat'] = os.path.exists(os.path.join(run_directory, 'IN_RAT'))

    return data
