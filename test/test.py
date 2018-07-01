import asyncio
import concurrent.futures
import logging
import os
import sys
import unittest

import yaml

from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from server import auth_util, cfg, http_handler, lls_ws_client
from server.user import lls

import log_opts
log = logging.getLogger()

async def mock_download_audio(chunk_size=60, chunk_count=40, chunk_delay_ms=5):
    '''Mock version of wx_http_client.download_audio().

    Arguments:
    chunk_size     -- bytes in each chunk (not including the length header)
    chunk_count    -- count of chunks to yield before returning
    chunk_delay_ms -- time that the mock should asyncly sleep after yielding each chunk, to simulate network latency
    '''

    for _ in range(chunk_count):
        await asyncio.sleep(chunk_delay_ms/1000.0)
        yield chunk_size.to_bytes(4, 'little') + os.urandom(chunk_size)

async def mock_ws_handler_normal(request):
    RSP_BYTES = '{}'.encode()
    WRONG_BYTES = 'wrong'.encode()
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    try:
        async for msg in ws:
            meta = msg.data
            break # Read one message only
        if meta == b'\x00\x00\x00\x02{}':
            await asyncio.sleep(0.2)
            await ws.send_bytes(len(RSP_BYTES).to_bytes(4, sys.byteorder) + RSP_BYTES)
        else:
            await ws.send_bytes(len(WRONG_BYTES).to_bytes(4, sys.byteorder) + WRONG_BYTES)
    finally:
        await ws.close()
    return ws

