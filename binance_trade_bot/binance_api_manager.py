import typing as t
from decimal import Decimal
from requests.exceptions import ReadTimeout

from binance.client import Client
from binance.enums import *

from .logger import Logger


class BinanceAPIManager:
    """
    Manager of binance API. Include all possible and useful for strategy requests.
    """
    def __init__(self, config, logger: Logger):
        self.config = config
        self.logger = logger
        self.binance_client = Client(self.config.BINANCE_API_KEY, self.config.BINANCE_API_SECRET_KEY)

    def get_account(self):
        """
        Get account data.
        :return: data{'balances': [{'asset':'', 'free':'', 'locked':''}, ...], ...}
        """
        account = self.binance_client.get_account()
        return account

    def check_balance(self, bridge_coin, target_coin):
        """
        Takes balance from accoun and save only usable.
        :param bridge_coin: coin tha is not crypto-coin.
        :param target_coin: crypto-coin that we're going to trade.
        :return: dict({'bridge/target coin': number of free coins})
        """
        coins = self.get_account()["balances"]
        balance = {}
        for coin in coins:
            if coin["asset"] == bridge_coin:
                balance[bridge_coin] = {"free": Decimal(coin["free"])}
            elif coin["asset"] == target_coin:
                balance[target_coin] = {"free": Decimal(coin["free"])}
        return balance

    def get_last_candle(self, symbol: str, interval: str):
        """
        Get candle of taken symbol of target and bridge coin for last hour with 1 hour interval.
        :param symbol: pair symbol. For example: 'BTCUSDT'.
        :param interval: time interval for request. Could be [minute, hour, day, Month, ...]
        :return: generator with list of candle data.
        """
        try:
            kline = self.binance_client.get_historical_klines_generator(symbol,
                                                                        self.config.KLINE_INTERVAL,
                                                                        f"2 {interval} ago UTC")
            return next(kline)
        except ReadTimeout:
            self.logger.warning("We have some timout exception here.")
            return None

    def get_period_candles(self, symbol: str, period: int, interval: str) -> t.Generator:
        """
        Get candles for fixed period with fixed time interval and return as generator.
        :param symbol: target + bridge assets.
        :param period: period for SMA.
        :param interval: time interval. May be mminute, hour, day, Month ..
        :return: Generator of historical candles.
        """
        klines_list = self.binance_client.get_historical_klines_generator(symbol,
                                                                          self.config.KLINE_INTERVAL,
                                                                          f"{period + 1} {interval} ago UTC")
        return klines_list

    def get_symbol_info(self, symbol: str) -> dict:
        """
        Return dict with list of dict wich has information about symbol include lot min size and min notional.
        :param symbol:  target + bridge assets.
        :return: dict.
        """
        return_info = self.binance_client.get_symbol_info(symbol)
        return return_info

    def place_order(self,
                    symbol: str,
                    side: str,
                    quantity: t.Union[float, Decimal],
                    type: str = ORDER_TYPE_MARKET) -> t.Union[dict, None]:
        """
        Create a new order on spot place. Market order by default. If something goes wrong, return None instead.
        :param symbol: target + bridge assets.
        :param side: SELL or BUY.
        :param quantity: amount of coins.
        :param type: type of order. Could be limit, market or another. Look into API docs for detail.
        :return: dict or None.
        """
        try:
            order = self.binance_client.create_order(symbol=symbol,
                                                     side=side,
                                                     quantity=float(quantity),
                                                     type=type)

            return order
        except ReadTimeout:
            self.logger.warning("We have some timout exception here.")
            return None
        except Exception as e:
            self.logger.warning("We have an unexpected error.")
            self.logger.warning(e)
            return None

    def cancel_order(self, symbol: str, order_id: str) -> t.Union[dict, None]:
        """
        Cancel created order if something went wrong.
        :param symbol: target + bridge assets.
        :param order_id: id of created order.
        :return: dict or None.
        """
        try:
            order = self.binance_client.cancel_order(symbol=symbol, orderId=order_id)
        except Exception as e:
            self.logger.info("We got an exception while canceling order.")
            self.logger.info(e.__class__.__name__)
            self.logger.info(e)
            return None

        return order

    def buy(self, symbol: str, quantity: Decimal, lot_size: Decimal, margin: bool = False):
        """
        Round amount of coin and place buy order on spot or margin trade market.
        :param symbol: target + bridge assets.
        :param quantity: amount of buying coins.
        :param lot_size: minimum amount of coins for order.
        :param margin: place on spot or margin market. Default - on spot.
        :return: Response dict.
        """
        extra = quantity % lot_size
        round_quantity = quantity - extra
        self.logger.debug("Here our normalize quantity to buy: %s" % round_quantity)
        if margin:
            order = self.place_margin_order(symbol, SIDE_BUY, round_quantity)
        else:
            order = self.place_order(symbol, SIDE_BUY, round_quantity)

        return order

    def sell(self, symbol: str, quantity: Decimal, lot_size: Decimal, margin: bool = False):
        """
        Round amount of coin and place sell order on spot or margin trade market.
        :param symbol: target + bridge assets.
        :param quantity: amount of selling coins.
        :param lot_size: minimum amount of coins for order.
        :param margin: place on spot or margin market. Default - on spot.
        :return: Response dict.
        """
        extra = quantity % lot_size
        round_quantity = quantity - extra
        self.logger.debug("Here our normalize quantity to sell: %s" % round_quantity)
        if margin:
            order = self.place_margin_order(symbol, SIDE_SELL, round_quantity)
        else:
            order = self.place_order(symbol, SIDE_SELL, round_quantity)

        return order

    def get_margin_account(self):
        """
        Get account data.
        :return: data{'userAssets': [{'asset':'', 'free':'', 'borrowed':'', 'netAsset':''}, ...], ...}
        """
        account = self.binance_client.get_margin_account()
        return account

    def check_margin_balance(self, bridge_coin: str, target_coin: str) -> dict:
        """
        Takes balance from accoun and save only usable.
        :param bridge_coin: coin tha is not crypto-coin.
        :param target_coin: crypto-coin that we're going to trade.
        :return: dict({'bridge/target coin': number of free coins})
        """
        coins = self.get_margin_account()["userAssets"]
        balance = {}
        for coin in coins:
            if coin["asset"] == bridge_coin:
                balance[bridge_coin] = {"free": Decimal(coin["free"]),
                                        "borrowed": Decimal(coin["borrowed"])}
            elif coin["asset"] == target_coin:
                balance[target_coin] = {"free": Decimal(coin["free"]),
                                        "borrowed": Decimal(coin["borrowed"])}
        return balance

    def repay_loan(self, symbol: str, quantity: Decimal, lot_size: Decimal) -> dict:
        """
        Repay all loan coins to broker.
        :param symbol: asset of repaying coin.
        :param quantity: amount of repaying coin.
        :param lot_size: minimum amount of coins for order.
        :return: Response dict.
        """
        self.logger.info("Here our normalize quantity to repay loan: %s" % quantity)
        try:
            order = self.binance_client.repay_margin_loan(asset=symbol, amount=quantity)
        except Exception as e:
            self.logger.info("We Have an exception while repaying loan.")
            self.logger.info(e.__class__.__name__)
            self.logger.info(e)
            order = None

        return order

    def get_loan(self, symbol: str, quantity: Decimal, lot_size: Decimal):
        """
        Loan specified amount of coins for margin trade.
        :param symbol: asset of repaying coin.
        :param quantity: amount of repaying coin.
        :param lot_size: minimum amount of coins for order.
        :return: Response dict.
        """
        extra = quantity % lot_size
        round_quantity = quantity - extra
        self.logger.info("Here our normalize quantity to loan: %s" % round_quantity)
        try:
            order = self.binance_client.create_margin_loan(asset=symbol, amount=round_quantity)
        except Exception as e:
            self.logger.info("We Have an exception while geting loan.")
            self.logger.info(e.__class__.__name__)
            self.logger.info(e)
            order = None

        return order

    def place_margin_order(self,
                           symbol: str,
                           side: str,
                           quantity: t.Union[float, Decimal],
                           type: str = ORDER_TYPE_MARKET) -> t.Union[dict, None]:
        """
        Create a new order on spot place. Market order by default. If something goes wrong, return None instead.
        :param symbol: target + bridge assets.
        :param side: SELL or BUY.
        :param quantity: amount of coins.
        :param type: type of order. Could be limit, market or another. Look into API docs for detail.
        :return: dict or None.
        """
        try:
            order = self.binance_client.create_margin_order(symbol=symbol,
                                                            side=side,
                                                            quantity=float(quantity),
                                                            type=type)

            return order
        except ReadTimeout:
            self.logger.warning("We have some timout exception here.")
            return None
        except Exception as e:
            self.logger.warning("We have an unexpected error.")
            self.logger.info(e.__class__.__name__)
            self.logger.warning(e)
            return None

    def cancel_margin_order(self, symbol: str, order_id: str) -> t.Union[dict, None]:
        """
        Cancel created order if something went wrong.
        :param symbol: target + bridge assets.
        :param order_id: id of created order.
        :return: dict or None.
        """
        try:
            order = self.binance_client.cancel_margin_order(symbol=symbol, orderId=order_id)
        except Exception as e:
            self.logger.info("We got an exception while canceling order.")
            self.logger.info(e.__class__.__name__)
            self.logger.info(e)
            return None

        return order
