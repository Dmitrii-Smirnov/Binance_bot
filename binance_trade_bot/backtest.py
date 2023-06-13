import csv
from decimal import Decimal
import os
import pandas as pd
import typing as t

from .binance_api_manager import BinanceAPIManager
from .trader import GlobalStrategy
from .config import Config
from .logger import Logger


class MockAPIManager(BinanceAPIManager):
    """
    Imitate binance api response for backtests of spot trading.
    """
    def __init__(self, config: Config, logger: Logger, global_strategy: GlobalStrategy, history_period: int = 6):
        super().__init__(config, logger)
        # How old would be data.
        self.global_strategy = global_strategy
        self.HISTORY_MONTH_PERIOD = history_period
        self.BACKTEST_BRIDGE_BALANCE = Decimal(50)
        self.BACKTEST_TARGET_BALANCE = Decimal(0.00000)
        self.BACKTEST_PORTFOLIO_PRICE = Decimal(50)
        self.time_format = self.config.TIME_FORMAT
        self.minute_candle_data_path = self.config.BACKTEST_MINUTE_CANDLE_DATA_PATH.format(
            target_symbol=self.global_strategy.target_coin, bridge_symbol=self.global_strategy.bridge_coin
                                                                                           )
        self.period_candle_data_path = self.config.BACKTEST_PERIOD_CANDLE_DATA_PATH.format(
            target_symbol=self.global_strategy.target_coin, bridge_symbol=self.global_strategy.bridge_coin
                                                                                           )
        self.historical_hour_candles = self._get_historical_interval_candles_fo_period(
            self.global_strategy.target_coin + self.global_strategy.bridge_coin
                                                                                       )
        self.historical_minute_candles = self._get_historical_minute_candles_fo_half_year(
            self.global_strategy.target_coin + self.global_strategy.bridge_coin
                                                                                       )
        self.current_price = 0
        self.init_done = False

    def get_account(self):
        """
        Get account data.
        :return: data{'balances': [{'asset':'', 'free':'', 'locked':''}, ...], ...}
        """
        account = {"balances": [{"asset": f"{self.global_strategy.bridge_coin}",
                                 "free": f"{self.BACKTEST_BRIDGE_BALANCE}"},
                                {"asset": f"{self.global_strategy.target_coin}",
                                 "free": f"{self.BACKTEST_TARGET_BALANCE}"}
                                ]}
        return account

    def _update_balance(self):
        self.BACKTEST_PORTFOLIO_PRICE = (self.BACKTEST_BRIDGE_BALANCE +
                                         (self.BACKTEST_TARGET_BALANCE * self.current_price))

    def get_last_candle(self, symbol: str, interval: str):
        """
        Get candle of taken symbol of target and bridge coin for last hour with 1 hour interval.
        :param symbol: pair symbol. For example: 'BTCUSDT'.
        :return: generator with list of candle data.
        """
        kline = next(self.historical_hour_candles)

        return kline

    def get_server_time(self):
        """
        Make request to the binance server and get it time.
        :return:
        """
        time = self.binance_client.get_server_time()
        return time

    def get_last_minute_candle(self):
        """
        On start of backtest will skip minutes candles for the period of hour candle. Than would be return
        list of minute candle data.
        :return:
        """
        if self.init_done is False:
            for _ in range(self.config.SMA_PERIOD*60):
                next(self.historical_minute_candles)
            self.init_done = True
        raw_candle = next(self.historical_minute_candles)
        candle = {"kline_start_time": raw_candle[0], "open_price": raw_candle[1]}
        self.current_price = Decimal(candle["open_price"])
        self._update_balance()
        return candle

    def get_period_candles(self, symbol: str, period: int, interval: str) -> t.Generator:
        """
        Get candles for the fixed period with fixed interval from binance api.
        :param symbol: trade symbol (target_coin)+(bridge_coin).
        :param period: int time period for request.
        :param interval: str interval of time. May be minute, hour, day, Month...
        :return: list of candles.
        """
        klines_list = (self.get_last_candle(symbol, interval) for _ in range(period))
        return klines_list

    def _get_historical_minute_candles_fo_half_year(self, symbol: str) -> t.Generator:
        """
        Get minute trade candles for specified month period and save in in .csv file, ig it doesn't exist.
        :param symbol: target + bridge symbols.
        :return: Candles generator.
        """
        if not os.path.exists(self.minute_candle_data_path):
            klines_generator = self.binance_client.get_historical_klines_generator(symbol,
                                                                        self.binance_client.KLINE_INTERVAL_1MINUTE,
                                                                        f"{self.HISTORY_MONTH_PERIOD} month ago UTC")

            kline_df = pd.DataFrame([candle for candle in klines_generator])
            kline_df.to_csv(self.minute_candle_data_path, header=False, index=False)

        with open(self.minute_candle_data_path) as f:
            csv_reader = csv.reader(f, delimiter=",")
            for candle in csv_reader:
                candle[0] = int(candle[0])
                yield candle

    def _get_historical_interval_candles_fo_period(self, symbol: str) -> t.Generator:
        """
        Get specified time interval trade candles for specified month period and
        save in in .csv file, ig it doesn't exist.
        :param symbol: target + bridge symbols.
        :return: Candles generator.
        """
        if not os.path.exists(self.period_candle_data_path):
            klines_generator = self.binance_client.get_historical_klines_generator(symbol,
                                                                        self.config.KLINE_INTERVAL,
                                                                        f"{self.HISTORY_MONTH_PERIOD} month ago UTC")

            kline_df = pd.DataFrame([candle for candle in klines_generator])
            kline_df.to_csv(self.period_candle_data_path, header=False, index=False)

        with open(self.period_candle_data_path) as f:
            csv_reader = csv.reader(f, delimiter=",")
            for candle in csv_reader:
                candle[0] = int(candle[0])
                yield candle

    def buy(self, symbol: str, quantity: Decimal, lot_size: Decimal, margin: bool = False) -> dict:
        """
        Imitate buying coin.
        :param symbol: target_coin+bridge_coin.
        :param quantity: amount of buying coin.
        :param lot_size: minimum of quantity.
        :param margin: is margin trade, or not.
        :return: imitation dict of order.
        """
        extra = quantity % lot_size
        round_quantity = quantity - extra

        price = self.current_price * round_quantity
        self.BACKTEST_BRIDGE_BALANCE -= price
        self.BACKTEST_TARGET_BALANCE += round_quantity
        self._update_balance()

        order = {
            "side": "BUY",
            "executedQty": round_quantity,
            "origQty": round_quantity,
            "fills": [{"price": self.current_price, "qty": round_quantity}],
            "status": "FILLED",
            "order_price": price
        }

        return order

    def sell(self, symbol: str, quantity: Decimal, lot_size: Decimal, margin: bool = False) -> dict:
        """
        Imitate selling coin.
        :param symbol: target_coin+bridge_coin.
        :param quantity: amount of selling coin.
        :param lot_size: minimum of quantity.
        :param margin: is margin trade, or not.
        :return: imitation dict of order.
        """
        extra = quantity % lot_size
        round_quantity = quantity - extra
        price = self.current_price * round_quantity
        self.BACKTEST_BRIDGE_BALANCE += price
        self.BACKTEST_TARGET_BALANCE -= round_quantity
        self._update_balance()

        order = {
            "side": "SELL",
            "executedQty": round_quantity,
            "origQty": round_quantity,
            "fills": [{"price": self.current_price, "qty": round_quantity}],
            "status": "FILLED",
            "order_price": price
        }

        return order


