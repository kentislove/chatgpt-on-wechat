# encoding:utf-8
import os
import signal
import sys
import time
import threading
from importlib import import_module

# 修復模組導入問題
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import const
from config import load_config, conf
from plugins import PluginManager
import logging

logger = logging.getLogger(__name__)

def sigterm_handler_wrap(_signo):
    old_handler = signal.getsignal(_signo)

    def func(_signo, _stack_frame):
        logger.info(f"signal {_signo} received, exiting...")
        conf().save_user_datas()
        if callable(old_handler):
            return old_handler(_signo, _stack_frame)
        sys.exit(0)

    signal.signal(_signo, func)

def start_channel(channel_name: str):
    # 動態導入 channel 模組
    try:
        channel_module = import_module(f'channel.{channel_name}_channel')
        channel = channel_module.Channel()
    except Exception as e:
        logger.error(f"Channel {channel_name} init failed: {e}")
        return

    if channel_name in ["wx", "wxy", "terminal", "wechatmp", "web", 
                       "wechatmp_service", "wechatcom_app", "wework",
                       const.FEISHU, const.DINGTALK]:
        PluginManager().load_plugins()

    if conf().get("use_linkai"):
        try:
            from common import linkai_client
            threading.Thread(
                target=linkai_client.start, 
                args=(channel,),
                daemon=True
            ).start()
        except Exception as e:
            logger.error(f"LinkAI client failed: {e}")

    # Web 通道專用端口綁定
    if channel_name == "web":
        from flask import Flask, request, jsonify
        app = Flask(__name__)
        
        @app.route('/chat', methods=['POST'])
        def chat():
            data = request.json
            response = channel.handle(data)
            return jsonify(response)

        port = int(os.environ.get("PORT", 10000))
        threading.Thread(
            target=app.run,
            kwargs={'host': '0.0.0.0', 'port': port},
            daemon=True
        ).start()
    
    channel.startup()

def run():
    try:
        load_config()
        sigterm_handler_wrap(signal.SIGINT)
        sigterm_handler_wrap(signal.SIGTERM)

        channel_name = conf().get("channel_type", "wx")
        if "--cmd" in sys.argv:
            channel_name = "terminal"

        # 初始化日誌
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        start_channel(channel_name)

        while True:
            time.sleep(1)
    except Exception as e:
        logger.error("App startup failed!", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    run()
