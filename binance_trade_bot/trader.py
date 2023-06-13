from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from operator import itemgetter
import numpy as np
import typing as t
import talib
import time

from .binance_api_manager import BinanceAPIManager
from .logger import Logger
from .config import Config
from db.connections import RedisConnection
from db.models import Report
from db.schema import ReportSchema


class GlobalStrategy:
    """
    Definition entity. Encapsulate two coin that would be trade.
    """
    def __init__(self, bridge_coin="USDT", target_coin="BTC"):
        self.bridge_coin = bridge_coin
        self.target_coin = target_coin
        self.bid_symbol = self.target_coin + self.bridge_coin


class Portfolio:
    """
    Definition entity. Encapsulate balances and orders.
    """
    def __init__(self):
        # Balance of portfolio. Include target and bridge coins.
        self.balance: t.Union[t.Dict[str, Decimal], None] = {}
        # For now 20% of bridge coin balance.
        self.working_balance: Decimal = Decimal(0)
        # Price condition of target coin  for strategy.
        self.target_order: t.Tuple[Decimal, Decimal] = (Decimal(0), Decimal(0))
        # Price The expected price to sell all target coins if candle is too downgrade.
        self.stop_loss: Decimal = Decimal(0)
        # Price of the last order.
        self.current_portfolio_price: Decimal = Decimal(0)
        self.margin_credit: Decimal = Decimal(0)
        self.last_price: Decimal = Decimal(0)
        self.profit: Decimal = Decimal(0)
        self.total_profit: Decimal = Decimal(0)
        self.start_balance: Decimal = Decimal(0)


def generate_strategy(strategy: dict) -> str:
    """
    Strategy index generator. Return strategy key from strategy dict in config.
    :param strategy: strategy dict define in config.py.
    :return: str index.
    """
    while True:
        for strategy_index in strategy.keys():
            yield strategy_index


