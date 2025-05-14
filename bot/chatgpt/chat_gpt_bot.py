# encoding:utf-8

import time
import os
from openai import OpenAI, APIError, APITimeoutError, APIConnectionError, RateLimitError
from bot.bot import Bot
from bot.chatgpt.chat_gpt_session import ChatGPTSession
from bot.openai.open_ai_image import OpenAIImage
from bot.session_manager import SessionManager
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from common.token_bucket import TokenBucket
from config import conf

class ChatGPTBot(Bot, OpenAIImage):
    def __init__(self):
        super().__init__()
        
        # 新版 SDK 初始化 (强制从环境变量读取)
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),  # 直接从环境变量获取
            base_url=conf().get("open_ai_api_base"),
            timeout=conf().get("request_timeout", 30.0)
        )
        
        # 代理设置 (新版 SDK 格式)
        if conf().get("proxy"):
            self.client.proxy = {"http": conf().get("proxy"), "https": conf().get("proxy")}

        # 限流配置
        self.tb4chatgpt = None
        if conf().get("rate_limit_chatgpt"):
            self.tb4chatgpt = TokenBucket(conf().get("rate_limit_chatgpt", 20))

        # 模型配置
        conf_model = conf().get("model", "gpt-3.5-turbo")
        self.sessions = SessionManager(ChatGPTSession, model=conf_model)
        
        # 请求参数模板
        self.args = {
            "model": conf_model,
            "temperature": conf().get("temperature", 0.7),
            "top_p": conf().get("top_p", 1),
            "frequency_penalty": conf().get("frequency_penalty", 0.0),
            "presence_penalty": conf().get("presence_penalty", 0.0)
        }

        logger.debug(f"[CHATGPT] 初始化完成，API 密钥状态: {'已设置' if os.getenv('OPENAI_API_KEY') else '未设置'}")

    def reply_text(self, session: ChatGPTSession, api_key=None, args=None, retry_count=0) -> dict:
        """调用 OpenAI 的 Chat Completion API"""
        try:
            # 限流检查
            if self.tb4chatgpt and not self.tb4chatgpt.get_token():
                raise RateLimitError("Rate limit exceeded")

            # 合并请求参数
            request_args = self.args.copy()
            if args:
                request_args.update(args)
            request_args = {k: v for k, v in request_args.items() if v is not None}

            # API 调用
            response = self.client.chat.completions.create(
                messages=session.messages,
                **request_args
            )

            return {
                "total_tokens": response.usage.total_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "content": response.choices[0].message.content
            }

        except RateLimitError as e:
            logger.warning(f"[CHATGPT] 速率限制: {str(e)}")
            return self._handle_retry(e, session, retry_count, "请求过于频繁，请稍后再试")
            
        except APITimeoutError as e:
            logger.warning(f"[CHATGPT] 请求超时: {str(e)}")
            return self._handle_retry(e, session, retry_count, "请求超时，请重试", 5)

        except APIConnectionError as e:
            logger.warning(f"[CHATGPT] 连接错误: {str(e)}")
            return self._handle_retry(e, session, retry_count, "网络连接异常", 5)

        except APIError as e:
            logger.error(f"[CHATGPT] API 错误: {str(e)}")
            return {"content": f"API 错误: {e.message}", "completion_tokens": 0}

        except Exception as e:
            logger.exception(f"[CHATGPT] 未预期错误: {str(e)}")
            return {"content": "系统暂时不可用，请稍后再试", "completion_tokens": 0}

    def _handle_retry(self, error, session, retry_count, default_msg, sleep_time=5):
        """重试逻辑处理"""
        if retry_count < 2:
            logger.warning(f"[CHATGPT] 第 {retry_count+1} 次重试")
            time.sleep(sleep_time)
            return self.reply_text(session, retry_count=retry_count+1)
        else:
            self.sessions.clear_session(session.session_id)
            return {"content": default_msg, "completion_tokens": 0}

# Azure 专用版本
class AzureChatGPTBot(ChatGPTBot):
    def __init__(self):
        super().__init__()
        
        # 重写客户端配置
        self.client = OpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            base_url=conf().get("azure_api_base"),
            api_version=conf().get("azure_api_version", "2023-12-01-preview"),
            timeout=conf().get("request_timeout", 30.0)
        )
        
        # Azure 专用参数
        self.args["extra_body"] = {
            "deployment_id": conf().get("azure_deployment_id")
        }
