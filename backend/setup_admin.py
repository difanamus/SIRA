"""Run from repository root: python -m backend.setup_admin."""

import argparse
import getpass
import secrets

from backend.app.config import Settings
from backend.app.db import Database
from backend.app.security import hasher


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true", help="Buat password acak dan simpan hanya di data lokal.")
    parser.add_argument(
        "--reset", action="store_true", help="Ganti password secara interaktif dan cabut semua sesi admin."
    )
    args = parser.parse_args()
    settings = Settings()
    db = Database(settings.data_dir)
    if db.one("SELECT id FROM admin"):
        if not args.reset:
            print("Akun sudah ada. Gunakan --reset untuk mengganti password secara interaktif.")
            return
    username = "admin" if args.generate else input("Nama admin [admin]: ").strip() or "admin"
    password = secrets.token_urlsafe(18) if args.generate else getpass.getpass("Password (minimal 12 karakter): ")
    if len(password) < 12 or (not args.generate and password != getpass.getpass("Ulangi password: ")):
        raise SystemExit("Password terlalu pendek atau konfirmasi berbeda.")
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO admin VALUES (1,?,?) ON CONFLICT(id) DO UPDATE SET username=excluded.username,password_hash=excluded.password_hash",
            (username, hasher.hash(password)),
        )
        conn.execute("DELETE FROM admin_sessions")
    credentials = settings.data_dir / "admin-initial-password.txt"
    if args.generate:
        credentials.write_text(
            "Username: "
            + username
            + "\nPassword: "
            + password
            + "\n\nFile lokal ini tidak masuk Git. Hapus setelah dicatat; gunakan --reset untuk mengganti password.\n",
            encoding="utf-8",
        )
        print("Password acak disimpan di:", credentials)
    elif args.reset:
        credentials.unlink(missing_ok=True)
    print("Akun admin dibuat. Jalankan aplikasi melalui start.ps1.")


if __name__ == "__main__":
    main()