async def mock_ws_handler_empty_rsp(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    try:
        await ws.send_bytes((0).to_bytes(4, sys.byteorder))
    finally:
        await ws.close()
    return ws

async def mock_ws_handler_stuck_forever(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    try:
        async for msg in ws:
            log.debug('mock_ws_handler_stuck_forever received %d bytes' % len(msg.data))
    finally:
        await ws.close()
    return ws

class TestCfg(unittest.TestCase):
    '''Test for server.cfg.ScorerConfig class.
    '''
    
    def test_init(self):
        '''Test for default values and loading from mappings.
        '''
        test_dict = {
            'some_test_key': 'booo',
            'listen_addr':   '127.0.0.1',
        }
        obj = cfg.ScorerConfig(**test_dict)
        self.assertEqual(obj.some_test_key, 'booo')    # Added key
        self.assertEqual(obj.listen_addr, '127.0.0.1') # Modified value
        self.assertEqual(int(obj.listen_port), 54449)  # The default value
        with self.assertRaises(AttributeError):
            print(obj.another_test_key) # Nonexistent key

class TestLLSClientUtils(unittest.TestCase):
    '''Test for the utility function in server.lls_ws_client.
    '''

    TEST_META_WELL_FORMED = 'eyJpdGVtIjp7InR5cGUiOiJhYmMifX0K'
    TEST_META_ACCEPTABLE  = 'eyJ0eXBlIjoiYWJjIn0K'
    TEST_META_MALFORMED   = 'YmF6aW5nYQo='

    def test_provide_scorer_url(self):
        '''Test for getting question type from request and choosing from
        configured scorer URLs according to the type.
        '''
        cfg1 = cfg.ScorerConfig()
        res1 = lls_ws_client.provide_scorer_url(cfg1, self.TEST_META_ACCEPTABLE)
        self.assertEqual(res1, cfg1.scorer_url)
        cfg1.type_specific_scorer_urls = {
            'abc': 'test double',
        }
        res1 = lls_ws_client.provide_scorer_url(cfg1, self.TEST_META_MALFORMED)
        self.assertEqual(res1, cfg1.scorer_url)
        res2 = lls_ws_client.provide_scorer_url(cfg1, self.TEST_META_WELL_FORMED)
        self.assertEqual(res2, 'test double')
        res2 = lls_ws_client.provide_scorer_url(cfg1, self.TEST_META_ACCEPTABLE)
        self.assertEqual(res2, 'test double')

class TestLLSClientScoring(AioHTTPTestCase):
    '''Test for getting score via WebSocket connections.
    '''

    MOCK_NORMAL    = '/ws-endpoint'
    MOCK_EMPTY_RSP = '/ws-endpoint-empty'
    MOCK_TIMEOUT   = '/ws-endpoint-hog'

    async def get_application(self):
        '''Set up three mock WS servers with distinct behaviors.
        '''
        app = web.Application()
        app.add_routes([
            web.get(self.MOCK_NORMAL, mock_ws_handler_normal),
            web.get(self.MOCK_EMPTY_RSP, mock_ws_handler_empty_rsp),
            web.get(self.MOCK_TIMEOUT, mock_ws_handler_stuck_forever),
        ])
        return app

    @unittest_run_loop
    async def test_get_score_normal(self):
        rsp = await lls_ws_client.get_score(self.client, self.MOCK_NORMAL, '{}', mock_download_audio())
        self.assertEqual(rsp.decode(), '{}')
    
    @unittest_run_loop
    async def test_get_score_empty(self):
        with self.assertRaises(lls_ws_client.LiulishuoResponseError):
            await lls_ws_client.get_score(self.client, self.MOCK_EMPTY_RSP, '{}', mock_download_audio())

    @unittest_run_loop
    async def test_get_score_timeout(self):
        lls_ws_client.SCORING_TIMEOUT_SEC = 1
        with self.assertRaises(concurrent.futures._base.TimeoutError):
            await lls_ws_client.get_score(self.client, self.MOCK_TIMEOUT, '{}', mock_download_audio())

class TestLLSTokenService(AioHTTPTestCase):
    '''Test for the server.user.lls module.
    '''

    NORMAL_RESPONSE = b'{"jsonrpc":"2.0","result":{"access_token":"8_nKdOGFSoJvqAPN4u4mv7aukG2uhA3XXUIPSKXUro3NRP4UomM7FXGNblQIGfTrwJ8RB9p5u6DXT5J6e_x1JDUN6fdj8PnChdoWlNM8DYQ-lxod9jnWf1BknX_24xrGwRR8v5jOV07aykqFLRABFaAFARSW","expires":1523882233},"id":"52fdfc072182654f"}'
    ERROR_RESPONSE  = b'{"jsonrpc":"2.0","error":{"code":-32000,"message":"app_id xxx not found in config","data":null},"id":"52fdfc072182654f"}'
    RESPONSE_TYPE   = 'application/json'
    PATH_NORMAL              = '/normal'
    PATH_ABNORMAL            = '/abnormal'

    async def get_application(self):
        async def normal(request):
            return web.Response(
                body=self.NORMAL_RESPONSE,
                content_type=self.RESPONSE_TYPE,
            )
        async def abnormal(request):
            return web.Response(
                body=self.ERROR_RESPONSE,
                content_type=self.RESPONSE_TYPE,
            )
        app = web.Application()
        app.add_routes([
            web.post(self.PATH_NORMAL, normal),
            web.post(self.PATH_ABNORMAL, abnormal),
        ])
        return app

    @unittest_run_loop
    async def test_get_access_token(self):
        class MockScorerConfig(object):
            pass

        cfg1 = MockScorerConfig()
        cfg1.token_service_jsonrpc_addr = self.PATH_NORMAL
        ret1 = await lls.get_access_token(
            self.client, cfg1, {},
        )
        self.assertEqual(ret1, '8_nKdOGFSoJvqAPN4u4mv7aukG2uhA3XXUIPSKXUro3NRP4UomM7FXGNblQIGfTrwJ8RB9p5u6DXT5J6e_x1JDUN6fdj8PnChdoWlNM8DYQ-lxod9jnWf1BknX_24xrGwRR8v5jOV07aykqFLRABFaAFARSW')

        cfg2 = MockScorerConfig()
        cfg2.token_service_jsonrpc_addr = self.PATH_ABNORMAL
        with self.assertRaises(lls.GetAccessTokenError):
            _ = await lls.get_access_token(
                self.client, cfg2, {},
            )

class TestHTTPHandler(unittest.TestCase):
    '''Test for the server.http_handler module.

    This test suite is supplementary; http_handler is the core routine of this
    program and should be covered in regression/stress tests.
    '''

    def setUp(self):
        self.__handler = http_handler.OpenWeixinScorer(cfg.ScorerConfig())

    def test_calculate_url(self):
        self.assertEqual(
            self.__handler.calculateURL('DDD', 'TOKEN'),
            'https://api.weixin.qq.com/cgi-bin/media/get/jssdk?access_token=TOKEN&media_id=DDD'
        )

class TestAuthUtil(unittest.TestCase):
    '''Test for the server.auth_util module.
    '''

    meta = '''{
  "item": {
    "type": "readaloud",
    "quality": -1,
    "audioFormat": "wav",
    "audioChannel": 1,
    "audioSamplerate": 16000,
    "reftext": "Accepted connections are configured to enable TCP keep-alives."
  }
}'''

    def setUp(self):
        config_dict = yaml.safe_load('''
        app_id: 
        secret: 
        ''')
        self.__zero_config = cfg.ScorerConfig(**config_dict)
        config_dict = yaml.safe_load('''
        app_id: SDKdemo
        secret: abc
        ''')
        self.__config = cfg.ScorerConfig(**config_dict)

    def test_get_signed_request(self):
        log.debug('test_get_signed_request: %s', auth_util.get_signed_request(
            self.__config,
            self.meta,
            '123',
        ))
        log.debug('test_get_signed_request: %s', auth_util.get_signed_request(
            self.__zero_config,
            self.meta,
            '123',
        ))
        # Unless you implement the hashing again, you can only check for
        # exceptions and observe the output with bare eyes, without making
        # any assertions.

if __name__ == '__main__':
    unittest.main()
