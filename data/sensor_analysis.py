from dataclasses import asdict, dataclass


class SensorAnalysisDataError(ValueError):
    pass


@dataclass(frozen=True)
class SensorAnalysisData:
    latest_reading: dict | None

    def to_dict(self):
        return asdict(self)


def build_sensor_analysis_data(latest_reading):
    if latest_reading is not None and not isinstance(latest_reading, dict):
        raise SensorAnalysisDataError("Field 'latest_reading' harus berupa JSON object atau null.")

    return SensorAnalysisData(latest_reading=latest_reading).to_dict()
