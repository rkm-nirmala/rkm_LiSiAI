import csv
import re
from difflib import SequenceMatcher
from pathlib import Path


DATABASE_PATH = Path(__file__).resolve().parent / "db.csv"
REQUIRED_COLUMNS = {"judul", "pengarang", "isbn", "sinopsis"}
OPTIONAL_COLUMNS = {"penerbit", "tahun"}
CONFIDENT_MATCH_THRESHOLD = 0.65


class BookCatalogError(Exception):
    pass


def _normalize(value):
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _extract_isbns(text):
    pattern = r"(?<![A-Z0-9])(?:97[89][ -]?)?[0-9X](?:[ -]?[0-9X]){9,12}(?![A-Z0-9])"
    return {
        re.sub(r"[^0-9X]", "", candidate.upper())
        for candidate in re.findall(pattern, text.upper())
    }


def _phrase_similarity(ocr_text, field_value):
    query_words = _normalize(ocr_text).split()
    field_words = _normalize(field_value).split()
    if not query_words or not field_words:
        return 0.0

    phrase = " ".join(field_words)
    query = " ".join(query_words)
    if phrase in query:
        return 1.0

    window_lengths = {
        length
        for length in (len(field_words) - 1, len(field_words), len(field_words) + 1)
        if length > 0
    }
    sequence_score = max(
        (
            SequenceMatcher(
                None,
                phrase,
                " ".join(query_words[start : start + length]),
            ).ratio()
            for length in window_lengths
            for start in range(max(1, len(query_words) - length + 1))
        ),
        default=0.0,
    )
    query_set = set(query_words)
    token_score = len(set(field_words) & query_set) / len(set(field_words))
    return max(sequence_score, token_score)


def _load_books():
    try:
        with DATABASE_PATH.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            columns = set(reader.fieldnames or ())
            missing = REQUIRED_COLUMNS - columns
            if missing:
                raise BookCatalogError(
                    "Kolom wajib pada data/db.csv belum lengkap: "
                    + ", ".join(sorted(missing))
                    + "."
                )

            books = []
            for row_number, row in enumerate(reader, start=2):
                book = {
                    column: (row.get(column) or "").strip()
                    for column in REQUIRED_COLUMNS | OPTIONAL_COLUMNS
                }
                if not any(book.values()):
                    continue
                if not book["judul"]:
                    raise BookCatalogError(
                        f"Kolom 'judul' wajib diisi pada baris {row_number} data/db.csv."
                    )
                books.append(book)
            return books
    except BookCatalogError:
        raise
    except (OSError, UnicodeError, csv.Error) as error:
        raise BookCatalogError(f"Database buku data/db.csv tidak dapat dibaca: {error}") from error


def find_best_book_match(extracted_text):
    books = _load_books()
    if not books:
        return {
            "status": "empty",
            "match_score": None,
            "book": None,
            "warning": "Database buku belum berisi data.",
        }

    scanned_isbns = _extract_isbns(extracted_text)
    candidates = []
    for book in books:
        database_isbn = re.sub(r"[^0-9X]", "", book["isbn"].upper())
        if database_isbn and database_isbn in scanned_isbns:
            score = 1.0
            reason = "isbn"
        else:
            title_score = _phrase_similarity(extracted_text, book["judul"])
            author_score = _phrase_similarity(extracted_text, book["pengarang"])
            score = 0.8 * title_score + 0.2 * author_score if book["pengarang"] else title_score
            reason = "title_author"
        candidates.append((score, book, reason))

    score, book, reason = max(candidates, key=lambda candidate: candidate[0])
    confident = reason == "isbn" or score >= CONFIDENT_MATCH_THRESHOLD
    return {
        "status": "matched" if confident else "candidate",
        "match_score": round(score * 100, 1),
        "match_reason": reason,
        "book": book,
        "warning": (
            None
            if confident
            else "Kecocokan belum meyakinkan; verifikasi judul dan pengarang dengan sampul."
        ),
    }
