"""Configure a fresh local install from the owner's public exam relay.

The public manifest contains only an HTTPS endpoint. The demo credential is
intentionally obtainable by anyone while installation access is enabled.
Existing user configuration is preserved; no OpenAI key is distributed.
"""

import argparse
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def configure(env_path=ROOT / ".env", manifest_path=ROOT / "config" / "relay.json"):
    env_path, manifest_path = Path(env_path), Path(manifest_path)
    values = dotenv_values(env_path) if env_path.exists() else {}
    relay_url = os.getenv("SIRA_RELAY_URL") or values.get("SIRA_RELAY_URL")
    relay_token = os.getenv("SIRA_RELAY_TOKEN") or values.get("SIRA_RELAY_TOKEN")
    if relay_url and relay_token:
        return {"configured": False, "existing": True}
    if relay_url or relay_token:
        raise ValueError("Konfigurasi relay terisi sebagian. Lengkapi URL/token Anda; setup tidak menimpanya.")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        endpoint = manifest["installation_url"]
        url = urlparse(endpoint)
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.path != "/installation"
        ):
            raise ValueError
        with httpx.Client(timeout=httpx.Timeout(20, connect=10), follow_redirects=False) as client:
            response = client.get(endpoint, headers={"Accept": "application/json"})
        if response.status_code != 200 or len(response.content) > 16000:
            raise ValueError
        packet = response.json()
        origin = f"{url.scheme}://{url.netloc}"
        if packet.get("relay_url") != origin or packet.get("access") != "public-demo":
            raise ValueError
        token = packet.get("relay_token")
        if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{40,100}", token):
            raise ValueError
        expiry = datetime.fromisoformat(packet["expires_at"].replace("Z", "+00:00"))
        if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
            raise ValueError
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
        raise ValueError(
            "Koneksi otomatis ke Cloudflare belum berhasil. Periksa internet atau masa akses pengujian, "
            "lalu jalankan kembali python -m backend.setup_relay. Aplikasi belum siap memakai AI."
        ) from exc

    content = env_path.read_text(encoding="utf-8-sig") if env_path.exists() else ""
    for key, value in [("SIRA_RELAY_URL", origin), ("SIRA_RELAY_TOKEN", token)]:
        line = f"{key}={value}"
        pattern = re.compile(rf"^(?:export\s+)?{key}\s*=.*$", re.M)
        if pattern.search(content):
            content = pattern.sub(line, content)
        else:
            content = content.rstrip("\r\n") + "\n" + line + "\n"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    # Publish both fields atomically. Never leave a partially configured .env.
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=env_path.parent, prefix=".env.bootstrap-", delete=False
        ) as stream:
            temp_path = Path(stream.name)
            stream.write(content)
        os.replace(temp_path, env_path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return {"configured": True, "existing": False, "relay_url": origin, "expires_at": packet["expires_at"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--manifest", type=Path, default=ROOT / "config" / "relay.json")
    args = parser.parse_args()
    try:
        result = configure(args.env_file, args.manifest)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    if result["existing"]:
        print("Konfigurasi AI yang sudah ada dipertahankan.")
    else:
        print("Cloudflare terhubung otomatis. Tidak perlu API key OpenAI atau token manual.")
        print("Masa akses AI pengujian (UTC):", result["expires_at"])


if __name__ == "__main__":
    main()
