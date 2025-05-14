# channel/web/web_channel.py

from flask import Flask, request, jsonify, render_template
from bridge.context import Context, ContextType
from bridge.reply import Reply, ReplyType
from channel.chat_channel import ChatChannel
from common.log import logger
import os

class WebChannel(ChatChannel):
    def __init__(self):
        super().__init__()
        # 用絕對路徑指定模板目錄
        template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
        self.app = Flask(__name__, template_folder=template_dir)
        self.port = int(os.environ.get("PORT", 10000))
        self.app.add_url_rule('/chat', 'chat', self.chat_handler, methods=['POST'])
        self.app.add_url_rule('/', 'index', self.index_handler)
        self.app.add_url_rule('/chatui', 'chatui', self.chatui_handler)

    def chat_handler(self):
        data = request.json
        context = Context(ContextType.TEXT, content=data.get("message", ""))
        reply = self.produce(context)
        return jsonify({"reply": reply.content})

    def index_handler(self):
        return render_template('chat.html')

    def startup(self):
        logger.info(f"Starting web service on 0.0.0.0:{self.port}")
        self.app.run(host="0.0.0.0", port=self.port)

    def chatui_handler(self):
        return render_template('chatui.html')
    def chat_handler(self):
        data = request.json
    # 加入 session_id 參數（範例用固定值，正式環境需用用戶ID或隨機生成）
        context = Context(
            type=ContextType.TEXT,
            content=data.get("message", ""),
        )
        context.kwargs["session_id"] = "web_user_001"
        reply = self.produce(context)
        return jsonify({"reply": reply.content})
def create_channel():
    return WebChannel()
