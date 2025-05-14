from flask import Flask, request, jsonify
import os
from bridge.context import Context
from bridge.reply import Reply, ReplyType
from channel.chat_channel import ChatChannel
from common.log import logger

class WebChannel(ChatChannel):
    def __init__(self):
        super().__init__()
        self.app = Flask(__name__)
        self.port = int(os.environ.get("PORT", 10000))
        self.app.run(host="0.0.0.0", port=self.port)


    def chat_handler(self):
        data = request.json
        context = Context(ContextType.TEXT, content=data.get("message", ""))
        reply = self.produce(context)
        return jsonify({"reply": reply.content})

    def startup(self):
        self.app.run(host="0.0.0.0", port=self.port)

def create_channel():
    return WebChannel()
