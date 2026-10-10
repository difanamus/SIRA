import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
os.environ.setdefault("TIKTOKEN_CACHE_DIR", str((ROOT / os.getenv("SIRA_DATA_DIR", "data") / "tokenizer").resolve()))


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("SIRA_DATA_DIR", "data")))
    relay_url: str = field(default_factory=lambda: os.getenv("SIRA_RELAY_URL", "").rstrip("/"))
    relay_token: str = field(default_factory=lambda: os.getenv("SIRA_RELAY_TOKEN", ""))
    origin: str = field(default_factory=lambda: os.getenv("SIRA_ORIGIN", "http://127.0.0.1:8000"))
    secure_cookie: bool = field(default_factory=lambda: os.getenv("SIRA_SECURE_COOKIE", "false").lower() == "true")
    tesseract_cmd: str = field(
        default_factory=lambda: (
            os.getenv("SIRA_TESSERACT_CMD", "")
            or (
                str(ROOT / "tools" / "tesseract" / "tesseract.exe")
                if (ROOT / "tools" / "tesseract" / "tesseract.exe").exists()
                else ""
            )
        )
    )
    ocr_lang: str = field(default_factory=lambda: os.getenv("SIRA_OCR_LANG", "ind+eng"))
    max_pages: int = field(default_factory=lambda: int(os.getenv("SIRA_MAX_PAGES", "300")))
    vision_enabled: bool = field(default_factory=lambda: os.getenv("SIRA_VISION_ENABLED", "true").lower() == "true")
    ocr_workers: int = field(default_factory=lambda: int(os.getenv("SIRA_OCR_WORKERS", "3")))
    # Load the bundled sample knowledge base once on a fresh installation.
    seed_enabled: bool = field(default_factory=lambda: os.getenv("SIRA_SEED_KB", "true").lower() == "true")
    max_upload: int = 100 * 1024 * 1024
    session_cache_ttl: int = 1800

    def __post_init__(self):
        self.data_dir = (ROOT / self.data_dir).resolve()
        if self.relay_url:
            url = urlparse(self.relay_url)
            if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
                raise ValueError("SIRA_RELAY_URL harus berupa URL HTTPS tanpa kredensial/query.")
        if not 1 <= self.max_pages <= 1000:
            raise ValueError("SIRA_MAX_PAGES harus antara 1 dan 1000.")
        if not 1 <= self.ocr_workers <= 6:
            raise ValueError("SIRA_OCR_WORKERS harus antara 1 dan 6.")

    @property
    def ai_ready(self):
        return bool(self.relay_url and self.relay_token)
