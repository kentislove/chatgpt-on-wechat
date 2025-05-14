import sys
import time
import json
from queue import Queue
import web
import os
from bridge.context import *
from bridge.reply import Reply, ReplyType
from channel.chat_channel import ChatChannel
from channel.chat_message import ChatMessage
from common.log import logger
from common.singleton import singleton
from config import conf

class WebMessage(ChatMessage):
    def __init__(
        self,
        msg_id,
        content,
        ctype=ContextType.TEXT,
        from_user_id="User",
        to_user_id="Chatgpt",
        other_user_id="Chatgpt",
    ):
        super().__init__(msg_id, content, ctype, from_user_id, to_user_id, other_user_id)
        self.msg_id = msg_id
        self.ctype = ctype
        self.content = content
        self.from_user_id = from_user_id
        self.to_user_id = to_user_id
        self.other_user_id = other_user_id

@singleton
class WebChannel(ChatChannel):
    NOT_SUPPORT_REPLYTYPE = [ReplyType.VOICE]
    
    def __init__(self):
        super().__init__()
        self.message_queues = {}
        self.msg_id_counter = 0
        self.port = int(os.environ.get("PORT", 9899))  # 優先讀取 Render 的 PORT
        self.host = "0.0.0.0"  # 強制綁定到 0.0.0.0

    def _generate_msg_id(self):
        self.msg_id_counter += 1
        return f"{int(time.time())}{self.msg_id_counter}"

    def send(self, reply: Reply, context: Context):
        try:
            user_id = context["receiver"]
            if user_id not in self.message_queues:
                self.message_queues[user_id] = Queue()
                
            message_data = {
                "type": str(reply.type),
                "content": reply.content,
                "timestamp": time.time()
            }
            self.message_queues[user_id].put(message_data)
            logger.info(f"Message sent to user {user_id}")  # 提升為 INFO 級別
            
        except Exception as e:
            logger.error(f"Send error: {e}", exc_info=True)

    def sse_handler(self, user_id):
        web.header('Content-Type', 'text/event-stream')
        web.header('Cache-Control', 'no-cache')
        web.header('Connection', 'keep-alive')
        
        if user_id not in self.message_queues:
            self.message_queues[user_id] = Queue()
        
        try:    
            while True:
                yield f": heartbeat\n\n"
                if not self.message_queues[user_id].empty():
                    message = self.message_queues[user_id].get_nowait()
                    yield f"data: {json.dumps(message)}\n\n"
                time.sleep(0.5)
        except GeneratorExit:
            logger.info(f"SSE connection closed for {user_id}")
        except Exception as e:
            logger.error(f"SSE error: {e}", exc_info=True)
        finally:
            if self.message_queues[user_id].empty():
                del self.message_queues[user_id]

    def post_message(self):
        try:
            data = web.data()
            json_data = json.loads(data)
            user_id = json_data.get('user_id', 'default_user')
            prompt = json_data.get('message', '')
            
            if not prompt:
                return json.dumps({"status": "error", "message": "Empty message"})
                
            msg_id = self._generate_msg_id()
            context = self._compose_context(
                ContextType.TEXT, 
                prompt, 
                msg=WebMessage(msg_id, prompt, from_user_id=user_id)
            )
            
            if context:
                context["isgroup"] = False
                self.produce(context)
                return json.dumps({"status": "success", "message": "Received"})
                
        except json.JSONDecodeError:
            return json.dumps({"status": "error", "message": "Invalid JSON"})
        except Exception as e:
            logger.error(f"Post error: {e}", exc_info=True)
            return json.dumps({"status": "error", "message": "Server error"})

    def chat_page(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(current_dir, 'templates', 'chat.html')
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"HTML file not found: {file_path}")
            return "Chat interface unavailable"

    def startup(self):
        urls = (
            '/sse/(.+)', 'SSEHandler',
            '/message', 'MessageHandler',
            '/chat', 'ChatHandler', 
        )
        app = web.application(urls, globals(), autoreload=False)
        logger.info(f"Starting web service on {self.host}:{self.port}")
        web.httpserver.runsimple(app.wsgifunc(), (self.host, self.port))

class SSEHandler:
    def GET(self, user_id):
        return WebChannel().sse_handler(user_id)

class MessageHandler:
    def POST(self):
        return WebChannel().post_message()

class ChatHandler:
    def GET(self):
        return WebChannel().chat_page()
