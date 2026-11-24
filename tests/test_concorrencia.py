"""Concorrência (versão leve do scripts/carga.py): colaboradores apontando ao mesmo tempo, nada perdido."""

import importlib.util
from pathlib import Path

from tests.test_web import server  # noqa: F401 (fixture do servidor)

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "carga.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("carga", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_concurrent_entries_are_all_saved(server, db):  # noqa: F811
    carga = _load_script()
    result = carga.run_load(server, users=5, entries=3, db_path=db.path)
    assert result.stats.failures == []
    assert result.confirmed == 15
    assert (result.saved, result.duplicates, result.users_with_wrong_count) == (15, 0, 0)
    assert result.ok
