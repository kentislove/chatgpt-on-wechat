# encoding:utf-8

import time
from openai import OpenAI, APIError, APITimeoutError, APIConnectionError, RateLimitError
from bot.bot import Bot
from bot.chatgpt.chat_gpt_session import ChatGPTSession
from bot.openai.open_ai_image import OpenAIImage
from bot.session_manager import SessionManager
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from common.token_bucket import TokenBucket
from config import conf, load_config
import os

class ChatGPTBot(Bot, OpenAIImage):
    def __init__(self):
        super().__init__()
        
        # 新版 SDK 初始化方式
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY") or conf().get("open_ai_api_key"),
            base_url=conf().get("open_ai_api_base"),
            timeout=conf().get("request_timeout", 30.0)
        )
        
        if conf().get("proxy"):
            self.client.proxy = conf().get("proxy")

        # 限流配置
        if conf().get("rate_limit_chatgpt"):
            self.tb4chatgpt = TokenBucket(conf().get("rate_limit_chatgpt", 20))

        conf_model = conf().get("model") or "gpt-3.5-turbo"
        self.sessions = SessionManager(ChatGPTSession, model=conf_model)
        
        # 初始化参数
        self.args = {
            "model": conf_model,
            "temperature": conf().get("temperature", 0.9),
            "top_p": conf().get("top_p", 1),
            "frequency_penalty": conf().get("frequency_penalty", 0.0),
            "presence_penalty": conf().get("presence_penalty", 0.0),
            "timeout": conf().get("request_timeout", 30.0)
        }

        logger.debug(f"[CHATGPT] 初始化完成，API Key: {os.getenv('OPENAI_API_KEY')}")

    def reply_text(self, session: ChatGPTSession, api_key=None, args=None, retry_count=0) -> dict:
        """调用 OpenAI 的 ChatCompletion 接口获取回复"""
        try:
            if conf().get("rate_limit_chatgpt") and not self.tb4chatgpt.get_token():
                raise RateLimitError("Rate limit exceeded")

            # 使用新版 SDK 的调用方式
            response = self.client.chat.completions.create(
                messages=session.messages,
                **self._get_request_args(args)
            )

            return {
                "total_tokens": response.usage.total_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "content": response.choices[0].message.content
            }

        except RateLimitError as e:
            logger.warn(f"[CHATGPT] RateLimitError: {e}")
            return self._handle_retry(e, session, retry_count, "提问太快啦，请休息一下再问我吧")
            
        except APITimeoutError as e:
            logger.warn(f"[CHATGPT] Timeout: {e}")
            return self._handle_retry(e, session, retry_count, "我没有收到你的消息", 5)

        except APIConnectionError as e:
            logger.warn(f"[CHATGPT] ConnectionError: {e}")
            return self._handle_retry(e, session, retry_count, "我连接不到你的网络", 5)

        except APIError as e:
            logger.error(f"[CHATGPT] APIError: {e}")
            return {"content": f"API 错误: {e.message}", "completion_tokens": 0}

        except Exception as e:
            logger.exception(f"[CHATGPT] Unexpected error: {e}")
            return {"content": "系统暂时不可用，请稍后再试", "completion_tokens": 0}

    def _get_request_args(self, args=None):
        """获取请求参数"""
        request_args = self.args.copy()
        if args:
            request_args.update(args)
        
        # 移除空值参数
        return {k: v for k, v in request_args.items() if v is not None}

    def _handle_retry(self, error, session, retry_count, default_msg, sleep_time=5):
        """处理重试逻辑"""
        if retry_count < 2:
            logger.warn(f"[CHATGPT] 第{retry_count+1}次重试")
            time.sleep(sleep_time)
            return self.reply_text(session, retry_count=retry_count+1)
        else:
            self.sessions.clear_session(session.session_id)
            return {"content": default_msg, "completion_tokens": 0}

# Azure 专用版本（如果需要）
class AzureChatGPTBot(ChatGPTBot):
    def __init__(self):
        super().__init__()
        self.client = OpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            base_url=conf().get("azure_api_base"),
            api_version=conf().get("azure_api_version", "2023-12-01-preview"),
            timeout=conf().get("request_timeout", 30.0)
        )
        
        self.args["extra_body"] = {
            "deployment_id": conf().get("azure_deployment_id")
        }
