from collections import defaultdict
import time
import typing as t

from unicorn_binance_websocket_api import BinanceWebSocketApiManager

from .binance_api_manager import BinanceAPIManager
from .logger import Logger
from .trader import Trader
from .config import Config
from db.connections import RedisConnection
from db.models import Kline, Task
from db.schema import KlineSchema, TaskSchema


class BinanceConnectionManager:
    """
    Entity for initialization websocket stream session and management inside session.
    """
    def __init__(self, api_manager: BinanceAPIManager, config: Config, logger: Logger, trader: t.Union[Trader, None],
                 db: RedisConnection, spot_trader: Trader = None, margin_trader: Trader = None, both=False):
        self.logger = logger
        self.config = config
        self.db = db
        self.manager = api_manager
        self.both = both
        if self.both:
            self.spot_trader = spot_trader
            self.margin_trader = margin_trader
            self.trader = None
        else:
            self.trader = trader

        self._connect_to_stream()

        self.reconnected = 1
        self.in_work = True

    def _stream_processor(self):
        """
        Get info from websocket connection and transfer it to trade algoritm.
        :return:
        """
        counter = 0
        try:
            spot_kline_last_time = 0
            margin_kline_last_time = 0
            while counter < 10000:
                if self.bw_api_manager.is_manager_stopping():
                    return

                stream_data = self.bw_api_manager.pop_stream_data_from_stream_buffer()

                if stream_data is not False:
                    counter = 0
                    kline_data = stream_data.get("kline", None)
                    if kline_data:
                        if (kline_data["kline_start_time"] > spot_kline_last_time or
                                kline_data["kline_start_time"] > margin_kline_last_time):
                            if self.both:
                                if (stream_data["symbol"] == self.spot_trader.global_strategy.bid_symbol and
                                        kline_data["kline_start_time"] > spot_kline_last_time):
                                    spot_kline_last_time = kline_data["kline_start_time"]
                                    spot_response = self.spot_trader.use_strategy(kline_data, stream_data["event_time"])
                                    if spot_response is False:
                                        time.sleep(60 * 10)
                                    self.spot_trader.make_report(spot_response)

                                if (stream_data["symbol"] == self.margin_trader.global_strategy.bid_symbol and
                                        kline_data["kline_start_time"] > margin_kline_last_time):
                                    margin_kline_last_time = kline_data["kline_start_time"]
                                    margin_response = self.margin_trader.use_strategy(kline_data,
                                                                                      stream_data["event_time"])

                                    if margin_response is False:
                                        time.sleep(60 * 10)
                                    self.margin_trader.make_report(margin_response)
                            else:
                                if stream_data["symbol"] == self.trader.global_strategy.bid_symbol:
                                    spot_kline_last_time = margin_kline_last_time = kline_data["kline_start_time"]
                                    response = self.trader.use_strategy(kline_data, stream_data["event_time"])
                                    if response is False:
                                        time.sleep(60 * 10)
                                    self.trader.make_report(response)
                            self.save_kline_data(stream_data)
                if stream_data is False:
                    counter += 0.01
                    time.sleep(0.01)
                self.check_for_tasks()
        finally:
            if self.reconnected > 15:
                time.sleep(60)
                self.stop()
            elif not self.in_work:
                self.logger.info("stopping")
                return
            else:
                self.logger.info("Too many tries for reconnect, Connection was closed. reconnecting.")
                self.close()
                time.sleep(60 * self.reconnected)
                self._connect_to_stream()
                self.reconnected += 1
                self._stream_processor()

    def _connect_to_stream(self):
        self.bw_api_manager = BinanceWebSocketApiManager(
            output_default="UnicornFy", enable_stream_signal_buffer=True, exchange=f"binance.{self.config.BINANCE_TLD}"
        )
        self.bw_api_manager.create_stream(
            ["arr"], ["!userData"], api_key=self.config.BINANCE_API_KEY, api_secret=self.config.BINANCE_API_SECRET_KEY
        )

        self.bw_api_manager.create_stream(
            channels=[self.config.KLINE_TIMEFRAME],
            markets=[(self.config.TARGET_MARGIN_SYMBOL + self.config.BRIDGE_MARGIN_SYMBOL),
                     (self.config.TARGET_SPOT_SYMBOL + self.config.BRIDGE_SPOT_SYMBOL)],
            api_key=self.config.BINANCE_API_KEY,
            api_secret=self.config.BINANCE_API_SECRET_KEY
        )

    def save_kline_data(self, data):
        """Add to redis db hash websocket kline data using event time as a key."""
        kline_report = defaultdict(**data["kline"])
        kline_report["event_time"] = data["event_time"]
        kline_report["symbol"] = data["symbol"]
        kline = Kline(**kline_report)

        list_key = self.db.key_schema.kline_key(kline.symbol)
        hash_key = self.db.key_schema.kline_hash(kline.symbol, kline.event_time)
        set_key = self.db.key_schema.kline_set(kline.symbol)
        pipeline = self.db.redis_client.pipeline()
        pipeline.hset(hash_key, mapping=KlineSchema().dump(kline))
        pipeline.lpush(list_key, kline.event_time)
        pipeline.zadd(set_key, mapping={kline.event_time: kline.event_time})
        pipeline.execute()

    def check_for_tasks(self):
        """
        Check for tasks in db task hash. If it is, execute task.
        :return:
        """
        task_list = self.db.key_schema.tasks_key()
        task_len = self.db.redis_client.llen(task_list)
        if task_len > 0:
            self.logger.info("We have task.")

            hash_key = int(self.db.redis_client.rpop(task_list))
            task_hash_key = self.db.key_schema.task_hash(hash_key)
            task_hash = self.db.redis_client.hgetall(task_hash_key)
            self.db.redis_client.hdel(task_hash_key, *task_hash.keys())

            task = TaskSchema().load(task_hash.decode("utf-8"))
            self.execute_task(task)

    def execute_task(self, task: Task):
        """
        Get task by task name from db and execute it.
        :param task:
        :return:
        """
        execution_dict = {
            "START": self.start,
            "STOP": self.stop,
            "PAUSE": self.pause,
            "CONTINUE": self.continue_,
            "CLOSE_POSITION": self.close_position
        }
        task_func = execution_dict[task.task]
        task_func()
        return

    def start(self):
        """
        Start stream and trade bot.
        :return:
        """
        if self.in_work:
            self.logger.info("We already in work. Don't try to start me!")
            return
        else:
            self.in_work = True
            self.logger.info("Starting.")
            self.initialization()
            return

    def stop(self):
        """
        Stop trading and stream process.
        :return:
        """
        if not self.in_work:
            self.logger.info("I'm already stop. Don't try to stop me, imao!")
            return
        else:
            self.in_work = False
            self.logger.info("Stopping.")
            self.close_position()
            self.close()
            while not self.in_work:
                self.check_for_tasks()
                time.sleep(1)

    def pause(self):
        """
        Pause stream process.
        :return:
        """
        if not self.in_work:
            self.logger.info("I'm already stop. Don't try to stop me, imao!")
            return
        else:
            self.in_work = False
            self.logger.info("In pause.")
            self.close()
            while not self.in_work:
                self.check_for_tasks()
                time.sleep(1)

    def continue_(self):
        """
        Continue stream process.
        :return:
        """
        if self.in_work:
            self.logger.info("We already in work. Don't try to start me!")
            return
        else:
            self.in_work = True
            self.logger.info("Continue.")
            self._stream_processor()
            return

    def close_position(self):
        """
        Close open position in trade.
        :return:
        """
        if self.both:
            self.spot_trader.close_trades()
            self.margin_trader.close_trades()
        else:
            self.trader.close_trades()

        return

    def close(self):
        """
        Close all websocket connections and streams.
        :return:
        """
        self.bw_api_manager.stop_manager_with_all_streams()

    def initialization(self):
        """
        Initialize trader and start stream.
        :return: None
        """
        if self.both:
            self.spot_trader.initialization()
            self.margin_trader.initialization()
        else:
            self.trader.initialization()

        self._stream_processor()