class Trader:
    """
    Entity for management trade strategy.
    """
    def __init__(self, api_manager: BinanceAPIManager, db: t.Optional[RedisConnection], global_strategy: GlobalStrategy,
                 config: Config, logger: Logger):
        self.logger = logger
        self.config = config
        self.manager = api_manager
        self.db = db
        self.global_strategy = global_strategy
        self.portfolio = Portfolio()
        self.minute_candle_price: Decimal = Decimal(0)
        self.past_minute_candle_price: Decimal = Decimal(0)
        self.period_candle_price: t.List[t.Tuple[int, Decimal, Decimal, Decimal]] = []
        self.period_candle_price_updated: bool = False
        self.moving_average: Decimal = Decimal(0)
        self.max_period_price = Decimal(0)
        self.min_period_price = Decimal(0)
        self.lot_size: Decimal = Decimal(0)
        self.min_notional: Decimal = Decimal(0)
        self.current_strategy: t.Union[str, None] = None
        self.strategy_generator = generate_strategy(self.config.STRATEGY_DICT)
        self.current_time: int = 0
        self.default_order = {"side": "-",
                              "executedQty": "-",
                              "origQty": "-",
                              "fills": [{"price": "-", "qty": "-"}],
                              "status": "NO_ORDER",
                              "order_price": "-"}

    def __str__(self):
        return "Base Trader class."

    def initialization(self):
        """
        Initialize default params for class. Get historical candle data.
        """
        self.update_account_status()
        self.initialize_candle_list()

    def _reboot_generator(self):
        """
        Return generator to the firs strategy index.
        """
        del self.strategy_generator
        self.strategy_generator = generate_strategy(self.config.STRATEGY_DICT)

    def _reboot_strategy(self):
        self._reboot_generator()
        self.current_strategy = "INITIAL"
        self.portfolio.last_price = 0
        self.update_balance()
        self.set_working_balance()

    def target_dict(self, strategy):
        """
        Dict of strategy.
        :param strategy: index of strategy. In this version could be A B or C.
        :return: tuple(target price of coin, ammount of coin  will be sell)
        """
        targets = self.config.STRATEGY_DICT
        return targets[strategy]

    def update_max_and_min_period_price(self):
        """
        Get max close price from last seven hour candle data.
        """
        self.max_period_price = max(self.period_candle_price, key=itemgetter(1))[1]
        self.min_period_price = min(self.period_candle_price, key=itemgetter(1))[1]

    def update_current_portfolio_price(self):
        """
        Calculate new price of portfolio and update current_portfolio_price
        """
        self.portfolio.current_portfolio_price = ((self.portfolio.balance[self.global_strategy.target_coin]["free"] *
                                                  self.minute_candle_price) +
                                                  self.portfolio.balance[self.global_strategy.bridge_coin]["free"])

    def set_strategy(self):
        """
        Set strategy params if self.current_strategy is None.
        :return:
        """

    def set_working_balance(self):
        """
        Set balance based on fixed percent of bridge coin amount. Default 20% of bridge coin.
        """
        if self.config.WORKING_BALANCE > 1.00:
            self.logger.warning("Your working balance config more tha 100% of your money. "
                                "You can't trading more money, than you have. Check you configs.")
        self.portfolio.working_balance = (self.portfolio.balance[self.global_strategy.bridge_coin]["free"] *
                                          self.config.WORKING_BALANCE)

    def update_strategy(self):
        """
        Get new strategy symbol from generator and update target order.
        """
        self.current_strategy = next(self.strategy_generator)
        target_percent, amount_percent = self.target_dict(self.current_strategy)
        target_price = self.minute_candle_price * Decimal(target_percent)
        target_amount = self.portfolio.balance[self.global_strategy.target_coin]["free"] * Decimal(amount_percent)
        self.portfolio.target_order = (target_price, target_amount)
        self.update_stop_loss()

    def update_stop_loss(self):
        """
        Update sell price for stop loosing money.
        """
        self.portfolio.stop_loss = self.minute_candle_price * self.config.SPOT_STOP_LOSS

    def update_balance(self):
        """
        Update bridge and target coin amount after successful order.
        """

    def update_account_status(self):
        """
        Update prices and check trading status.
        """

    def update_moving_average(self):
        """
        Get moving average from candle data and save it in self.moving_average.
        :return:
        """
        ma_list = talib.SMA(np.array([float(candle[1]) for candle in self.period_candle_price]),
                            self.config.SMA_PERIOD)
        self.moving_average = ma_list[-1]

    def calculate_total_profit(self):
        """
        Calculate difference between start portfolio price and current portfolio price.
        :return: Decimal difference.
        """

    def check_for_hour_kline_update(self, unix_time: int):
        """
        Check that minute candlestick is 1 hour later than las hour candlestick. If it is - update last.
        :param unix_time: stream_data["kline"]["kline_start_time"]
        """
        self.period_candle_price_updated = False
        if unix_time - (self.config.UNIX_TIME_INTERVAL * 2) >= self.period_candle_price[-1][0]:
            self.period_candle_price.pop(0)
            latest_candle = self.manager.get_last_candle(self.global_strategy.bid_symbol, self.config.TIME_INTERVAL)
            if latest_candle is None:
                return
            self.period_candle_price.append((latest_candle[0], Decimal(latest_candle[1]),
                                             Decimal(latest_candle[3]), Decimal(latest_candle[2])))
            self.update_moving_average()
            self.update_max_and_min_period_price()
            self.period_candle_price_updated = True

    def check_for_min_notional(self):
        """
        Check bridge balance equal or more than min notional of trade symbol.
        :return:
        """
        if self.portfolio.working_balance < self.min_notional:
            return False
        return True

    def initialize_candle_list(self):
        """
        Fill the seven_hour_candle_price by last 7 hours candles.
        :return: None
        """
        if len(self.period_candle_price) < self.config.SMA_PERIOD:
            candles = self.manager.get_period_candles(self.global_strategy.bid_symbol,
                                                      self.config.SMA_PERIOD,
                                                      self.config.TIME_INTERVAL)

            self.period_candle_price = []
            for _ in range(self.config.SMA_PERIOD):
                candle = next(candles)
                self.period_candle_price.append((candle[0], Decimal(candle[1]), Decimal(candle[3]), Decimal(candle[2])))
            self.update_moving_average()
            self.update_max_and_min_period_price()

    def use_strategy(self, data: dict, current_time: int):
        """
        Make a cell or buy decision based on current data.
        :param data: stream_data["kline"]
        :param current_time: stream_data["event_time"]
        """
        self.check_for_hour_kline_update(data["kline_start_time"])
        self.current_time = current_time

    def sell(self, quantity: Decimal):
        """
        Sell fixed quantity of coins, update current strategy and portfolio balance.
        """

    def buy(self, cancel_func, quantity: t.Union[Decimal, None] = None, margin: bool = False, *args, **kwargs):
        """
        Buy fixed quantity of coins, update current strategy and portfolio balance.
        """
        if quantity is None:
            quantity = self.portfolio.working_balance / self.minute_candle_price
        order = self.manager.buy(symbol=self.global_strategy.bid_symbol,
                                 quantity=quantity,
                                 lot_size=self.lot_size,
                                 margin=margin)
        if order is None:
            count = 0
            while count < 10:
                count += 1
                self.logger.info("Order is None. Trying to rebuy coin. Attempt %s/10" % count)
                time.sleep(1)
                order = self.manager.buy(symbol=self.global_strategy.bid_symbol,
                                         quantity=quantity,
                                         lot_size=self.lot_size,
                                         margin=margin)
                if order is not None:
                    break
            if order is None:
                return None
        self.update_balance()

        if order["status"] != "FILLED" or order["executedQty"] != order["origQty"]:
            cancel_order = None
            while cancel_order is None:
                time.sleep(2)
                cancel_order = cancel_func(self.global_strategy.bid_symbol, order["orderID"])

            return None

        return order

    def sell_all(self, cancel_func, margin: bool = False, *args, **kwargs):
        """
        Sell all coins, and close trade.
        """
        order = self.manager.sell(symbol=self.global_strategy.bid_symbol,
                                  quantity=self.portfolio.balance[self.global_strategy.target_coin]["free"],
                                  lot_size=self.lot_size,
                                  margin=margin)
        if order is None:
            count = 0
            while order is None and count < 10:
                count += 1
                self.logger.info("Order is None. Trying to resell coin. Attempt %s/10" % count)
                time.sleep(1)
                order = self.manager.sell(symbol=self.global_strategy.bid_symbol,
                                          quantity=self.portfolio.balance[self.global_strategy.target_coin]["free"],
                                          lot_size=self.lot_size,
                                          margin=margin)
            if order is None:
                return None

        if order["status"] != "FILLED":
            cancel_order = None
            while cancel_order is None:
                cancel_order = self.manager.cancel_order(self.global_strategy.bid_symbol, order["orderID"])
            while order["status"] != "FILLED":
                self.update_balance()
                order = self.manager.sell(symbol=self.global_strategy.bid_symbol,
                                          quantity=self.portfolio.balance[self.global_strategy.target_coin]["free"],
                                          lot_size=self.lot_size,
                                          margin=margin)

        if float(order["executedQty"]) != float(order["origQty"]):
            self.update_balance()
            try:
                self.sell_all(cancel_func)
            except RecursionError:
                self.logger.info("Too many recursion. I'm out.")
                return None

        return order

    def close_trades(self):
        """
        Sell all target coins if they are.
        """

    def make_report(self, order: dict, initial: bool = False):
        """
        Create a report and print it in logs if there is a trade transaction or MA was updated.
        :param order: order Response dict.
        :param initial: Bool flag. If True undoubtedly send the report.
        :return: None
        """
        if self.__str__() == "MARGIN":
            target_balance = (f"free: {str(self.portfolio.balance[self.global_strategy.target_coin]['free'])} | "
                              f"borrowed: {str(self.portfolio.balance[self.global_strategy.target_coin]['borrowed'])}")
        else:
            target_balance = self.portfolio.balance[self.global_strategy.target_coin]["free"]
        if order["side"] != "-" or self.period_candle_price_updated or initial:
            report = defaultdict(
                event_time=self.current_time,
                market_place=self.__str__(),
                target_coin=self.global_strategy.target_coin,
                bridge_coin=self.global_strategy.bridge_coin,
                moving_average=float(self.moving_average),
                minimum_price=float(self.min_period_price),
                max_price=float(self.max_period_price),
                stop_loss=float(self.portfolio.stop_loss),
                bridge_balance=float(self.portfolio.balance[self.global_strategy.bridge_coin]["free"]),
                target_balance=str(target_balance),
                current_strategy=self.current_strategy,
                order_side=order["side"],
                order_quantity=order["executedQty"],
                order_price=str((Decimal(order["executedQty"]) * Decimal(order["fills"][0]["price"]))
                                if order["side"] != "-" else "-"),
                candle_price=str(Decimal(order["fills"][0]["price"]) if order["side"] != "-" else "-"),
                profit=str(self.portfolio.profit if self.portfolio.profit != Decimal(0) else "-"),
                bridge_balance_profit=float(self.portfolio.total_profit)
            )
            self.logger.info(self.config.REPORT_TEMPLATE.format(**report))
            self.save_report(Report(**report))

    def save_report(self, report: Report):
        """
        Save report to Redis db using current time as a key for hash.
        :param report: class Report.
        :return: None.
        """
        if self.db is None:
            return
        symbol = (report.target_coin + report.bridge_coin)
        list_key = self.db.key_schema.report_key(symbol)
        hash_key = self.db.key_schema.report_hash(symbol, self.current_time)
        set_key = self.db.key_schema.report_set(symbol)

        pipeline = self.db.redis_client.pipeline()
        pipeline.lpush(list_key, self.current_time)
        pipeline.zadd(set_key, mapping={self.current_time: self.current_time})
        pipeline.hset(hash_key, mapping=ReportSchema().dump(report))
        pipeline.execute()
