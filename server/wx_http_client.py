import asyncio

import aiohttp

READ_TIMEOUT = 10
WX_SPEEX_FRAME_SIZE = 60
WX_SPEEX_CONTENT_TYPE = 'voice/speex'

class WeixinResponseError(Exception):
    '''This exception is thrown when WeChat did not respond with 200 and
    voice/speex contents.
    '''

    def __init__(self, message, status=200, content_type=WX_SPEEX_CONTENT_TYPE):
        '''
        Only message is mandatory. See:
        https://stackoverflow.com/questions/16244923/how-to-make-a-custom-exception-class-with-multiple-init-args-pickleable
        '''

        super().__init__(message)
        self.status = status
        self.content_type = content_type

async def download_audio(session, url):
    '''Download audio from WeChat media server `url` and convert it to Liulishuo
    variant of speex format.
    At the time of writing, the "Fetching 'High-Definition' Voice Assets" API is
    listed on https://mp.weixin.qq.com/wiki?t=resource/res_main&id=mp1444738727
    (Appendix section), with no counterpart on open.wechat.com. You should use
    the base URL in that doc (https://api.weixin.qq.com/cgi-bin/media/get/jssdk)
    instead of the "standard" Fetching Temporary Asset URL, because Liulishuo
    OpenAPI does not support AMR format and only speex will be recognized.
    During my tests, the so-called "High-Definition' assets are encoded by speex
    VBR Quality 7 (60 bytes per 20ms frame). Liulishuo accepts any Quality from
    0 to 10, but requires a Length-Value encoding for each frame, so insertion
    of frame length field is done at the end of loop body.

    Arguments:
    session -- aiohttp.client.ClientSession object
    url     -- anything that session.get() accepts
    '''
    async with session.get(url, timeout=READ_TIMEOUT) as rsp:
        if rsp.status != 200 or rsp.content_type != WX_SPEEX_CONTENT_TYPE:
            body = await rsp.text()
            raise WeixinResponseError(body, rsp.status, rsp.content_type)
        while True:
            chunk = await rsp.content.read(WX_SPEEX_FRAME_SIZE)
            if not chunk:
                break
            # Add length field before the chunk (Liulishuo convention)
            yield len(chunk).to_bytes(4, 'little') + chunk
