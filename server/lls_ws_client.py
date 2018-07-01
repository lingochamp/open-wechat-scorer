import asyncio
import base64
import binascii
import json
import logging
import sys

import aiohttp
from . import auth_util

# The maximum duration of one WeChat voice message is 60 seconds. Under
# moderate load, Liulishuo needs ~30s to finish marking a 60s audio.
SCORING_TIMEOUT_SEC = 30
# Size of the length field in streaming reqs/rsps
INTEGER_SIZE = 4
# Add this HTTP header to get the server informed of the requestor being WeChat.
# This has effect on certain behaviors, such as disabling queuing (HTTP requests
# will inevitably time out after queued for ~10 seconds).
HEADER_FOR_STATS = 'X-from-WeChat'

log = logging.getLogger()

class LiulishuoResponseError(Exception):
    pass

async def get_score(session, endpoint, meta, audio_iter):
    async with session.ws_connect(
        endpoint,
        timeout=SCORING_TIMEOUT_SEC,
        receive_timeout=SCORING_TIMEOUT_SEC,
        headers={HEADER_FOR_STATS: '1'},
    ) as ws:
        meta_bin = meta.encode()
        meta_len = len(meta_bin).to_bytes(INTEGER_SIZE, 'big')
        await ws.send_bytes(meta_len+meta_bin)
        async for chunk in audio_iter:
            await ws.send_bytes(chunk)
        await ws.send_bytes(b'EOS') # End-of-Stream marker
        ret = b''
        ret_size = None
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.BINARY:
                ret += msg.data
            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                break
            # Get response size from the 4-byte header
            if ret_size == None and len(ret) >= INTEGER_SIZE:
                ret_size = int.from_bytes(ret[0:INTEGER_SIZE], byteorder='big', signed=False)
            # If the 'first' response has been wholly received, stop and ignore the rest
            if ret_size != None and len(ret) >= INTEGER_SIZE+ret_size:
                break
        if ret_size != None and ret_size > 0:
            # NOTE: this does not handle the case where ret_size is greater than
            # the bytes actually received
            return ret[INTEGER_SIZE:INTEGER_SIZE+ret_size]
        raise LiulishuoResponseError('Response too short: '+repr(ret))

def get_type_from_meta(meta):
    '''
    Get `type` from meta (scoring request).

    Arguments:
    meta -- a str (JSON expected)
    '''

    meta_json = auth_util.remove_trail_from_meta(meta)
    try:
        meta_dict = json.loads(meta_json)
    except json.decoder.JSONDecodeError as jde:
        log.warning(jde)
        return ''
    try:
        question_type = meta_dict['type']
        return question_type
    except KeyError as ke:
        log.warning(repr(ke))
    try:
        question_type = meta_dict['item']['type']
        return question_type
    except KeyError as ke:
        log.warning(repr(ke))
    return ''

def provide_scorer_url(config, meta):
    '''
    This is a service selector: it tries extracting the `type` field from meta
    and returns the corresponding URL in config.
    It fallbacks to default if there's no `type` in meta or no `type_specific_
    scorer_urls` in config.

    Arguments:
    config -- server.cfg.ScorerConfig object
    meta   -- a str (Base64-encoded JSON expected)
    '''

    ret = config.scorer_url
    try:
        meta = base64.b64decode(meta).decode()
    except (binascii.Error, ValueError) as e:
        log.warning(e)
        return ret
    type_str = get_type_from_meta(meta)
    try:
        return config.type_specific_scorer_urls[type_str]
    except (AttributeError, KeyError) as e:
        log.warning(e)
    return ret
