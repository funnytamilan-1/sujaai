"""Make the backend package importable when pytest is launched from any directory."""
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
backend_path = str(BACKEND_ROOT)
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)
