from operator import itemgetter
from .spot_strategy import SpotTrader
from .margin_strategy import MarginTrader


class NewMinMaxMarginTrader(SpotTrader):
    def update_max_and_min_period_price(self):
        self.max_period_price = max(self.period_candle_price, key=itemgetter(3))[3]
        self.min_period_price = min(self.period_candle_price, key=itemgetter(2))[2]
