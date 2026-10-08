"""Generate a local testing credential, never an OpenAI key. Does not print token."""

import hashlib
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
directory = root / "data"
directory.mkdir(exist_ok=True)
path = directory / "relay-token.txt"
if path.exists():
    raise SystemExit("Token lokal sudah ada. Skrip tidak menimpa token aktif.")
token = secrets.token_urlsafe(32)
path.write_text(token, encoding="utf-8")
(directory / "relay-token.sha256").write_text(hashlib.sha256(token.encode()).hexdigest(), encoding="utf-8")
print("Token dan SHA256 disimpan di data/relay-token.txt dan data/relay-token.sha256 (tidak masuk Git).")
