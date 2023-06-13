# Config consts
import configparser
import os
from decimal import Decimal
from binance.enums import *


CFG_FL_NAME = "user.cfg"
USER_CFG_SECTION = "binance_user_config"


class Config:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    def __init__(self):
        # Init config
        config = configparser.ConfigParser()
        config["DEFAULT"] = {
            "bridge": "USDT",
            "tld": "com",
            "strategy": "default",
            "sell_timeout": "0",
            "buy_timeout": "0",
        }

        if not os.path.exists(CFG_FL_NAME):
            print("No configuration file (user.cfg) found! See README. Assuming default config...")
            config[USER_CFG_SECTION] = {}
        else:
            config.read(CFG_FL_NAME)

        # Get config for binance
        self.BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY") or config.get(USER_CFG_SECTION, "api_key")
        self.BINANCE_API_SECRET_KEY = (os.environ.get("BINANCE_API_SECRET_KEY") or
                                       config.get(USER_CFG_SECTION, "api_secret_key"))
        self.BINANCE_TLD = os.environ.get("BINANCE_TLD") or config.get(USER_CFG_SECTION, "tld")

        # Configs for binance statistics.
        # Time period for moving average and historical candle.
        self.TIME_INTERVAL = "hour"
        self.UNIX_TIME_INTERVAL = Decimal(3600000)
        self.KLINE_TIMEFRAME = "kline_1m"
        self.TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
        self.KLINE_INTERVAL = KLINE_INTERVAL_1HOUR
        self.REPORT_TEMPLATE = ("\n"
                                "{market_place} | {target_coin}/{bridge_coin}\n"
                                "\n"
                                "Unix time: {event_time}\n"
                                "\n"
                                "MA: {moving_average}\n"
                                "Min: {minimum_price}\n"
                                "Max: {max_price}\n"
                                "Stop loss: {stop_loss}\n"
                                "\n"
                                "Cash({bridge_coin}): {bridge_balance}\n"
                                "{target_coin}: {target_balance}\n"
                                "\n"
                                "Current strategy: {current_strategy}\n"
                                "Activity: {order_side}\n"
                                "Quantity: {order_quantity}\n"
                                "Price({bridge_coin}): {order_price}\n"
                                "Market position price({bridge_coin}): {candle_price}\n"
                                "Profit({bridge_coin}): {profit}\n"
                                "Total profit: {bridge_balance_profit}")

        # Configs for trading.
        self.MARKET_PLACE = os.environ.get("market_place") or config.get(USER_CFG_SECTION, "market_place")
        self.BRIDGE_SPOT_SYMBOL = os.environ.get("BRIDGE_SYMBOL") or config.get(USER_CFG_SECTION, "bridge_spot_symbol")
        self.BRIDGE_MARGIN_SYMBOL = (os.environ.get("BRIDGE_SYMBOL") or
                                     config.get(USER_CFG_SECTION, "bridge_margin_symbol"))
        self.TARGET_SPOT_SYMBOL = os.environ.get("TARGET_SYMBOL") or config.get(USER_CFG_SECTION, "target_spot_symbol")
        self.TARGET_MARGIN_SYMBOL = (os.environ.get("TARGET_SYMBOL") or
                                     config.get(USER_CFG_SECTION, "target_margin_symbol"))
        self.SPOT_STOP_LOSS = Decimal(os.environ.get("SPOT_STOP_LOSS") or
                                      config.get(USER_CFG_SECTION, "spot_stop_loss"))
        self.MARGIN_STOP_LOSS = Decimal(os.environ.get("MARGIN_STOP_LOSS") or
                                        config.get(USER_CFG_SECTION, "margin_stop_loss"))
        self.MIN_PORTFOLIO_PRICE = Decimal(os.environ.get("MIN_PORTFOLIO_PRICE") or
                                           config.get(USER_CFG_SECTION, "min_portfolio_price"))
        self.SMA_PERIOD = int(os.environ.get("SMA_PERIOD") or config.get(USER_CFG_SECTION, "sma_period"))
        # Percent of bridge balance tha would bu used in trading.
        self.WORKING_BALANCE = Decimal(os.environ.get("WORKING_BALANCE") or
                                       config.get(USER_CFG_SECTION, "working_balance"))
        self.STRATEGY_DICT = {"FIRST_STEP": (Decimal(0), Decimal(0))}

        # Backtest configs.
        self.HISTORY_PERIOD_FOR_BACKTEST = 1
        self.BACKTEST_MINUTE_CANDLE_DATA_PATH = ("backtest_data/{target_symbol}{bridge_symbol}-"
                                                 f"{self.HISTORY_PERIOD_FOR_BACKTEST}_month-minute-data.csv")
        self.BACKTEST_PERIOD_CANDLE_DATA_PATH = ("backtest_data/{target_symbol}{bridge_symbol}-"
                                                 f"{self.HISTORY_PERIOD_FOR_BACKTEST}_month-"
                                                 f"{self.TIME_INTERVAL}-data.csv")
        self.BACKTEST_REPORT_DATA_PATH = ("backtest_data/{target_symbol}{bridge_symbol}-"
                                          f"{self.MARKET_PLACE}_report.csv")

        #Database
        self.REDIS_HOST = "redis"
        self.REDIS_PORT = "6379"
        self.CLEAR_DB = os.environ.get("CLEAR_DB") or config.get(USER_CFG_SECTION, "clear_db")
        self.DEFAULT_KEY_PREFIX = "binance-trade"
