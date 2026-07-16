"""Shared Insyte API credential loader — reads INSYTE_EMAIL / INSYTE_KEY from
the environment, falling back to a local .env file (not committed to git).
See .env.example for the expected format."""
import os

def _load_dotenv():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

_load_dotenv()

EMAIL = os.environ.get("INSYTE_EMAIL", "")
KEY = os.environ.get("INSYTE_KEY", "")

if not EMAIL or not KEY:
    raise RuntimeError(
        "INSYTE_EMAIL / INSYTE_KEY not set. Copy .env.example to .env and fill in your credentials."
    )
