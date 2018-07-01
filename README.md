# Liulishuo Online Scorer Backend SDK for WeChat

> [中文版链接/Chinese](/README-zh.md)

Our frontend SDK：[OnlineScorer-Wechat](https://github.com/lingochamp/OnlineScorer-Wechat)

The Liulishuo Online Scorer serves on a WebSocket URL, which is not accessible in the limited environment of WeChat official accounts. This SDK provides a pure HTTP portal and downloads user voice from WeChat media platform for scoring. That way, WeChat official account operators can adopt the scoring service easily. (Mini Program developers should use the WebSocket directly.)

This HTTP portal must be deployed on the official account operator's backend server for the following reasons:

- You need the WeChat access_token to fetch user-uploaded audio, which token is highly confidential (grants almost all privileges to the account) and we're aware should not be exposed to us (or any third party). So the download of audio must be done on your own server instead of Liulishuo's server. (An official account `developer` will need a backend anyway, to ensure universal caching of access_token.)
- If you use the basic auth scheme (appID and secret) in your scoring requests, you also have to keep the `secret` on server side and never code/config it in frontend scripts, so you should authenticate requests in your own account system, only after which you would sign the `meta` with `secret` and send request to Liulishuo. (That is not yet implemented in the SDK; `meta` will be forwarded as-is.)

You can subclass `server.OpenWeixinScorer` to extend its functionality, such as altering the meta and/or adding metrics. `main.py` is an demo of how you can config and run the service; edit it to instantiate `YourWeixinScorer` in place of `OpenWeixinScorer` and you're ready to go.

## System Requirements

Python **3.6+** on Windows/Linux/macOS

It's recommended for Ubuntu 14.04/16.04 users to [install Python 3.6 via PPA](https://askubuntu.com/a/865569/557668).

## Installation and Startup

You'd better create a `virtualenv` for development on your local machine (mind your Python version):

``` bash
cd <PROJECT-ROOT>
python3.6 -m virtualenv env
source env/bin/activate
```

> `Virtualenv` is not useful if you're building a Docker image

Install 3rdparty libs using `pip` (declared in `requirements.txt`):

``` bash
pip install -r requirements.txt
```

Running tests:

``` bash
cp config.example config.yml
vim config.yml # Edit config
python3.6 test/test.py # Unittest
./main.py config.yml & # Start service (for regression tests)
python3.6 test/stress.py # Run `stress.py` directly and you get server response for a single run
molotov test/stress.py # Stress test
```
