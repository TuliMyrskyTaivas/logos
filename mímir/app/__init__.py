"""Mímir — gateway service to the Logos financial analytics database."""

from __future__ import annotations

import sys
from pathlib import Path

# The ORM models (`models.py`) and CRUD helpers (`crud.py`) live in the
# repository root. Add it to `sys.path` so `import models` / `import crud`
# resolve regardless of where the service is launched from.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
