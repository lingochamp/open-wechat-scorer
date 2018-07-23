import hashlib
import json
import logging
import random
import time

log = logging.getLogger()
rand = random.Random()
rand.seed()

def remove_trail_from_meta(meta):
    return meta[:meta.rfind('}')+1]

def generate_salt():
    rand_uint32 = rand.randint(0, 2**32 - 1)
    now = time.time()
    return '{0:d}:{1:08x}'.format(int(now), rand_uint32)

def get_signed_request(config, meta, salt=None):
    '''Sign request if app_id and secret exist in config.

    If the given meta is already signed, the original authentication info is
      replaced.
    If credentials are not set, the function returns meta untouched.

    Arguments:
    config -- object
    meta   -- str (JSON expected)
    salt   -- the random string used in hashing (in most cases you don't need
              to set this argument)
    '''

    meta_json = remove_trail_from_meta(meta)
    try:
        meta_dict = json.loads(meta_json)
    except json.decoder.JSONDecodeError as jde:
        log.warning(jde)
        return ''
    if 'item' in meta_dict and type(meta_dict['item']) == dict:
        # Force speex quality 7 to match WeChat audio's encode setting
        meta_dict['item']['quality'] = 7

    app_id = ''
    secret = ''
    try:
        app_id = config.app_id
        secret = config.secret
    except AttributeError as ae:
        log.warning(ae)
    if app_id == None or secret == None or len(app_id) == 0 or len(secret) == 0:
        # AppID or secret not set - signing disabled
        return json.dumps(meta_dict)

    if salt == None or len(salt) == 0:
        salt = generate_salt()
    meta_dict['appID'] = app_id
    meta_dict['salt'] = salt
    new_meta = json.dumps(meta_dict)
    str_to_hash = '+'.join((app_id, new_meta, meta_dict['salt'], secret))
    hash_obj = hashlib.new('md5', str_to_hash.encode())
    hash_str = hash_obj.hexdigest()
    return new_meta + ';hash=' + hash_str
