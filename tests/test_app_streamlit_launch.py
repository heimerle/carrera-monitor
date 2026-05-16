"""Regression test for the Streamlit launch import path.

When Streamlit runs ``streamlit run src/app.py`` it prepends the *script's
parent directory* (``src/``) to ``sys.path`` instead of the project root,
which previously broke ``from src import dashboard`` at first page run.
The fix in ``src/app.py`` prepends the project root before any first-party
import. This test simulates Streamlit's sys.path layout and asserts the
file is importable end-to-end.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


@pytest.fixture
def streamlit_like_sys_path(monkeypatch: pytest.MonkeyPatch) -> Path:
    """Mimic ``streamlit run src/app.py`` by isolating ``src/`` on ``sys.path``.

    Removes the project root, drops any cached ``src`` or ``src.app`` modules,
    and prepends only ``src/`` — the layout Streamlit actually creates.
    """
    repo_root = Path(__file__).resolve().parent.parent
    src_dir = repo_root / "src"

    monkeypatch.syspath_prepend(str(src_dir))
    # Remove repo root entries so the fix in src/app.py is the *only* reason
    # ``src`` resolves.
    new_path = [p for p in sys.path if Path(p).resolve() != repo_root]
    monkeypatch.setattr(sys, "path", new_path)

    # Snapshot + restore the affected sys.modules entries so we don't pollute
    # other tests that import the project ``src`` package.
    for mod in ("src", "src.app", "app"):
        monkeypatch.delitem(sys.modules, mod, raising=False)

    return src_dir


def test_app_module_recovers_src_import(
    streamlit_like_sys_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Importing ``src/app.py`` under Streamlit's sys.path must repair itself.

    We avoid running the Streamlit navigation by stubbing ``streamlit`` with a
    minimal fake before import. The relevant assertion is that the sys.path
    fix block at module top runs and makes ``from src import dashboard``
    succeed.
    """
    import types

    fake_st = types.SimpleNamespace(
        navigation=lambda pages: types.SimpleNamespace(run=lambda: None),
        Page=lambda *a, **kw: None,
    )
    monkeypatch.setitem(sys.modules, "streamlit", fake_st)

    spec = importlib.util.spec_from_file_location(
        "app_under_test", streamlit_like_sys_path / "app.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # must not raise ModuleNotFoundError

    # After the module ran, ``src`` must be importable (the fix put repo root
    # on sys.path).
    src_pkg = importlib.import_module("src")
    assert hasattr(src_pkg, "__path__")
