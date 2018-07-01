import asyncio
import json

import aiohttp
import molotov

A_META = 'ewogICAgIml0ZW0iOiB7CiAgICAgICAgImF1ZGlvQ2hhbm5lbCI6IDEsCiAgICAgICAgImF1ZGlvRm9ybWF0IjogInNwZWV4IiwKICAgICAgICAiYXVkaW9TYW1wbGVyYXRlIjogMTYwMDAsCiAgICAgICAgInF1YWxpdHkiOiA3LAogICAgICAgICJyZWZ0ZXh0IjogImhlbGxvIGhlbGxvIGhlbGxvIGhlbGxvIiwKICAgICAgICAidHlwZSI6ICJyZWFkYWxvdWQiCiAgICB9Cn0K'

def provide_meta():
    return A_META

def provide_access_token():
    return 'TOKEN'

def provide_media_id():
    return 'DDD'

@molotov.scenario(weight=100)
async def _test(session):
    '''Main stress test.
    
    Usage: ``` bash
    molotov --sizing stress.py # Stress until it fails
    molotov -w 20 stress.py    # The configuration I used for local testing
    ```
    
    To get the best result, you must change scorer_url and audio_download_url
    in your config file away from the official WeChat/Liulishuo servers. Your
    mock WeChat server must respond with 200 and voice/speex content type,
    while your mock WebSocket Scoring service could be anything (even a closed
    port will do).

    My 4th-gen Intel Core @ 3.50GHz can handle ~50QPS with 7-second audio
    files. Not great, but 1) you can always scale it up, 2) after you begin to
    use the service seriously, the bottleneck will be inside the WS scoring
    service.

    Logging levels don't seem to have an impact on performance.
    '''

    LOCAL_SERVER_INSTANCE = 'http://localhost:55555/api/ratings'
    
    meta = {
        'mediaId':     provide_media_id(),
        'accessToken': provide_access_token(),
        'meta':        provide_meta(),
    }
    async with session.post(
        LOCAL_SERVER_INSTANCE,
        data=json.dumps(meta),
    ) as rsp:
        assert rsp.status == 200, rsp.status
        ret = await rsp.text()
        return ret

async def print_result():
    async with aiohttp.ClientSession() as ses:
        print(await _test(ses), end='')

if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(print_result())
