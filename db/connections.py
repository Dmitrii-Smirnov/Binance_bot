import typing as t
from redis.client import Redis
from binance_trade_bot.config import Config
from .key_schema import KeySchema


class RedisConnection:
    def __init__(self, host=None, port=None):
        self.config = Config()
        self.redis_client: t.Optional[Redis] = None
        if host is None or port is None:
            self.redis_client = Redis(host=self.config.REDIS_HOST, port=self.config.REDIS_PORT, decode_responses=True)
        else:
            self.redis_client = Redis(host=host, port=port)
        self.key_schema: t.Optional[KeySchema] = KeySchema()

    def close(self):
        """
        Close redis connection.
        """
        self.redis_client.close()
