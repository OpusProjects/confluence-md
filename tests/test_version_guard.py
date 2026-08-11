"""Tests for the concurrent-edit version guard."""

import argparse

import pytest

import confluence_md
from confluence_md import parse_version_marker

PAGE_URL = "https://org.atlassian.net/wiki/spaces/ENG/pages/123"


class TestParseVersionMarker:
    def test_marker_extracted_and_stripped(self):
        text, page_id, version = parse_version_marker(
            "<!-- confluence-md page_id=123 version=7 -->\n# Title\n\nbody"
        )
        assert (page_id, version) == ("123", 7)
        assert text == "# Title\n\nbody"

    def test_no_marker(self):
        text, page_id, version = parse_version_marker("# Title\n\nbody")
        assert (page_id, version) == (None, None)
        assert text == "# Title\n\nbody"

    def test_marker_with_extra_whitespace(self):
        text, page_id, version = parse_version_marker(
            "\n<!--  confluence-md  page_id=9  version=2  -->\n# T"
        )
        assert (page_id, version) == ("9", 2)
        assert text == "# T"


class FakeClient:
    """Minimal stand-in for the Confluence client used by cmd_edit."""

    def __init__(self, remote_version: int):
        self.remote_version = remote_version
        self.updated = False

    def get_page_by_id(self, page_id, expand=None):
        return {
            "id": "123",
            "title": "T",
            "space": {"key": "ENG"},
            "version": {"number": self.remote_version},
        }

    def update_page(self, **kwargs):
        self.updated = True


def _edit_args(md_file, force=False):
    return argparse.Namespace(file=str(md_file), page_url=PAGE_URL, title=None, force=force)


@pytest.fixture
def md_file(tmp_path):
    path = tmp_path / "page.md"
    path.write_text(
        "<!-- confluence-md page_id=123 version=3 -->\n# T\n\nbody",
        encoding="utf-8",
    )
    return path


def test_edit_aborts_on_version_conflict(md_file, monkeypatch, capsys):
    client = FakeClient(remote_version=5)
    monkeypatch.setattr(confluence_md, "get_client", lambda: client)

    with pytest.raises(SystemExit) as exc:
        confluence_md.cmd_edit(_edit_args(md_file))

    assert exc.value.code == 1
    assert "version 3 -> 5" in capsys.readouterr().out
    assert not client.updated


def test_edit_force_overrides_conflict(md_file, monkeypatch):
    client = FakeClient(remote_version=5)
    monkeypatch.setattr(confluence_md, "get_client", lambda: client)

    confluence_md.cmd_edit(_edit_args(md_file, force=True))
    assert client.updated


def test_edit_proceeds_when_versions_match(md_file, monkeypatch):
    client = FakeClient(remote_version=3)
    monkeypatch.setattr(confluence_md, "get_client", lambda: client)

    confluence_md.cmd_edit(_edit_args(md_file))
    assert client.updated


def test_edit_without_marker_skips_guard(tmp_path, monkeypatch):
    path = tmp_path / "page.md"
    path.write_text("# T\n\nbody", encoding="utf-8")
    client = FakeClient(remote_version=99)
    monkeypatch.setattr(confluence_md, "get_client", lambda: client)

    confluence_md.cmd_edit(_edit_args(path))
    assert client.updated
