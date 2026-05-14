import os
import tempfile

# Set DB_PATH before main.py is imported so the module-level constant picks it up.
_tmp_db_dir = tempfile.mkdtemp()
os.environ.setdefault("DB_PATH", os.path.join(_tmp_db_dir, "test.db"))
