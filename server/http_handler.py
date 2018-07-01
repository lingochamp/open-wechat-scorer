import base64
import json
import logging
import traceback
import urllib.parse as urlparse

import aiohttp
import aiohttp.web
import asyncio

from . import auth_util, cfg, url_util, lls_ws_client, wx_http_client
from .user.lls import get_access_token

log = logging.getLogger()

class OpenWeixinScorer(object):
    '''OpenWeixinScorer is the main server object that you can use out-of-box.

    It uses aiohttp to achieve single-threaded concurrency and maintains the
    ClientSession on its own. To extend its functionality you should create a
    subclass and rewrite get_access_token, validate_request or rating_handler.
    '''

    RETURN_CONTENT_TYPE = 'application/json'
    REQUEST_ENDPOINT    = '/api/ratings'

    config = cfg.ScorerConfig()

    def __init__(self, new_config):
        self.config = new_config

    async def on_startup(self):
        self._session = aiohttp.ClientSession()
        log.debug('Created client session %s' % repr(self._session))

    def run(self):
        asyncio.get_event_loop().run_until_complete(self.on_startup())
        async def on_cleanup(app):
            await self._session.close()
        app = aiohttp.web.Application()
        app.on_cleanup.append(on_cleanup)
        app.router.add_post(self.REQUEST_ENDPOINT, self.rating_handler)
        aiohttp.web.run_app(app,
            host=self.config.listen_addr,
            port=self.config.listen_port,
        )

    async def get_access_token(self, req_dict):
        '''Get access token (from external service).

        You can implement your 'token service' with JSON-RPC on the HTTP level
        (details in ./user/lls.py) and left this function intact, or you can
        override this function in your OpenWeixinScorer subclass without call
        to __super__. Both solutions are good given that you don't keep your
        token in multiple services.

        Any exceptions raised in get_access_token will result in 500 for an
        /api/ratings request. Keep your token highly available.
        '''

        access_token = await get_access_token(self._session, self.config, req_dict)
        return access_token

    async def validate_request(self, req_dict, header_dict, query_dict):
        '''Validate request and optionally alter it.

        Put authentication or statistics here (in your overridden version).
        Raise an exception for an unauthorized request and the description will
        be put into a 400 response. Return the processed request if all's well.
        '''

        return req_dict

    async def rating_handler(self, request):
        '''The only HTTP handler, mounted on /api/ratings by default.

        If you should override this (to add metrics etc.), be sure to call
        original.
        You can change the path by editing the value of REQUEST_ENDPOINT.
        '''

        json_str = await request.text()
        try:
            req_dict = json.loads(json_str)
        except json.decoder.JSONDecodeError as jde:
            log.warning('Can\'t unmarshal request "%s": %s' % (json_str, jde))
            raise aiohttp.web.HTTPBadRequest(
                reason='JSON Decode Error',
            )
        try:
            media_id = req_dict['mediaId']
            meta = req_dict['meta']
        except KeyError as ke:
            log.warning('Request "%s" is missing field %s' % (json_str, ke))
            raise aiohttp.web.HTTPBadRequest(
                reason='Missing required field(s)',
            )

        try:
            req_dict = await self.validate_request(
                req_dict,
                request.headers,
                request.query,
            )
        except Exception as e:
            raise aiohttp.web.HTTPBadRequest(
                body=str(e),
            )

        access_token = ''
        try:
            # If accessToken is specified, use it
            access_token = req_dict['accessToken']
        except KeyError:
            pass
        if len(access_token) == 0:
            try:
                access_token = await self.get_access_token(req_dict)
            except Exception as e:
                log.warning('Unable to get access token')
                traceback.print_tb(e.__traceback__)
                raise aiohttp.web.HTTPInternalServerError(
                    body=repr(e),
                )

        # Sign request if credentials are set in config.
        # TODO: catch exceptions and return 400 (will be 500 if not done)
        meta_signed = auth_util.get_signed_request(self.config, base64.b64decode(meta).decode())
        log.debug(meta_signed)
        meta = base64.b64encode(meta_signed.encode()).decode()

        audio_link = self.calculateURL(media_id, access_token)
        try:
            # Receive from WeChat, convert to LLS format, and send to scoring
            # service - all done in parallel.
            rsp = await lls_ws_client.get_score(
                self._session,
                lls_ws_client.provide_scorer_url(self.config, meta),
                meta,
                wx_http_client.download_audio(self._session, audio_link),
            )
            return aiohttp.web.Response(
                body=rsp,
                content_type=self.RETURN_CONTENT_TYPE,
            )
        except wx_http_client.WeixinResponseError as wre:
            log.warning(wre)
            rsp = json.dumps({
                'status': -100,
                'msg':    str(wre),
                'flag':   1,
            })
            return aiohttp.web.Response(
                body=rsp,
                content_type=self.RETURN_CONTENT_TYPE,
            )

    def calculateURL(self, media_id, access_token):
        '''Return link to the wanted audio from the above arguments.

        The domain & path part of URL is declared in `self.config`.
        '''

        query = {'access_token': access_token, 'media_id': media_id}
        return url_util.add_url_params(self.config.audio_download_url, query)
