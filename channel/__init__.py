# channel/__init__.py
from .web.web_channel import WebChannel

CHANNEL_REGISTRY = {
    "web": WebChannel,
    # 其他通道...
}
