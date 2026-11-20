"""Root-level Vercel entrypoint for the SUJAAI FastAPI backend.

Supports deployments whose Vercel Root Directory is the repository root.
The backend project can continue using backend/api/index.py unchanged.
"""
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402

