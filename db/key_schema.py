from binance_trade_bot.config import Config


def prefixed_key(f):
    """
    A method decorator that prefixes return values.

    Prefixes any string that the decorated method `f` returns with the value of
    the `prefix` attribute on the owner object `self`.
    """
    def prefixed_method(self, *args, **kwargs):
        key = f(self, *args, **kwargs)
        return f"{self.prefix}:{key}"

    return prefixed_method


class KeySchema:
    """
    Methods to generate key names for Redis data structures.

    This class therefore contains a reference to all possible key names used by this application.
    """
    def __init__(self, config: Config = Config()):
        self.config = config
        self.prefix = config.DEFAULT_KEY_PREFIX

    @prefixed_key
    def time_hash(self) -> str:
        """
        hash:time
        Redis type: hash
        """
        return 'hash:time'

    @prefixed_key
    def kline_hash(self, kline_symbol: str, kline_key: int) -> str:
        """
        kline:{kline_symbol}:hash:{kline_key}
        """
        return f'kline:{kline_symbol}:hash:{kline_key}'

    @prefixed_key
    def kline_key(self, kline_symbol: str) -> str:
        """
        line:{kline_symbol}:list
        Redis typeL list
        """
        return f'kline:{kline_symbol}:list'

    @prefixed_key
    def kline_set(self, kline_symbol: str):
        """
        kline:{kline_symbol}:set
        Redis typeL sorted set (zset)
        """
        return f'kline:{kline_symbol}:zset'

    @prefixed_key
    def tasks_key(self) -> str:
        """
        tasks:key:list
        Redis typeL list
        """
        return 'tasks:key:list'

    @prefixed_key
    def task_hash(self, task_id) -> str:
        """
        tasks:hash:(task_id)
        task_id: Task.id
        Redis type hash
        """
        return f'tasks:hash:{task_id}'

    @prefixed_key
    def report_key(self, symbol_key: str) -> str:
        """
        reports:key:list
        Redis typeL list
        """
        return f'report:{symbol_key}:list'

    @prefixed_key
    def report_hash(self, symbol_key: str, report_key: int) -> str:
        """
        reports:hash:(report_id)
        task_id: Task.id
        :Redis type hash
        """
        return f'report:{symbol_key}:hash:{report_key}'

    @prefixed_key
    def report_set(self, symbol: str):
        """
        report:{symbol}:set
        Redis typeL sorted set (zset)
        """
        return f'report:{symbol}:zset'
