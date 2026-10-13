from dataclasses import asdict, dataclass

from data.book_catalog import find_best_book_match

MAX_EXTRACTED_TEXT_LENGTH = 12_000


class BookScanDataError(ValueError):
    pass


@dataclass(frozen=True)
class BookScanData:
    extracted_text: str
    catalog_match: dict

    def to_dict(self):
        return asdict(self)


def build_book_scan_data(extracted_text):
    if not isinstance(extracted_text, str) or not extracted_text.strip():
        raise BookScanDataError("Field 'extracted_text' wajib diisi dengan teks hasil scan.")

    extracted_text = extracted_text.strip()
    if len(extracted_text) > MAX_EXTRACTED_TEXT_LENGTH:
        raise BookScanDataError(
            f"Teks hasil scan terlalu panjang; batasnya {MAX_EXTRACTED_TEXT_LENGTH} karakter."
        )

    return BookScanData(
        extracted_text=extracted_text,
        catalog_match=find_best_book_match(extracted_text),
    ).to_dict()
