"""Tests for the Confluence storage-format --> Markdown pipeline."""

from confluence_md import confluence_storage_to_md


class TestBasicElements:
    def test_heading(self):
        assert "## Title" in confluence_storage_to_md("<h2>Title</h2>")

    def test_paragraph(self):
        assert "Hello world" in confluence_storage_to_md("<p>Hello world</p>")

    def test_inline_formatting(self):
        out = confluence_storage_to_md(
            "<p><strong>b</strong> <em>i</em> <del>s</del> <code>c</code></p>"
        )
        assert "**b**" in out
        assert "*i*" in out
        assert "~~s~~" in out
        assert "`c`" in out

    def test_link(self):
        out = confluence_storage_to_md('<p><a href="https://example.com">text</a></p>')
        assert "[text](https://example.com)" in out

    def test_horizontal_rule(self):
        assert "---" in confluence_storage_to_md("<p>a</p><hr /><p>b</p>")

    def test_blockquote(self):
        out = confluence_storage_to_md("<blockquote><p>quoted</p></blockquote>")
        assert "> quoted" in out


class TestTables:
    def test_header_separator(self):
        out = confluence_storage_to_md(
            "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>"
        )
        assert "| A | B |" in out
        assert "| --- | --- |" in out
        assert "| 1 | 2 |" in out

    def test_pipes_escaped_in_cells(self):
        out = confluence_storage_to_md("<table><tr><td>a|b</td></tr></table>")
        assert "a\\|b" in out


class TestLists:
    def test_unordered(self):
        out = confluence_storage_to_md("<ul><li>one</li><li>two</li></ul>")
        assert "- one" in out
        assert "- two" in out

    def test_ordered(self):
        out = confluence_storage_to_md("<ol><li>first</li></ol>")
        assert "1. first" in out

    def test_nested(self):
        out = confluence_storage_to_md(
            "<ul><li>parent<ul><li>child</li></ul></li></ul>"
        )
        assert "- parent" in out
        assert "  - child" in out

    def test_multiple_nested_lists_in_one_item(self):
        out = confluence_storage_to_md(
            "<ul><li>parent"
            "<ul><li>bullet child</li></ul>"
            "<ol><li>numbered child</li></ol>"
            "</li></ul>"
        )
        assert "- parent" in out
        assert "  - bullet child" in out
        assert "  1. numbered child" in out


class TestMacros:
    def test_code_macro_to_fence(self):
        storage = (
            '<ac:structured-macro ac:name="code">'
            '<ac:parameter ac:name="language">python</ac:parameter>'
            '<ac:plain-text-body><![CDATA[print("hi")]]></ac:plain-text-body>'
            "</ac:structured-macro>"
        )
        out = confluence_storage_to_md(storage)
        assert "```python" in out
        assert 'print("hi")' in out

    def test_toc_macro_builds_anchor_links(self):
        storage = (
            '<ac:structured-macro ac:name="toc" />'
            "<h1>Intro</h1><h2>Getting Started</h2>"
        )
        out = confluence_storage_to_md(storage)
        assert "- [Intro](#intro)" in out
        assert "  - [Getting Started](#getting-started)" in out

    def test_children_macro_to_marker(self):
        out = confluence_storage_to_md('<ac:structured-macro ac:name="children" />')
        assert "[CHILD_PAGES]" in out

    def test_unknown_macro_stripped(self):
        storage = (
            '<p>before</p><ac:structured-macro ac:name="info">'
            "<ac:rich-text-body><p>panel text</p></ac:rich-text-body>"
            "</ac:structured-macro><p>after</p>"
        )
        out = confluence_storage_to_md(storage)
        assert "before" in out
        assert "after" in out
        assert "ac:" not in out


class TestPageLinks:
    def test_link_body_text_preserved(self):
        storage = (
            "<p>see <ac:link>"
            '<ri:page ri:content-title="Target Page" />'
            "<ac:plain-text-link-body><![CDATA[the target]]></ac:plain-text-link-body>"
            "</ac:link> for details</p>"
        )
        out = confluence_storage_to_md(storage)
        assert "the target" in out
        assert "ac:link" not in out

    def test_falls_back_to_page_title(self):
        storage = (
            '<p>see <ac:link><ri:page ri:content-title="Target Page" /></ac:link></p>'
        )
        out = confluence_storage_to_md(storage)
        assert "Target Page" in out
