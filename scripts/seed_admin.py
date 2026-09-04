"""Create the bootstrap admin user (idempotent).

Run:  python -m scripts.seed_admin
Optional demo seed: python -m scripts.seed_admin --demo
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))

from memes_shared.config import get_settings  # noqa: E402
from memes_shared.db.session import get_session  # noqa: E402
from memes_shared.logging_setup import setup_logging  # noqa: E402
from memes_shared.models import AdminUser  # noqa: E402
from memes_shared.security import hash_password  # noqa: E402
from memes_shared.services.settings import ensure_default_settings  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="seed demo data")
    args = parser.parse_args()

    setup_logging()
    cfg = get_settings()
    with get_session() as s:
        existing = s.query(AdminUser).filter_by(email=cfg.admin_email).first()
        if not existing:
            s.add(
                AdminUser(
                    email=cfg.admin_email,
                    password_hash=hash_password(cfg.admin_password),
                    full_name="Owner",
                    role="owner",
                )
            )
            print(f"✔ admin created: {cfg.admin_email}")
        else:
            print(f"• admin already exists: {cfg.admin_email}")
        ensure_default_settings(s)

    if args.demo:
        from scripts.demo_data import seed_demo

        seed_demo()
        print("✔ demo data seeded")


if __name__ == "__main__":
    main()
