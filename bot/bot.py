"""
Auto-replay chat robot abstract class
"""

from bridge.context import Context
from bridge.reply import Reply

class Bot(object):
    def reply(self, query, context: Context = None) -> Reply:
        """
        bot auto-reply content
        :param query: received message
        :param context: extra context info
        :return: reply content (Reply object)
        """
        raise NotImplementedError("子類別必須實作 reply 方法")
