import marshmallow
import marshmallow_dataclass

from .models import Kline, Report, Task


class KlineReportSchema(marshmallow.Schema):
    @marshmallow.post_dump
    def convert_to_int(self, out_data, **kwargs):
        for key, value in out_data.items():
            if type(value) is bool:
                out_data[key] = int(value)
        return out_data


# This Kline schema is used to serialize a Kline to and from a nested JSON object
KlineSchema = marshmallow_dataclass.class_schema(Kline, base_schema=KlineReportSchema)
ReportSchema = marshmallow_dataclass.class_schema(Report)
TaskSchema = marshmallow_dataclass.class_schema(Task)
