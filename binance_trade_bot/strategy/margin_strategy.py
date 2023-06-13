import time
import typing as t
from decimal import Decimal

from binance_trade_bot.trader import Trader


class MarginTrader(Trader):
    def __str__(self):
        return "MARGIN"

    def calculate_total_profit(self):
        bridge_balance = self.portfolio.balance[self.global_strategy.bridge_coin]["free"]
        target_balance = self.portfolio.balance[self.global_strategy.target_coin]["free"]
        borrowed_balance = self.portfolio.balance[self.global_strategy.target_coin]["borrowed"]
        difference = (bridge_balance + (target_balance * self.minute_candle_price) -
                      (borrowed_balance * self.minute_candle_price)) - self.portfolio.start_balance
        return difference

    def update_current_portfolio_price(self):
        """
        Calculate new price of portfolio and update current_portfolio_price
        """
        self.portfolio.current_portfolio_price = (
                (self.portfolio.balance[self.global_strategy.target_coin]["free"] * self.minute_candle_price) +
                self.portfolio.balance[self.global_strategy.bridge_coin]["free"] -
                (self.portfolio.balance[self.global_strategy.target_coin]["borrowed"] * self.minute_candle_price)
        )

    def set_strategy(self):
        """
        Set strategy params if self.current_strategy is None.
        :return:
        """
        borrowed_coin = self.portfolio.balance[self.global_strategy.target_coin]["borrowed"]
        target_coin = self.portfolio.balance[self.global_strategy.target_coin]["free"]
        bridge_coin = self.portfolio.balance[self.global_strategy.bridge_coin]["free"]
        if target_coin < self.lot_size and borrowed_coin == 0:
            self.current_strategy = "INITIAL"
        else:
            borrowed_price = borrowed_coin * self.minute_candle_price
            if target_coin < self.lot_size and borrowed_price > self.min_notional:
                self.portfolio.last_price = borrowed_price
                self.update_strategy()
            elif target_coin > 0 and borrowed_coin > 0:
                if target_coin < borrowed_coin:
                    quantity = target_coin
                else:
                    quantity = borrowed_coin
                self.manager.repay_loan(symbol=self.global_strategy.target_coin,
                                        quantity=quantity,
                                        lot_size=self.lot_size)
                self.update_balance()
                self._reboot_strategy()
                self.current_strategy = "INITIAL"
            else:
                self.current_strategy = "INITIAL"

        self.portfolio.start_balance = (bridge_coin + (target_coin * self.minute_candle_price) -
                                        (borrowed_coin * self.minute_candle_price))

    def update_stop_loss(self):
        """
        Update sell price for stop loosing money.
        """
        self.portfolio.stop_loss = self.minute_candle_price * self.config.MARGIN_STOP_LOSS

    def update_balance(self):
        """
        Update bridge and target coin amount after successful order.
        """
        bridge_coin = self.global_strategy.bridge_coin
        target_coin = self.global_strategy.target_coin
        self.portfolio.balance = self.manager.check_margin_balance(bridge_coin, target_coin)
        self.update_current_portfolio_price()

    def update_account_status(self):
        """
        Update prices and check trading status.
        """
        self.update_balance()

        bridge_coin = self.global_strategy.bridge_coin
        target_coin = self.global_strategy.target_coin
        target_borrowed = self.portfolio.balance[target_coin]["borrowed"]

        symbol_info = self.manager.get_symbol_info(self.global_strategy.bid_symbol)
        self.lot_size = Decimal(symbol_info["filters"][2]["stepSize"])
        self.min_notional = Decimal(symbol_info["filters"][3]["minNotional"])

        if self.portfolio.balance[bridge_coin]["free"] == 0 and target_borrowed == 0:
            self.logger.info("No cash on MARGIN balance. You need to put some money here.")
            return
        if self.portfolio.balance[target_coin]["free"] < self.lot_size and target_borrowed < self.min_notional:
            self.set_working_balance()
        elif target_borrowed >= self.min_notional:
            self.logger.info("Something isn't correct. We've already have MARGIN coins.")
        elif target_borrowed < 0:
            self.logger.info("Something goes wrong: MARGIN balance is less then zero.")
        else:
            self.logger.info("Something isn't normal. Check balance.")
            self.set_working_balance()

    def update_strategy(self):
        """
        Get new strategy symbol from generator and update target order.
        """
        self.current_strategy = next(self.strategy_generator)
        self.update_stop_loss()

    def use_strategy(self, data: dict, current_time: int):
        """
        Make a cell or buy decision based on current data.
        :param data: stream_data["kline"]
        :param current_time: stream_data["event_time"]
        """
        super().use_strategy(data, current_time)
        self.portfolio.profit = 0
        self.minute_candle_price = Decimal(data["open_price"])

        if self.current_strategy is None:
            self.set_strategy()
            self.make_report(order=self.default_order, initial=True)

        if self.current_strategy == "INITIAL":
            if self.portfolio.current_portfolio_price > self.config.MIN_PORTFOLIO_PRICE:
                if self.minute_candle_price > self.max_period_price:
                    if self.check_for_min_notional() is False:
                        self.logger.warning(f"We don't have enough money in MARGIN working balance. "
                                            f"Working balance is {self.portfolio.working_balance}")
                        return False
                    order = self.sell_all(self.manager.cancel_margin_order)
                    if order is None:
                        self.logger.info("Failed to loan coin.")
                        return self.default_order

                    self.update_balance()
                    self.update_strategy()
                    self.portfolio.last_price = Decimal(order["executedQty"]) * Decimal(order["fills"][0]["price"])
                    return order
            else:
                self.logger.info("You've got not enough money for MARGIN trade. You have only %s" %
                                 self.portfolio.current_portfolio_price)
                return self.default_order
        elif self.current_strategy in self.config.STRATEGY_DICT.keys():

            if self.portfolio.balance[self.global_strategy.target_coin]["borrowed"] < self.lot_size:
                self.logger.info("We have MARGIN strategy, but don't have borrowed coins. Rebooting strategy.")
                self._reboot_strategy()

                return self.default_order

            if (self.minute_candle_price >= self.portfolio.stop_loss or
                    self.minute_candle_price <= self.moving_average):
                order = self.buy(cancel_func=self.manager.cancel_margin_order,
                                 quantity=self.portfolio.balance[self.global_strategy.target_coin]["borrowed"])
                if order is None:
                    self.logger.info("Failed to repay loan.")
                    return self.default_order

                self.portfolio.profit = self.portfolio.last_price - (Decimal(order["executedQty"]) *
                                                                     Decimal(order["fills"][0]["price"]))
                self.portfolio.total_profit = self.calculate_total_profit()
                self._reboot_strategy()
                return order

        return self.default_order

    def buy(self, cancel_func, quantity: t.Union[Decimal, None] = None, margin: bool = True, *args, **kwarg):
        """
        Buy fixed quantity of coins, update current strategy and portfolio balance.
        """
        if self.portfolio.balance[self.global_strategy.target_coin]["free"] < self.lot_size:
            order = super().buy(self.manager.cancel_margin_order, quantity, margin)
            if order is None:
                return order
        else:
            order = self.default_order

        self.update_balance()
        if self.portfolio.balance[self.global_strategy.target_coin]["free"] < self.lot_size:
            time.sleep(1)
            self.logger.info("Margin target was less than lot size. Updating balance.")
            self.update_balance()
        target_coin = self.portfolio.balance[self.global_strategy.target_coin]["free"]
        borrowed_coin = self.portfolio.balance[self.global_strategy.target_coin]["borrowed"]
        if target_coin < borrowed_coin:
            loan_quantity = target_coin
        else:
            loan_quantity = borrowed_coin
        if loan_quantity > 0 and borrowed_coin > 0:
            repay = self.manager.repay_loan(symbol=self.global_strategy.target_coin,
                                            quantity=loan_quantity,
                                            lot_size=self.lot_size)
            time.sleep(1)
            self.update_balance()
            if repay is None and borrowed_coin > self.min_notional:
                count = 0
                while count < 10:
                    count += 1
                    self.logger.info("Repay is None. Trying to repay loan. Attempt %s/10" % count)
                    time.sleep(10)
                    repay = self.manager.repay_loan(symbol=self.global_strategy.target_coin,
                                                    quantity=loan_quantity,
                                                    lot_size=self.lot_size)
                    self.update_balance()
                    if repay is not None or borrowed_coin == 0:
                        break
                if repay is None and borrowed_coin > self.min_notional:
                    return None
            borrowed_coin = self.portfolio.balance[self.global_strategy.target_coin]["borrowed"]
            target_coin = self.portfolio.balance[self.global_strategy.target_coin]["free"]
            if (borrowed_coin > 0) and (target_coin >= borrowed_coin):
                repay = self.manager.repay_loan(symbol=self.global_strategy.target_coin,
                                                quantity=borrowed_coin,
                                                lot_size=self.lot_size)

        return order

    def sell_all(self, cancel_func, margin: bool = True, *args, **kwargs):
        """
        Sell all coins, and close trade.
        """
        borrowed_balance = self.portfolio.balance[self.global_strategy.target_coin]["borrowed"]
        loan_quantity = self.portfolio.working_balance / self.minute_candle_price
        loan = self.manager.get_loan(symbol=self.global_strategy.target_coin,
                                     quantity=loan_quantity,
                                     lot_size=self.lot_size)
        time.sleep(1)
        self.update_balance()
        if loan is None and self.portfolio.balance[self.global_strategy.target_coin]["borrowed"] == 0:
            count = 0
            while loan is None and count < 10:
                count += 1
                self.logger.info("Order is None. Trying to resell coin. Attempt %s/10" % count)
                time.sleep(1)
                loan = self.manager.sell(symbol=self.global_strategy.target_coin,
                                         quantity=loan_quantity,
                                         lot_size=self.lot_size)
                self.update_balance()
            if loan is None and borrowed_balance == 0:
                return None

        if self.portfolio.balance[self.global_strategy.target_coin]["free"] <= self.lot_size:
            return None
        order = super().sell_all(cancel_func, margin)
        self.update_balance()
        if (self.portfolio.balance[self.global_strategy.target_coin]["free"] *
           self.minute_candle_price) > self.min_notional:
            time.sleep(1)
            order = super().sell_all(cancel_func, margin)
        return order

    def close_trades(self):
        """
        Sell all target coins if they are.
        """
        borrowed_coin = self.portfolio.balance[self.global_strategy.target_coin]["borrowed"]
        if (Decimal(borrowed_coin) * self.minute_candle_price) >= self.min_notional:
            self.logger.info("Closing open MARGIN target coin position.")
            self.buy(self.manager.cancel_orde, borrowed_coin)
