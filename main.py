#!/usr/bin/env python3

import argparse
import logging
import os
import platform
import socket
import sys

import yaml

import server.cfg
import server.http_handler as http

import log_opts
log = logging.getLogger()

PROJECT = 'lls-open-wechat-scorer'
VERSION = 'v0.1.0'

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Backend of Liulishuo OpenAPI for WeChat clients')
    parser.add_argument('config', metavar='CONFIG-FILE', type=str, nargs=1,
        help='config (YAML) file path')
    args = parser.parse_args()
    config_file = args.config[0]

    log.info('Starting %s %s on %s (Python %s)...' % (
        PROJECT, VERSION, socket.gethostname(), platform.python_version()))
    log.info('Using config file: %s' % config_file)
    config_obj = server.cfg.ScorerConfig()
    with open(config_file) as f:
        data_map = yaml.safe_load(f)
        if data_map != None:
            config_obj = server.cfg.ScorerConfig(**data_map)

    # Set log level to the value of 'log_level' in the config.
    # For interpretation of 'log_level', see
    # https://docs.python.org/3/library/logging.html#logging-levels.
    # If 'log_level' is not set, no log will be printed.
    try:
        log.setLevel(config_obj.log_level)
    except AttributeError as ae:
        pass

    svr = http.OpenWeixinScorer(config_obj)
    svr.run()
