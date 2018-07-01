import asyncio

class ScorerConfig(object):
    '''
    ScorerConfig is loaded from YAML on server startup.
    It provides default values for the most common options.
    '''

    # LLS credentials - will be used to sign requests before sending to scoring
    # service. If app_id or secret is empty, requests will not be signed server-
    # side.
    app_id = ''
    secret = ''

    # Transport settings (merely listen address now, but timeouts or conn pool
    # size or so on may be added in the future):
    listen_addr = '0.0.0.0'
    listen_port = '54449'

    # The following link is documented here (in Appendix):
    # https://mp.weixin.qq.com/wiki?t=resource/res_main&id=mp1444738727
    audio_download_url = 'https://api.weixin.qq.com/cgi-bin/media/get/jssdk'

    # Contact LLS to get correct value for this:
    scorer_url = 'https://liulishuo-scorer-url'

    def __init__(self, **entries):
        self.__dict__.update(entries)
