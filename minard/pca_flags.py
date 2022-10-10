"""
Constants related to PCA runs

The creation of this file has been a manual process. 

I've been using this search:
^.+?\[(\d+)\]\s+?\=\s+\"(.+?)\";\s*(\/\/\s*(.+)\s*)?$
and this replace:
{'bit': $1, 'name': "$2", 'doc': "$4", 'type': 'info'},
"""

status_word_count = 9728

modes = {
    'tw': "Time Walk",
    'gf': "Gain Fit",
    'log': "Run Log"
}

colors = {'info':  (91,192,222), # light blue
          'danger':  (217,83,79), # red
          'warning': (240,173,78)} # orange

# order and blanks are important!
flags = {
    'log': [
        {'bit': 0, 'name': "status PCA", 'doc': "OR of bits 1-31 ", 'type': 'info'},
        {'bit': 1, 'name': "status TW", 'doc': "OR of bits 8-19", 'type': 'info'},
        {'bit': 2, 'name': "status GF", 'doc': "OR of bits 20-31", 'type': 'info'},
        {'bit': 3, 'name': "too many channels offline", 'doc': "", 'type': 'info'},
        {'bit': 4, 'name': "too many online channels that have 0 occupancy", 'doc': "", 'type': 'info'},
        {'bit': 5, 'name': "too many channels that have low occupancy", 'doc': "", 'type': 'info'},
        {'bit': 6, 'name': "overall high occupancy", 'doc': "", 'type': 'info'},
        {'bit': 7, 'name': "did not reach end of run", 'doc': "", 'type': 'info'},
        {'bit': 8, 'name': "N channels with very high RMS > max", 'doc': "", 'type': 'info'},
        {'bit': 9, 'name': "N channels with too high RMS > max", 'doc': "", 'type': 'info'},
        {'bit': 10, 'name': "N channels with no fit to high Q tail > max", 'doc': "", 'type': 'info'},
        {'bit': 11, 'name': "N channels with Tstep warning > max", 'doc': "", 'type': 'info'},
        {'bit': 12, 'name': "N channels with Flate warning > max", 'doc': "", 'type': 'info'},
        {'bit': 13, 'name': "N channels with Fout warning > max", 'doc': "", 'type': 'info'},
        {'bit': 14, 'name': "N channels with missing points warning > max", 'doc': "", 'type': 'info'},
        {'bit': 15, 'name': "TW spare", 'doc': "", 'type': 'info'},
        {'bit': 16, 'name': "TW spare", 'doc': "", 'type': 'info'},
        {'bit': 17, 'name': "TW spare", 'doc': "", 'type': 'info'},
        {'bit': 18, 'name': "TW spare", 'doc': "", 'type': 'info'},
        {'bit': 19, 'name': "TW spare", 'doc': "", 'type': 'info'},
        {'bit': 20, 'name': "too many (#PMTs with d(QHS TH) too large)", 'doc': "", 'type': 'info'},
        {'bit': 21, 'name': "too many (#PMTs with d(QHS PK) too large)", 'doc': "", 'type': 'info'},
        {'bit': 22, 'name': "too many (#PMTs with d(QHS HP) too large)", 'doc': "", 'type': 'info'},
        {'bit': 23, 'name': "too many (#PMTs with d(QHL TH) too large)", 'doc': "", 'type': 'info'},
        {'bit': 24, 'name': "too many (#PMTs with d(QHL PK) too large)", 'doc': "", 'type': 'info'},
        {'bit': 25, 'name': "too many (#PMTs with d(QHL HP) too large)", 'doc': "", 'type': 'info'},
        {'bit': 26, 'name': "too many (#PMTs with QHS TH too high)", 'doc': "", 'type': 'info'},
        {'bit': 27, 'name': "too many (#PMTs with QHL TH too high)", 'doc': "", 'type': 'info'},
        {'bit': 28, 'name': "too many (#PMTs with peak finder)", 'doc': "", 'type': 'info'},
        {'bit': 29, 'name': "too many (#PMTs with QHS TH too low)", 'doc': "", 'type': 'info'},
        {'bit': 30, 'name': "too many (#PMTs with QHL TH too low)", 'doc': "", 'type': 'info'},
        {'bit': 31, 'name': "GF spare", 'doc': "", 'type': 'info'}],
    'gf': [
        {'bit': 0, 'name': "status", 'doc': "OR of bits 1-31", 'type': 'info'},
        {'bit': 1, 'name': "channel offline", 'doc': "FAIL tube is marked as off in DQXX", 'type': 'info'},
        {'bit': 2, 'name': "zero occupancy QHS", 'doc': "FAIL tube is marked as on in DQXX but did not see any hits", 'type': 'danger'},
        {'bit': 3, 'name': "low occupancy", 'doc': "FAIL tube saw less than min hits", 'type': 'danger'},
        {'bit': 4, 'name': "< 100 hits in 100-bin window for QHS", 'doc': "FAIL", 'type': 'warning'},
        {'bit': 5, 'name': "< 100 hits in 100-bin window for QHL", 'doc': "FAIL", 'type': 'warning'},
        {'bit': 6, 'name': "spare", 'doc': "", 'type': 'warning'},
        {'bit': 7, 'name': "spare", 'doc': "", 'type': 'warning'},
        {'bit': 8, 'name': "spare", 'doc': "", 'type': 'warning'},
        {'bit': 9, 'name': "spare", 'doc': "", 'type': 'warning'},
        {'bit': 10, 'name': "QHS TH diff too large", 'doc': "WARN", 'type': 'warning'},
        {'bit': 11, 'name': "QHS PK diff too large", 'doc': "WARN", 'type': 'warning'},
        {'bit': 12, 'name': "QHS HP diff too large", 'doc': "WARN", 'type': 'warning'},
        {'bit': 13, 'name': "QHL TH diff too large", 'doc': "WARN", 'type': 'warning'},
        {'bit': 14, 'name': "QHL PK diff too large", 'doc': "WARN", 'type': 'warning'},
        {'bit': 15, 'name': "QHL HP diff too large", 'doc': "WARN ", 'type': 'warning'},
        {'bit': 16, 'name': "spare", 'doc': "", 'type': 'warning'},
        {'bit': 17, 'name': "spare", 'doc': "", 'type': 'warning'},
        {'bit': 18, 'name': "spare", 'doc': "", 'type': 'warning'},
        {'bit': 19, 'name': "spare", 'doc': "", 'type': 'warning'},
        {'bit': 20, 'name': "QHS TH too high", 'doc': "bad pedestal?", 'type': 'warning'},
        {'bit': 21, 'name': "QHL TH too high", 'doc': "bad pedestal?", 'type': 'warning'},
        {'bit': 22, 'name': "Peakfinder called and used", 'doc': "peakfinder was called and used to determine position of second peak", 'type': 'warning'},
        {'bit': 23, 'name': "QHS TH too low", 'doc': "WARN, Possible noise peak fitted for threshold", 'type': 'warning'},
        {'bit': 24, 'name': "QHL TH too low", 'doc': "", 'type': 'warning'},
        {'bit': 25, 'name': "spare", 'doc': "", 'type': 'warning'},
        {'bit': 26, 'name': "spare", 'doc': "", 'type': 'warning'},
        {'bit': 27, 'name': "spare", 'doc': "", 'type': 'warning'},
        {'bit': 28, 'name': "spare", 'doc': "", 'type': 'warning'},
        {'bit': 29, 'name': "spare", 'doc': "", 'type': 'warning'},
        {'bit': 30, 'name': "spare", 'doc': "", 'type': 'warning'},
        {'bit': 31, 'name': "spare", 'doc': "", 'type': 'warning'}],
    'tw': [
        {'bit': 0, 'name': "status", 'doc': "OR of bits 1-31", 'type': 'info'},
        {'bit': 1, 'name': "channel offline", 'doc': "same as GF", 'type': 'info'},
        {'bit': 2, 'name': "zero occupancy", 'doc': "no hits on this PMT, same as GF", 'type': 'danger'},
        {'bit': 3, 'name': "low occupancy", 'doc': "Less than min hits on this PMT, could be different than GF", 'type': 'danger'},
        {'bit': 4, 'name': "spare", 'doc': "", 'type': 'info'},
        {'bit': 5, 'name': "spare", 'doc': "", 'type': 'info'},
        {'bit': 6, 'name': "spare", 'doc': "", 'type': 'info'},
        {'bit': 7, 'name': "RMS is very high", 'doc': "", 'type': 'warning'},
        {'bit': 8, 'name': "RMS is too high", 'doc': "", 'type': 'warning'},
        {'bit': 9, 'name': "high Q tail was not fitted", 'doc': "", 'type': 'warning'},
        {'bit': 10, 'name': "Tstep warning", 'doc': "Possible bad ADC charge conversion. This will affect a complete card.", 'type': 'warning'},
        {'bit': 11, 'name': "Flate warning", 'doc': "The fraction of late light is too large", 'type': 'warning'},
        {'bit': 12, 'name': "Fout warning", 'doc': "The fraction of hits <QHSmin and < Tpeak-10 is too large", 'type': 'warning'},
        {'bit': 13, 'name': "Gradient warning", 'doc': "The gradient of the fit to high charge tail is positive", 'type': 'warning'},
        {'bit': 14, 'name': "Gradient warning", 'doc': "The gradient of the fit to high charge tail is out of bounds", 'type': 'warning'},
        {'bit': 15, 'name': "spare", 'doc': "", 'type': 'info'},
        {'bit': 16, 'name': "spare", 'doc': "", 'type': 'info'},
        {'bit': 17, 'name': "spare", 'doc': "", 'type': 'info'},
        {'bit': 18, 'name': "spare", 'doc': "", 'type': 'info'},
        {'bit': 19, 'name': "spare", 'doc': "", 'type': 'info'},
        {'bit': 20, 'name': "spare", 'doc': "", 'type': 'info'},
        {'bit': 21, 'name': "interpolation bin #1 failed", 'doc': ">10hits? no interpolation point was extracted", 'type': 'warning'},
        {'bit': 22, 'name': "interpolation bin #2 failed", 'doc': ">10hits? no interpolation point was extracted", 'type': 'warning'},
        {'bit': 23, 'name': "interpolation bin #3 failed", 'doc': ">10hits? no interpolation point was extracted", 'type': 'warning'},
        {'bit': 24, 'name': "interpolation bin #4 failed", 'doc': ">10hits? no interpolation point was extracted", 'type': 'warning'},
        {'bit': 25, 'name': "interpolation bin #5 failed", 'doc': ">10hits? no interpolation point was extracted", 'type': 'warning'},
        {'bit': 26, 'name': "interpolation bin #6 failed", 'doc': ">10hits? no interpolation point was extracted", 'type': 'warning'},
        {'bit': 27, 'name': "interpolation bin #7 failed", 'doc': ">4hits?", 'type': 'warning'},
        {'bit': 28, 'name': "interpolation bin #8 failed", 'doc': ">4hits? ", 'type': 'warning'},
        {'bit': 29, 'name': "interpolation bin #9 failed", 'doc': ">4hits?", 'type': 'warning'},
        {'bit': 30, 'name': "interpolation bin #10 failed", 'doc': ">4hits?", 'type': 'warning'},
        {'bit': 31, 'name': "N Bins failed interpolation point calculation > Max", 'doc': "", 'type': 'warning'}],
}
