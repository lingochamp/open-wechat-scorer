# 流利说微信打分服务端 SDK

> For English, click [here](/README.md)

前端 SDK: [OnlineScorer-Wechat](https://github.com/lingochamp/OnlineScorer-Wechat)

流利说对外提供的在线打分接口，需使用 WebSocket 协议，微信公众号无法支持，本 SDK 旨在提供纯 HTTP 接口，并自动从微信方面获取公众号粉丝录制的语音消息，用于打分，以便微信公众号开发者接入（小程序开发者则可以直接使用 WebSocket 方式接入）。

此 HTTP 服务需要部署在公众号开发者的服务器上，原因有二：

- 获取语音所需公众号的 access_token 安全级别非常高，我们不能强制接入者把该 token 暴露给我们，所以必须在接入方服务器上完成下载音频的动作。（由于微信对 access_token 全局缓存的要求，公众号开发者一定已经拥有自己的服务器）
- 打分需要的流利说 appID 与 secret 也需要严格保密，不应写在前端脚本中，因此只能配置在服务端 SDK 内，先验证客户端身份，通过后方才用 secret 对 meta 进行签名并打分。（SDK 中目前没有包含这部分逻辑，客户端的 meta 会原封不动地传给 WebSocket 打分服务）

开发者可以通过继承 `server.OpenWeixinScorer` 来扩展所需功能，如对请求进行变换（上述第二条需要）或增加监控。

## 系统要求

Python **3.6+** on Windows/Linux/macOS

Ubuntu 14.04/16.04 用户可参考[这里](https://askubuntu.com/a/865569/557668)通过 PPA 安装 Python 3.6。

## 安装与运行

在本地运行时，建议创建一个虚拟环境（不要选错 Python 版本）：

``` bash
cd <PROJECT-ROOT>
python3.6 -m virtualenv env
source env/bin/activate
```

> 若是在 Docker 镜像中运行，则不必使用 Virtualenv

Python 3.6 环境准备好后，用 `pip` 安装依赖项（已经声明在 `requirements.txt` 中）：

``` bash
mkdir -p ~/.pip && cp tools/pip.conf ~/.pip/ # 如果你的网络访问官方 PyPI 太慢，可以执行这行命令来使用阿里云的镜像
pip install -r requirements.txt
```

运行测试：

``` bash
cp config.example config.yml
vim config.yml # 编辑配置
python3.6 test/test.py # 单元测试
./main.py config.yml & # 启动服务（压力测试需要先启动服务）
python3.6 test/stress.py # 直接运行此脚本，效果是执行一次请求并打印结果
molotov test/stress.py # 压力测试
```

## 已知问题

如果服务端快速返回错误（如认证失败）并关闭连接，本服务有可能产生 HTTP 500 而不能把服务端错误正确转发给请求方。
