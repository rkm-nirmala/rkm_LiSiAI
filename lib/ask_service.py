import json
import os
import socket
from pathlib import Path
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROMPT_DIRECTORY = Path(__file__).resolve().parent.parent / "prompts"
TASK_PROMPTS = {
    "book_scan": "book_scan.txt",
    "sensor_analysis": "sensor_analysis.txt",
}
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "qwen2.5:3b"
DEFAULT_TIMEOUT_SECONDS = 120


class AskServiceError(Exception):
    def __init__(self, message, status_code=502):
        super().__init__(message)
        self.status_code = status_code


def _load_prompt(task):
    prompt_file = TASK_PROMPTS.get(task)
    if prompt_file is None:
        raise AskServiceError("Jenis analisis AI tidak dikenal.", status_code=400)

    try:
        prompt = (PROMPT_DIRECTORY / prompt_file).read_text(encoding="utf-8").strip()
    except OSError as error:
        raise AskServiceError(f"File prompt tidak dapat dibaca: {error}", status_code=500) from error

    if not prompt:
        raise AskServiceError("File prompt AI kosong.", status_code=500)
    return prompt


def _ollama_settings():
    base_url = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_URL).rstrip("/")
    model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL).strip()
    timeout_value = os.getenv("OLLAMA_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
    parsed_url = urlparse(base_url)

    if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
        raise AskServiceError(
            "OLLAMA_BASE_URL harus berupa URL HTTP atau HTTPS yang valid.",
            status_code=500,
        )
    if not model:
        raise AskServiceError("OLLAMA_MODEL tidak boleh kosong.", status_code=500)

    try:
        timeout = float(timeout_value)
    except ValueError as error:
        raise AskServiceError(
            "OLLAMA_TIMEOUT_SECONDS harus berupa angka positif.",
            status_code=500,
        ) from error
    if timeout <= 0:
        raise AskServiceError(
            "OLLAMA_TIMEOUT_SECONDS harus berupa angka positif.",
            status_code=500,
        )

    return base_url, model, timeout


def _read_ollama_error(error):
    detail = error.reason
    try:
        body = json.loads(error.read().decode("utf-8"))
        if isinstance(body, dict) and isinstance(body.get("error"), str):
            detail = body["error"]
    except (UnicodeDecodeError, json.JSONDecodeError):
        pass
    return str(detail)


def ask_ollama(task, data):
    system_prompt = _load_prompt(task)
    base_url, model, timeout = _ollama_settings()
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(data, ensure_ascii=False),
            },
        ],
        "options": {"temperature": 0.2},
    }
    request = Request(
        f"{base_url}/api/chat",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = _read_ollama_error(error)
        raise AskServiceError(
            f"Ollama menolak permintaan (HTTP {error.code}): {detail}",
            status_code=502,
        ) from error
    except (TimeoutError, socket.timeout) as error:
        raise AskServiceError(
            "Ollama terlalu lama merespons. Coba lagi atau kurangi beban model.",
            status_code=504,
        ) from error
    except URLError as error:
        if isinstance(error.reason, (TimeoutError, socket.timeout)):
            raise AskServiceError(
                "Ollama terlalu lama merespons. Coba lagi atau kurangi beban model.",
                status_code=504,
            ) from error
        raise AskServiceError(
            f"Tidak dapat terhubung ke Ollama lokal di {base_url}: {error.reason}",
            status_code=503,
        ) from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AskServiceError("Ollama mengirim respons yang tidak valid.", status_code=502) from error

    message = result.get("message") if isinstance(result, dict) else None
    answer = message.get("content") if isinstance(message, dict) else None
    if not isinstance(answer, str) or not answer.strip():
        raise AskServiceError("Ollama tidak mengembalikan jawaban teks.", status_code=502)

    return {"answer": answer.strip(), "model": model, "task": task}
