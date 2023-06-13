import time
from decimal import Decimal

from binance_trade_bot.trader import Trader, GlobalStrategy, Portfolio
from binance_trade_bot.binance_api_manager import BinanceAPIManager


class SpotTrader(Trader):
    def __str__(self):
        return "SPOT"

    def calculate_total_profit(self):
        bridge_balance = self.portfolio.balance[self.global_strategy.bridge_coin]["free"]
        target_balance = self.portfolio.balance[self.global_strategy.target_coin]["free"]
        difference =(bridge_balance + (target_balance * self.minute_candle_price)) - self.portfolio.start_balance
        return difference

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
        target_coin = self.portfolio.balance[self.global_strategy.target_coin]["free"]
        bridge_coin = self.portfolio.balance[self.global_strategy.bridge_coin]["free"]
        self.portfolio.start_balance = bridge_coin + (target_coin * self.minute_candle_price)
        if target_coin < self.lot_size:
            self.current_strategy = "INITIAL"
        else:
            self.portfolio.last_price = target_coin * self.minute_candle_price
            self.update_strategy()

    def update_strategy(self):
        """
        Get new strategy symbol from generator and update target order.
        """
        self.current_strategy = next(self.strategy_generator)
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
        bridge_coin = self.global_strategy.bridge_coin
        target_coin = self.global_strategy.target_coin
        self.portfolio.balance = self.manager.check_balance(bridge_coin, target_coin)
        self.update_current_portfolio_price()

    def update_account_status(self):
        """
        Update prices and check trading status.
        """
        self.update_balance()

        bridge_coin = self.global_strategy.bridge_coin
        target_coin = self.global_strategy.target_coin

        symbol_info = self.manager.get_symbol_info(self.global_strategy.bid_symbol)
        self.lot_size = Decimal(symbol_info["filters"][2]["stepSize"])
        self.min_notional = Decimal(symbol_info["filters"][3]["minNotional"])

        if self.portfolio.balance[bridge_coin]["free"] == 0 and self.portfolio.balance[target_coin]["free"] == 0:
            self.logger.info("No cash on SPOT balance. You need to put some money here.")
            return
        if self.portfolio.balance[target_coin]["free"] < self.lot_size:
            self.set_working_balance()
        elif self.portfolio.balance[target_coin]["free"] > self.lot_size:
            self.logger.info("Something isn't correct. We've already have coins in SPOT.")
        else:
            self.logger.info("Something goes wrong: SPOT balance is less then zero.")

    def use_strategy(self, data: dict, current_time: int):
        """
        Make a cell or buy decision based on current data.
        :param data: stream_data["kline"]
        :param current_time: stream_data["event_time"]
        """
        super().use_strategy(data, current_time)
        self.portfolio.profit = 0
        if self.minute_candle_price == 0:
            self.minute_candle_price = Decimal(data["open_price"])
            self.past_minute_candle_price = self.minute_candle_price
        else:
            self.past_minute_candle_price = self.minute_candle_price
            self.minute_candle_price = Decimal(data["open_price"])

        if self.current_strategy is None:
            self.set_strategy()
            self.make_report(order=self.default_order, initial=True)

        if self.current_strategy == "INITIAL":
            if self.portfolio.current_portfolio_price > self.config.MIN_PORTFOLIO_PRICE:
                if ((self.max_period_price > self.past_minute_candle_price > self.moving_average) and
                        (self.max_period_price > self.minute_candle_price > self.past_minute_candle_price)):
                    more_than_min_notional = self.check_for_min_notional()
                    if more_than_min_notional is False:
                        self.logger.warning("We don't have enough money in SPOT working balance.")
                        return False
                    order = self.buy(self.manager.cancel_order)
                    if order is None:
                        self.logger.info("SPOT Failed to buy coin.")
                        return self.default_order

                    self.update_balance()
                    self.update_strategy()
                    self.portfolio.last_price = Decimal(order["executedQty"]) * Decimal(order["fills"][0]["price"])
                    return order
            else:
                self.logger.info("You've got not enough money for SPOT trade. You have only %s" %
                                 self.portfolio.current_portfolio_price)
        elif self.current_strategy in self.config.STRATEGY_DICT.keys():
            if self.portfolio.balance[self.global_strategy.target_coin]["free"] < self.lot_size:
                self.logger.info("We have SPOT strategy, but don't have coins. Rebooting strategy.")
                self._reboot_strategy()

            elif (((self.minute_candle_price >= self.max_period_price) or
                  (self.minute_candle_price <= self.portfolio.stop_loss)) and
                    self.portfolio.balance[self.global_strategy.target_coin]["free"] > self.lot_size):

                order = self.sell_all(self.manager.cancel_order)
                if order is None:
                    self.logger.info("SPOT Failed to sell coin.")
                    return self.default_order

                self.portfolio.profit = (Decimal(order["executedQty"]) *
                                         Decimal(order["fills"][0]["price"])) - self.portfolio.last_price
                self.portfolio.total_profit = self.calculate_total_profit()
                self._reboot_strategy()
                return order

        return self.default_order

    def close_trades(self):
        """
        Sell all target coins if they are.
        """
        if self.portfolio.balance[self.global_strategy.target_coin]["free"] > self.lot_size:
            self.logger.info("Closing open SPOT target coin position.")
            time.sleep(1)
            self.update_balance()
            order = self.sell_all(self.manager.cancel_order)
            self.make_report(order)
