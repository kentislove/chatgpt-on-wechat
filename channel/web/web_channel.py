# channel/web/web_channel.py

from flask import Flask, request, jsonify, render_template
from bridge.context import Context, ContextType
from bridge.reply import Reply, ReplyType
from channel.chat_channel import ChatChannel
from channel.chat_message import ChatMessage
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
        user_msg = data.get("message", "")
        # 正確初始化 ChatMessage
        msg_obj = ChatMessage(msg=user_msg)
        # 動態添加插件所需的屬性
        msg_obj.from_user_nickname = "Web用戶"
        msg_obj.actual_user_nickname = "Web用戶"
        # 建立 Context
        context = Context(ContextType.TEXT, content=user_msg)
        context.kwargs["msg"] = msg_obj
        context.kwargs["session_id"] = "web_user_001"
        # 處理請求
        reply = self.produce(context)
        return jsonify({"reply": reply.content})

    def index_handler(self):
        return render_template('chat.html')

    def startup(self):
        logger.info(f"Starting web service on 0.0.0.0:{self.port}")
        self.app.run(host="0.0.0.0", port=self.port)

    def chatui_handler(self):
        return render_template('chatui.html')

def create_channel():
    return WebChannel()
