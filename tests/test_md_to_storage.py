"""Tests for the Markdown --> Confluence storage-format pipeline."""

from confluence_md import md_to_confluence_storage


class TestBasicElements:
    def test_heading(self):
        assert "<h2>Title</h2>" in md_to_confluence_storage("## Title")

    def test_paragraph(self):
        assert "<p>Hello world</p>" in md_to_confluence_storage("Hello world")

    def test_bold_italic(self):
        out = md_to_confluence_storage("**bold** and *italic*")
        assert "<strong>bold</strong>" in out
        assert "<em>italic</em>" in out

    def test_link(self):
        out = md_to_confluence_storage("[text](https://example.com)")
        assert '<a href="https://example.com">text</a>' in out

    def test_table(self):
        out = md_to_confluence_storage("| A | B |\n|---|---|\n| 1 | 2 |")
        assert "<table>" in out
        assert "<th>A</th>" in out
        assert "<td>1</td>" in out


class TestStrikethrough:
    def test_plain_text_converted(self):
        assert "<del>gone</del>" in md_to_confluence_storage("~~gone~~")

    def test_inside_fenced_block_untouched(self):
        out = md_to_confluence_storage("```\n~~not struck~~\n```")
        assert "<del>" not in out
        assert "~~not struck~~" in out

    def test_inside_inline_code_untouched(self):
        out = md_to_confluence_storage("use `~~literal~~` here")
        assert "<del>" not in out

    def test_mixed_code_and_text(self):
        out = md_to_confluence_storage("~~struck~~ but `~~kept~~`")
        assert "<del>struck</del>" in out
        assert out.count("<del>") == 1


class TestCodeMacro:
    def test_language_preserved(self):
        out = md_to_confluence_storage('```python\nprint("hi")\n```')
        assert '<ac:structured-macro ac:name="code">' in out
        assert '<ac:parameter ac:name="language">python</ac:parameter>' in out
        assert '<![CDATA[print("hi")\n]]>' in out

    def test_no_language(self):
        out = md_to_confluence_storage("```\nplain\n```")
        assert '<ac:parameter ac:name="language"></ac:parameter>' in out

    def test_cdata_end_marker_escaped(self):
        out = md_to_confluence_storage("```\na = ']]>'\n```")
        assert "]]]]><![CDATA[>" in out


class TestMarkerMacros:
    def test_toc(self):
        out = md_to_confluence_storage("[TOC]\n\n# Head")
        assert '<ac:structured-macro ac:name="toc" />' in out

    def test_child_pages(self):
        out = md_to_confluence_storage("[CHILD_PAGES]")
        assert '<ac:structured-macro ac:name="children" />' in out

    def test_toc_in_normal_text_not_converted(self):
        out = md_to_confluence_storage("The [TOC] marker must stand alone")
        assert "ac:structured-macro" not in out
