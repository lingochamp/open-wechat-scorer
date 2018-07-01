import asyncio
import json

import aiohttp


class GetAccessTokenError(Exception):
    def __init__(self, message, original_exception=None, wx_response=''):
        super().__init__(message)
        self.original_exception = original_exception
        self.wx_response = wx_response


async def get_access_token(session, config, req_dict):
    '''Sample implementation of getting access token.

    This routine expects your service to accept JSON-RPC 2.0 requests and be
    reachable on the HTTP URL that `config.wechatgo_jsonrpc_addr` specifies.

    JSON-RPC 2.0 Specification: http://www.jsonrpc.org/specification
    Request method is 'WeChat.AccessToken'
    Request params:
    - app_id: The AppID you will see on mp.weixin.qq.com
    Response fields:
    - access_token: The magic string that you need
    '''

    GET_TOKEN_METHOD = 'WeChat.AccessToken'
    JSONRPC_CNTTYPE  = 'application/json'

    TOKEN_SERVICE_JSONRPC_ADDR = 'http://localhost:8367/'
    GET_TOKEN_TIMEOUT_SEC = 1
    try:
        TOKEN_SERVICE_JSONRPC_ADDR = config.token_service_jsonrpc_addr
    except AttributeError:
        pass # Use default value if not found
    try:
        GET_TOKEN_TIMEOUT_SEC = float(config.get_token_timeout_sec)
    except AttributeError:
        pass

    payload = {
        'method':  GET_TOKEN_METHOD,
        'params':  {},
        'jsonrpc': '2.0',
        'id':      0,
    }
    headers = {
        'Content-Type': JSONRPC_CNTTYPE,
    }
    async with session.post(TOKEN_SERVICE_JSONRPC_ADDR,
        data=payload, headers=headers, timeout=GET_TOKEN_TIMEOUT_SEC) as res:
        body = await res.text()
        try:
            token_obj = json.loads(body)
            return token_obj['result']['access_token']
        except (json.decoder.JSONDecodeError, KeyError) as e:
            raise GetAccessTokenError(repr(e), e, body)
