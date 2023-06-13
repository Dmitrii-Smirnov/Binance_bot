import time
from collections import defaultdict
from datetime import datetime
import pandas as pd

from binance_trade_bot.config import Config
from binance_trade_bot.logger import Logger
from binance_trade_bot.backtest import MockAPIManager, MockMarginAPIManager
from binance_trade_bot.trader import GlobalStrategy
from binance_trade_bot.strategy.margin_strategy import MarginTrader
from binance_trade_bot.strategy.spot_strategy import SpotTrader
from binance_trade_bot.strategy.new_max_min_strategy import NewMinMaxMarginTrader


STRATEGY_FOR_BACKTEST = {
    "SPOT": (MockAPIManager, SpotTrader),
    "MARGIN": (MockMarginAPIManager, MarginTrader)
}


def backtest():
    start = time.time()
    config = Config()
    logger = Logger("backtesting", enable_notifications=False)
    if config.MARKET_PLACE == "SPOT":
        bridge_coin = config.BRIDGE_SPOT_SYMBOL
        target_coin = config.TARGET_SPOT_SYMBOL
    else:
        bridge_coin = config.BRIDGE_MARGIN_SYMBOL
        target_coin = config.TARGET_MARGIN_SYMBOL

    config.BACKTEST_PERIOD_CANDLE_DATA_PATH.format(target_symbol=target_coin, bridge_symbol=bridge_coin)
    config.BACKTEST_MINUTE_CANDLE_DATA_PATH.format(target_symbol=target_coin, bridge_symbol=bridge_coin)
    config.BACKTEST_REPORT_DATA_PATH.format(target_symbol=target_coin, bridge_symbol=bridge_coin)

    global_strategy = GlobalStrategy(bridge_coin=bridge_coin, target_coin=target_coin)
    manager, mock_trader = STRATEGY_FOR_BACKTEST[config.MARKET_PLACE]
    mock_manager = manager(config, logger, global_strategy, history_period=config.HISTORY_PERIOD_FOR_BACKTEST)
    trader = mock_trader(mock_manager, None, global_strategy, config, logger)
    trader.initialization()

    current_time = mock_manager.get_server_time()["serverTime"]
    candle_time = 0

    try:
        while candle_time < current_time:
            report_dict = defaultdict(list)
            data = mock_manager.get_last_minute_candle()
            candle_time = data["kline_start_time"]

            report_dict["date"].append(
                datetime.utcfromtimestamp(data["kline_start_time"] / 1000).strftime(config.TIME_FORMAT)
            )
            report_dict["symbol"].append(trader.global_strategy.bid_symbol)
            report_dict["minute_price"].append(data["open_price"])
            report_dict["period_max_price"].append(trader.max_period_price)
            report_dict["period_min_price"].append(trader.min_period_price)
            report_dict["moving_average"].append(trader.moving_average)
            report_dict["target_price"].append(trader.portfolio.target_order[0])
            report_dict["target_amount"].append(trader.portfolio.target_order[1])
            report_dict["stop_loss"].append(trader.portfolio.stop_loss)

            trader.check_for_hour_kline_update(candle_time)
            order = trader.use_strategy(data, candle_time)
            for key, value in order.items():
                if key == "fills":
                    for k, v in value[0].items():
                        report_dict[k].append(v)
                else:
                    report_dict[key].append(value)
            report_dict["bridge_coin"].append(mock_manager.BACKTEST_BRIDGE_BALANCE)
            report_dict["target_coin"].append(mock_manager.BACKTEST_TARGET_BALANCE)
            report_dict["portfolio_balance"].append(mock_manager.BACKTEST_PORTFOLIO_PRICE)
            trader.make_report(order)

            report_df = pd.DataFrame(report_dict)
            with open(config.BACKTEST_REPORT_DATA_PATH.format(target_symbol=global_strategy.target_coin,
                                                              bridge_symbol=global_strategy.bridge_coin), "a") as f:
                report_df.to_csv(f, header=f.tell() == 0)

            del report_dict, report_df

    except KeyboardInterrupt:
        pass
    except StopIteration:
        pass
    finally:
        print("Our balance:")
        print("Target coin: %s" % trader.portfolio.balance[trader.global_strategy.target_coin]["free"])
        print("Bridge coin: %s" % trader.portfolio.balance[trader.global_strategy.bridge_coin]["free"])
        print("Test time: %s сек." % (time.time() - start))


if __name__ == "__main__":
    backtest()
