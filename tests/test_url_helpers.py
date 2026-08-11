"""Tests for URL parsing helpers."""

import pytest

from confluence_md import page_id_from_url, space_key_from_url, _heading_slug


class TestPageIdFromUrl:
    def test_pretty_url(self):
        url = "https://org.atlassian.net/wiki/spaces/ENG/pages/123456789/My+Page"
        assert page_id_from_url(url) == "123456789"

    def test_pretty_url_without_title_suffix(self):
        url = "https://org.atlassian.net/wiki/spaces/ENG/pages/123456789"
        assert page_id_from_url(url) == "123456789"

    def test_query_string_url(self):
        url = "https://org.atlassian.net/wiki/pages/viewpage.action?pageId=987654321"
        assert page_id_from_url(url) == "987654321"

    def test_query_string_url_extra_params(self):
        url = "https://org.atlassian.net/wiki/x?foo=bar&pageId=42"
        assert page_id_from_url(url) == "42"

    def test_unrecognised_url_raises(self):
        with pytest.raises(ValueError):
            page_id_from_url("https://org.atlassian.net/wiki/spaces/ENG/overview")


class TestSpaceKeyFromUrl:
    def test_space_key(self):
        url = "https://org.atlassian.net/wiki/spaces/ENG/pages/123456789"
        assert space_key_from_url(url) == "ENG"

    def test_missing_space_raises(self):
        with pytest.raises(ValueError):
            space_key_from_url("https://org.atlassian.net/wiki/pages/123456789")


class TestHeadingSlug:
    def test_simple(self):
        assert _heading_slug("Getting Started") == "getting-started"

    def test_punctuation_stripped(self):
        assert _heading_slug("What's new?") == "whats-new"

    def test_whitespace_collapsed(self):
        assert _heading_slug("A   B\tC") == "a-b-c"
