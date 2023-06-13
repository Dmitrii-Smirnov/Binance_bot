from pprint import pprint as pp
from db.connections import RedisConnection
from db.schema import KlineSchema, ReportSchema
import pandas as pd


def load_to_csv(symbol, data, data_type, schema):
    for element in data:
        if data_type == "kline":
            hash_key = redis.key_schema.kline_hash(symbol, int(element))
        else:
            hash_key = redis.key_schema.report_hash(symbol, int(element))
        hash_dict = redis.redis_client.hgetall(hash_key)
        if len(hash_dict) > 0:
            hash_dict = {key.decode("utf-8"): value.decode("utf-8") for key, value in hash_dict.items()}
            pp(hash_dict)
            kline_data = schema().load(hash_dict)
            report_df = pd.DataFrame(kline_data.__dict__, index=[0])
            with open(f"{data_type}_{symbol}_data.csv", "a") as f:
                report_df.to_csv(f, header=f.tell() == 0)


redis = RedisConnection(host="127.0.0.1", port=6379)
spot_symbol = redis.redis_client.get("SPOT").decode("utf-8")
margin_symbol = redis.redis_client.get("MARGIN").decode("utf-8")

spot_set_kline_key = redis.key_schema.kline_set(spot_symbol)
margin_set_kline_key = redis.key_schema.kline_set(margin_symbol)

spot_set_order_key = redis.key_schema.report_set(spot_symbol)
margin_set_order_key = redis.key_schema.report_set(margin_symbol)

pipeline = redis.redis_client.pipeline()
pipeline.zrange(spot_set_kline_key, 0, -1)
pipeline.zrange(margin_set_kline_key, 0, -1)
pipeline.zrange(spot_set_order_key, 0, -1)
pipeline.zrange(margin_set_order_key, 0, -1)

spot_kline, margin_kline, spot_order, margin_order = pipeline.execute()

load_to_csv(symbol=spot_symbol, data=spot_kline, data_type="kline", schema=KlineSchema)
load_to_csv(symbol=spot_symbol, data=spot_order, data_type="order", schema=ReportSchema)
load_to_csv(symbol=margin_symbol, data=margin_kline, data_type="kline", schema=KlineSchema)
load_to_csv(symbol=margin_symbol, data=margin_order, data_type="order", schema=ReportSchema)