class MockMarginAPIManager(MockAPIManager):
    """
    Imitate binance api response for backtests of margin trading.
    """
    def __init__(self, config: Config, logger: Logger, global_strategy: GlobalStrategy, history_period: int = 6):
        super().__init__(config, logger, global_strategy, history_period)
        self.CREDIT_BALANCE: Decimal = Decimal(0)

    def get_margin_account(self):
        """
        Get account data.
        :return: data{'balances': [{'asset':'', 'free':'', 'locked':''}, ...], ...}
        """
        account = {"userAssets": [{"asset": f"{self.global_strategy.bridge_coin}",
                                  "free": f"{self.BACKTEST_BRIDGE_BALANCE}", "borrowed": 0},
                                  {"asset": f"{self.global_strategy.target_coin}",
                                   "free": f"{self.BACKTEST_TARGET_BALANCE}",
                                   "borrowed": f"{self.CREDIT_BALANCE}"}
                                ]}
        return account

    def _update_balance(self):
        """
        Change current portfolio balance.
        :return:
        """
        self.BACKTEST_PORTFOLIO_PRICE = (self.BACKTEST_BRIDGE_BALANCE +
                                         (self.BACKTEST_TARGET_BALANCE * self.current_price) -
                                         (self.CREDIT_BALANCE * self.current_price))

    def repay_loan(self, symbol: str, quantity: Decimal, lot_size: Decimal):
        """
        Imitate repaying loan. Change CREDIT_BALANCE and BACKTEST_TARGET_BALANCE. Than change portfolio price.
        No params are matter.
        """
        extra = quantity % lot_size
        round_quantity = quantity - extra
        self.BACKTEST_TARGET_BALANCE -= round_quantity
        self.CREDIT_BALANCE -= round_quantity
        self._update_balance()
        return True

    def get_loan(self, symbol: str, quantity: Decimal, lot_size: Decimal):
        """
        Imitate repaying loan. Change CREDIT_BALANCE and BACKTEST_TARGET_BALANCE. Than change portfolio price.
        No params are matter.
        """
        extra = quantity % lot_size
        round_quantity = quantity - extra
        self.BACKTEST_TARGET_BALANCE += round_quantity
        self.CREDIT_BALANCE += round_quantity
        self._update_balance()
        return True
