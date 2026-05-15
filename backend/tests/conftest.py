import os
import tempfile

import pytest

_tests_dir = os.path.dirname(__file__)
_backend_dir = os.path.dirname(_tests_dir)
_project_root = os.path.dirname(_backend_dir)

# Set before main.py is imported so module-level constants pick these up.
os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "test.db"))
os.environ.setdefault("CATALOG_PATH", os.path.join(_project_root, "catalog.json"))
os.environ.setdefault("TEMPLATES_DIR", os.path.join(_project_root, "templates"))


@pytest.fixture(autouse=True)
def fresh_db():
    """Re-create the database before every test so each test starts with a clean slate."""
    from main import init_db
    init_db()
