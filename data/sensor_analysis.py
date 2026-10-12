from dataclasses import asdict, dataclass


MAX_QUESTION_LENGTH = 2_000


class SensorAnalysisDataError(ValueError):
    pass


@dataclass(frozen=True)
class SensorAnalysisData:
    question: str
    latest_reading: dict | None

    def to_dict(self):
        return asdict(self)


def build_sensor_analysis_data(question, latest_reading):
    if not isinstance(question, str) or not question.strip():
        raise SensorAnalysisDataError("Field 'question' wajib diisi dengan pertanyaan.")

    question = question.strip()
    if len(question) > MAX_QUESTION_LENGTH:
        raise SensorAnalysisDataError(
            f"Pertanyaan terlalu panjang; batasnya {MAX_QUESTION_LENGTH} karakter."
        )
    if latest_reading is not None and not isinstance(latest_reading, dict):
        raise SensorAnalysisDataError("Field 'latest_reading' harus berupa JSON object atau null.")

    return SensorAnalysisData(question=question, latest_reading=latest_reading).to_dict()
