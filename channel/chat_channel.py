import os
import time
from concurrent.futures import ThreadPoolExecutor
from bridge.context import Context, ContextType
from bridge.reply import Reply, ReplyType
from common import memory
from common.log import logger
from config import conf
from plugins import PluginManager
from channel.channel import Channel
from bridge.bridge import Bridge
from common import utils
from common.tmp_dir import TmpDir
from common.audio_convert import any_to_wav

class ChatChannel(Channel):
    def __init__(self):
        super().__init__()
        self.pool = ThreadPoolExecutor(max_workers=8)
        self.users = {}
        self.plugin_manager = PluginManager()

    def startup(self):
        logger.info("Chat channel started")

    def _handle(self, context: Context):
        session_id = context["session_id"]
        if session_id not in self.users:
            self.users[session_id] = {
                "last_active_time": time.time(),
                "session": self._create_session()
            }
        try:
            reply = self._generate_reply(context)
            self.send(reply, context)
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}", exc_info=True)
            reply = Reply(ReplyType.TEXT, f"處理訊息時發生錯誤: {str(e)}")
            self.send(reply, context)

    def _generate_reply(self, context: Context, reply: Reply = Reply()) -> Reply:
        try:
            e_context = self.plugin_manager.emit_event(
                EventContext(
                    Event.ON_HANDLE_CONTEXT,
                    {"channel": self, "context": context, "reply": reply}
                )
            )
            reply = e_context["reply"]

            if not e_context.is_pass():
                logger.debug(f"Handling context: type={context.type}, content={context.content}")

                if context.type in [ContextType.TEXT, ContextType.IMAGE_CREATE]:
                    reply = self._handle_text(context)
                elif context.type == ContextType.VOICE:
                    reply = self._handle_voice(context)
                elif context.type == ContextType.IMAGE:
                    self._handle_image(context)
                elif context.type == ContextType.FILE:
                    self._handle_file(context)
                else:
                    logger.warning(f"Unhandled context type: {context.type}")
                    reply = Reply(ReplyType.TEXT, "暫不支援此類訊息")

            # 保證回覆有效性
            if not reply or not isinstance(reply, Reply):
                logger.error("Invalid reply object generated")
                reply = Reply(ReplyType.TEXT, "系統回覆生成失敗")

            return reply

        except Exception as e:
            logger.error("Unhandled exception in _generate_reply", exc_info=True)
            return Reply(ReplyType.TEXT, f"系統處理異常: {str(e)}")

    def _handle_text(self, context: Context) -> Reply:
        try:
            bridge = Bridge()
            reply = bridge.fetch_reply_content(context.content, context)
            return reply if reply else Reply(ReplyType.TEXT, "未取得有效回覆")
        except Exception as e:
            logger.error("Text handling error", exc_info=True)
            return Reply(ReplyType.TEXT, f"文字處理失敗: {str(e)}")

    def _handle_voice(self, context: Context) -> Reply:
        try:
            file_path = context.content
            wav_path = os.path.splitext(file_path)[0] + ".wav"
            any_to_wav(file_path, wav_path)
            reply = Bridge().fetch_voice_to_text(wav_path)
            utils.clean_tmp_file(file_path)
            if wav_path != file_path:
                utils.clean_tmp_file(wav_path)
            return reply
        except Exception as e:
            logger.error("Voice handling error", exc_info=True)
            return Reply(ReplyType.TEXT, f"語音處理失敗: {str(e)}")

    def _handle_image(self, context: Context):
        memory.USER_IMAGE_CACHE[context["session_id"]] = {
            "path": context.content,
            "msg": context.get("msg")
        }

    def _handle_file(self, context: Context):
        # 文件處理邏輯 (需自行實現)
        pass

    def produce(self, context: Context) -> Reply:
        try:
            # 直接同步呼叫 _generate_reply，避免 async 問題
            reply = self._generate_reply(context)
            return reply if reply else Reply(ReplyType.TEXT, "請求超時")
        except Exception as e:
            logger.error("Error in produce", exc_info=True)
            return Reply(ReplyType.TEXT, f"請求處理失敗: {str(e)}")

    def send(self, reply: Reply, context: Context):
        if not reply:
            logger.warning("Attempting to send empty reply")
            reply = Reply(ReplyType.TEXT, "空回覆")
        if reply.type == ReplyType.TEXT:
            logger.info(f"[CHAT] Reply content: {reply.content}")
        # 其他類型回覆處理邏輯...

    def _create_session(self):
        # 會話管理邏輯 (需自行實現)
        return {"create_time": time.time(), "last_active_time": time.time()}

# 事件類型定義
class Event:
    ON_HANDLE_CONTEXT = "on_handle_context"

class EventAction:
    BREAK = "break"
    CONTINUE = "continue"
    BREAK_PASS = "break_pass"

class EventContext(dict):
    def __init__(self, event: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event
        self._is_pass = False
        self._action = EventAction.CONTINUE

    def is_pass(self):
        return self._is_pass

    def set_pass(self, is_pass: bool):
        self._is_pass = is_pass

    @property
    def action(self):
        return self._action

    @action.setter
    def action(self, value):
        self._action = value
