import logging

log = logging.getLogger()
_loghdl = logging.StreamHandler()
_loghdl.setFormatter(logging.Formatter('%(asctime)s | %(levelname)-8s | %(lineno)04d | %(filename)s: %(message)s'))
log.addHandler(_loghdl)
log.setLevel(logging.DEBUG)
