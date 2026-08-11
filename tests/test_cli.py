"""Tests for command-line interface behaviour."""

import pytest

import confluence_md


def test_version_flag_prints_version(capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["confluence_md.py", "--version"])
    with pytest.raises(SystemExit) as exc:
        confluence_md.main()
    assert exc.value.code == 0
    assert confluence_md.__version__ in capsys.readouterr().out


def test_version_is_semver():
    assert len(confluence_md.__version__.split(".")) == 3
