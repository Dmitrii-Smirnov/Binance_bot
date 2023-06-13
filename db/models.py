from dataclasses import dataclass
import typing as t
from decimal import Decimal


@dataclass(frozen=True, eq=True)
class Kline:
    event_time: int
    symbol: str
    base_volume: str
    close_price: str
    first_trade_id: bool
    high_price: str
    ignore: str
    interval: str
    is_closed: bool
    kline_close_time: int
    kline_start_time: int
    last_trade_id: bool
    low_price: str
    number_of_trades: int
    open_price: str
    quote: str
    symbol: str
    taker_by_base_asset_volume: str
    taker_by_quote_asset_volume: str


@dataclass(frozen=True, eq=True)
class Report:
    event_time: int
    market_place: str
    target_coin: str
    bridge_coin: str
    moving_average: t.Union[str, float, Decimal]
    minimum_price: t.Union[str, float, Decimal]
    max_price: t.Union[str, float, Decimal]
    stop_loss: t.Union[str, float, Decimal]
    bridge_balance: t.Union[str, float, Decimal]
    target_balance: t.Union[str, float, Decimal]
    current_strategy: str
    order_side: str
    order_quantity: t.Union[str, float, Decimal]
    order_price: t.Union[str, float, Decimal]
    candle_price: t.Union[str, float, Decimal]
    profit: t.Union[str, float, Decimal]
    bridge_balance_profit: t.Union[str, float, Decimal]

    # def __dict__(self):
    #     return {
    #         "event_time": self.event_time,
    #         "market_place": self.market_place,
    #         "target_coin": self.target_coin,
    #         "bridge_coin": self.bridge_coin,
    #         "moving_average": self.moving_average,
    #         "minimum_price": self.minimum_price,
    #         "max_price": self.max_price,
    #         "stop_loss": self.stop_loss,
    #         "bridge_balance": self.bridge_balance,
    #         "target_balance": self.target_balance,
    #         "current_strategy": self.current_strategy,
    #         "order_side": self.order_side,
    #         "order_quantity": self.order_quantity,
    #         "order_price": self.order_price,
    #         "candle_price": self.candle_price,
    #         "profit": self.profit,
    #         "bridge_balance_profit": self.bridge_balance,
    #     }


@dataclass(frozen=True, eq=True)
class Task:
    task: str
