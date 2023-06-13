# BINANCE TRADE BOT.
## About project.
Trade bot for trading on SPOT and MARGIN market places of Binance.com. 
## Structure and configs.
All secret configs with API eys and secret API keys defines in usr.cfg in root folder. You can see an example in .user.cfg.example.
All docker files, requirements files and backtest starter are also in root folder. In `/config` folder is configs for apprise notifications.
You can see an example for config file in `/configs/apprise_example.yml`.

Base configs are in /binance_trade_bot/config.py. They based on `user.cfg` file wich include all sensitive settings like api key, secret key, 
SPOT and MARGIN assets for arget and margin coin and so on.

### Some instructions for configs.
`TIME_INTERVAL` - time interval for binance historical data. It's a historical step size for time period. Could be hour, days, month etc.

`KLINE_TIMEFRAME` - interval for stream data. Meaans what period of data update.

`KLINE_INTERVAL` - Time step size to summarize data. You can find the right value in binance.enum module.

`UNIX_TIME_INTERVAL` - 1 hour in unix format by default. Pay attention that this parametr is using for checkin period candle price. So, if yo want 
to change interval for period candles, you need to change this parametr too. For example, if you want get new period candle every 30 minutes, you 
need to divid by two this parametr. And so on.

`MARKET_PLACE` - In which place you would trade. Can be SPOT or MARGIN.

`SMA_PERIOD` - Time period for simple moving average.

`WORKING_BALANCE` - Which part of your bridge coin balance bot takes for trading operation. It's a coefficient. Couldn't be more than 1.00.

`STRATEGY_DICT` - In original, it's a dict with 2 value tuple. First value is some target prie for coin. We do some trades When minute candle price get to the strategy pri. Second value is about how much of our balance we going to sell/buy. Although in fact I use it as same marker in bot. Like 'Hey, we did, what we wanted to do to start our trade algorithm. Now we are on a second step of our cycle.'

`HISTORY_PERIOD_FOR_BACKTEST` - How far from past we would take data for backtest.

### Back to structure.
All project is in `/binance_trade_bot`. In `/binance_trade_bot/strategy/` is business logic for trade algorithm. `Binance_stream_manager.py` is about 
websocket connection to binance API. `Binance_api_manager.py` is about connection to binance API endpoints. `trder.py` - base business logic for trade algorithm
such as statistic request, data updating etc. `logger.py` and `notifications.py` is logs settings and configs for logs notifications in social networks.

All logs are saving in `/logs` folder.

## How it works.
Bot takes minute candle price info from websocket stream and compares it with historical candle information. First of all, he looks at min and max price for the period and a moving average. By default, period information updates evry hour.

## Start up.
First of all you need to configure a `user.cfg` file, couse it's core config file. You can find the example of how it shoul looks like in `user.cfg.example`. 

1. ### Start backtest.

    For startup backest you have to install requirements. I used TA-Lib and it's could be problematic to install. That's why I'm Using python 3.6.
    For installing I used conda virtual enviroment and 
    ```conda install -c conda-forge ta-lib ``` 
    command to install TA-Lib in conda virtualenv. 
    Than use. 
    ```
    pip install -r requirements.txt
    ```
  
    For running backtest use:
    ```
    python backtest.py
    ```

2. ### Start algorithm.
    ```
    docker-compose  up -d --build
    ```
