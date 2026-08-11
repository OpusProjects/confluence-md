"""Tests for image conversion in both pipelines."""

from confluence_md import confluence_storage_to_md, md_to_confluence_storage


class TestMarkdownToStorage:
    def test_local_image_becomes_attachment_macro(self):
        out = md_to_confluence_storage("![diagram](images/diagram.png)")
        assert '<ac:image ac:alt="diagram">' in out
        assert '<ri:attachment ri:filename="diagram.png" />' in out

    def test_local_image_path_collected(self):
        paths: list[str] = []
        md_to_confluence_storage("![a](img/one.png)\n\n![b](two.jpg)", paths)
        assert paths == ["img/one.png", "two.jpg"]

    def test_external_image_becomes_url_macro(self):
        out = md_to_confluence_storage("![logo](https://example.com/logo.svg)")
        assert '<ri:url ri:value="https://example.com/logo.svg" />' in out
        assert "ri:attachment" not in out

    def test_external_image_not_collected(self):
        paths: list[str] = []
        md_to_confluence_storage("![x](https://example.com/x.png)", paths)
        assert paths == []


class TestStorageToMarkdown:
    def test_attachment_image_with_prefix(self):
        storage = '<ac:image ac:alt="diagram"><ri:attachment ri:filename="d.png" /></ac:image>'
        out = confluence_storage_to_md(storage, attachment_prefix="Page_attachments/")
        assert "![diagram](Page_attachments/d.png)" in out

    def test_attachment_image_alt_falls_back_to_filename(self):
        storage = '<ac:image><ri:attachment ri:filename="chart.png" /></ac:image>'
        out = confluence_storage_to_md(storage)
        assert "![chart.png](chart.png)" in out

    def test_external_image_keeps_url(self):
        storage = (
            '<ac:image ac:alt="logo"><ri:url ri:value="https://example.com/l.svg" /></ac:image>'
        )
        out = confluence_storage_to_md(storage)
        assert "![logo](https://example.com/l.svg)" in out

    def test_image_inside_paragraph(self):
        storage = '<p>see <ac:image><ri:attachment ri:filename="x.png" /></ac:image> here</p>'
        out = confluence_storage_to_md(storage)
        assert "see ![x.png](x.png) here" in out


class TestRoundTrip:
    def test_local_image_round_trip(self):
        md = "![diagram](diagram.png)"
        storage = md_to_confluence_storage(md)
        assert "![diagram](diagram.png)" in confluence_storage_to_md(storage)

    def test_external_image_round_trip(self):
        md = "![logo](https://example.com/logo.svg)"
        storage = md_to_confluence_storage(md)
        assert md in confluence_storage_to_md(storage)
