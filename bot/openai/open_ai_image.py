# bot/openai/open_ai_image.py

import os
import time
import requests
from openai import OpenAI, APIError, APITimeoutError, APIConnectionError, RateLimitError
from common.log import logger
from common.token_bucket import TokenBucket
from config import conf

class OpenAIImage:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=conf().get("open_ai_api_base"),
            timeout=conf().get("request_timeout", 30.0)
        )
        
        if conf().get("proxy"):
            self.client.proxy = conf().get("proxy")

        self.tb4image = TokenBucket(conf().get("rate_limit_dalle", 50)) if conf().get("rate_limit_dalle") else None

    def create_img(self, query, retry_count=0):
        try:
            if self.tb4image and not self.tb4image.get_token():
                raise RateLimitError("DALL-E API rate limit exceeded")

            response = self.client.images.generate(
                prompt=query,
                model=conf().get("text_to_image") or "dall-e-2",
                size=conf().get("image_create_size", "1024x1024"),
                quality="standard",
                n=1
            )
            
            image_url = response.data[0].url
            return self._download_image(image_url)

        except RateLimitError as e:
            logger.warning(f"[OPENAI] RateLimitError: {str(e)}")
            return self._handle_retry(e, query, retry_count, "图片生成速度太快啦，请稍后再试")
        
        except APITimeoutError as e:
            logger.warning(f"[OPENAI] Timeout: {str(e)}")
            return self._handle_retry(e, query, retry_count, "图片生成超时，请重试", 5)
        
        except APIError as e:
            logger.error(f"[OPENAI] APIError: {str(e)}")
            return f"API 错误: {e.message}"
        
        except Exception as e:
            logger.exception(f"[OPENAI] Unexpected error: {str(e)}")
            return "图片生成失败，请检查日志"

    def _download_image(self, url):
        # ... 保持原有下载逻辑不变 ...
        return "图片保存路径"

    def _handle_retry(self, error, query, retry_count, default_msg, sleep_time=5):
        if retry_count < 2:
            time.sleep(sleep_time)
            return self.create_img(query, retry_count + 1)
        else:
            return default_msg
