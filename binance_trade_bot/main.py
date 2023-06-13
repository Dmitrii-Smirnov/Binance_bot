from binance_trade_bot.binance_stream_manager import BinanceConnectionManager
from binance_trade_bot.binance_api_manager import BinanceAPIManager
from binance_trade_bot.trader import Trader, GlobalStrategy
from binance_trade_bot.strategy.margin_strategy import MarginTrader
from binance_trade_bot.strategy.spot_strategy import SpotTrader
from binance_trade_bot.config import Config
from binance_trade_bot.logger import Logger
from db.connections import RedisConnection


def get_spot_or_margin_strategy(market_place):
    """
    Take name of market as a key and return value: trader and APIManager instances for trading.
    :param market_place: SPOT or MARGIN. Defines in config.
    :return: tuple(Trader Instance, APIManager Instance).
    """
    dict_of_strategy = {
        "SPOT":  Trader,
        "MARGIN":  MarginTrader
    }
    return dict_of_strategy[market_place]


def main():
    logger = Logger()

    logger.info("Starting.")
    config = Config()

    db = RedisConnection()
    global_spot_strategy = GlobalStrategy(config.BRIDGE_SPOT_SYMBOL, config.TARGET_SPOT_SYMBOL)
    global_margin_strategy = GlobalStrategy(config.BRIDGE_MARGIN_SYMBOL, config.TARGET_MARGIN_SYMBOL)

    manager = BinanceAPIManager(config, logger)

    try:
        _ = manager.get_account()
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Couldn't access Binance API - API keys may be wrong or lack sufficient permissions")
        logger.error(e)
        return
    
    db.redis_client.set("strategy", config.MARKET_PLACE)
    
    if config.MARKET_PLACE == "SPOT-MARGIN":
        db.redis_client.set("MARGIN", global_margin_strategy.bid_symbol)
        db.redis_client.set("SPOT", global_spot_strategy.bid_symbol)
        margin_trader = MarginTrader(manager, db, global_margin_strategy, config, logger)
        spot_trader = SpotTrader(manager, db, global_spot_strategy, config, logger)
        connection_manager = BinanceConnectionManager(config=config, api_manager=manager, logger=logger, trader=None,
                                                      spot_trader=spot_trader, margin_trader=margin_trader, both=True,
                                                      db=db)
    else:
        if config.MARKET_PLACE == "SPOT":
            global_strategy = global_spot_strategy
        else:
            global_strategy = global_margin_strategy
        db.redis_client.set(config.MARKET_PLACE, global_strategy.bid_symbol)
        trader_shell = get_spot_or_margin_strategy(config.MARKET_PLACE)
        trader = trader_shell(manager, db, global_strategy, config, logger)
        connection_manager = BinanceConnectionManager(config=config, api_manager=manager,
                                                      logger=logger, trader=trader, db=db)
    connection_manager.initialization()
