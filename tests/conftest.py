"""
conftest.py — añade la raíz del proyecto al sys.path para que pytest
encuentre app.py, rag_engine.py y route_engine.py independientemente
de desde dónde se ejecute pytest.
"""
import sys
from pathlib import Path

# Sube un nivel desde tests/ hasta la raíz del proyecto
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
