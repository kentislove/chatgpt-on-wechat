# channel/web/web_channel.py
from flask import Flask, request, jsonify
import os
from bridge.context import Context, ContextType
from bridge.reply import Reply, ReplyType
from channel.chat_channel import ChatChannel
from common.log import logger

class WebChannel(ChatChannel):
    def __init__(self):
        super().__init__()
        self.app = Flask(__name__)
        self.port = int(os.environ.get("PORT", 10000))
        self.app.add_url_rule('/chat', 'chat', self.chat_handler, methods=['POST'])
        self.app.add_url_rule('/', 'index', self.index_handler)

    def chat_handler(self):
        data = request.json
        context = Context(ContextType.TEXT, content=data.get("message", ""))
        reply = self.produce(context)
        return jsonify({"reply": reply.content})

    def index_handler(self):
        return "Web Service Running"

    def startup(self):
        logger.info(f"Starting web service on 0.0.0.0:{self.port}")
        self.app.run(host="0.0.0.0", port=self.port)

def create_channel():
    return WebChannel()
