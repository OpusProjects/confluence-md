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
        out = confluence_storage_to_md("<ul><li>parent<ul><li>child</li></ul></li></ul>")
        assert "- parent" in out
        assert "  - child" in out

    def test_multiple_nested_lists_in_one_item(self):
        out = confluence_storage_to_md(
            "<ul><li>parent<ul><li>bullet child</li></ul><ol><li>numbered child</li></ol></li></ul>"
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
        storage = '<ac:structured-macro ac:name="toc" /><h1>Intro</h1><h2>Getting Started</h2>'
        out = confluence_storage_to_md(storage)
        assert "- [Intro](#intro)" in out
        assert "  - [Getting Started](#getting-started)" in out

    def test_children_macro_to_marker(self):
        out = confluence_storage_to_md('<ac:structured-macro ac:name="children" />')
        assert "[CHILD_PAGES]" in out

    def test_unknown_macro_body_kept(self):
        storage = (
            '<p>before</p><ac:structured-macro ac:name="excerpt">'
            "<ac:rich-text-body><p>excerpt text</p></ac:rich-text-body>"
            "</ac:structured-macro><p>after</p>"
        )
        out = confluence_storage_to_md(storage)
        assert out == "before\n\nexcerpt text\n\nafter\n"

    def test_expand_macro_keeps_title_and_body(self):
        storage = (
            '<ac:structured-macro ac:name="expand">'
            '<ac:parameter ac:name="title">Details</ac:parameter>'
            "<ac:rich-text-body><p>Hidden <strong>text</strong></p>"
            "<ul><li>item</li></ul></ac:rich-text-body>"
            "</ac:structured-macro>"
        )
        out = confluence_storage_to_md(storage)
        assert out == "**Details**\n\nHidden **text**\n\n- item\n"

    def test_bodiless_macro_with_title_becomes_bold_text(self):
        storage = (
            '<p>State: <ac:structured-macro ac:name="status">'
            '<ac:parameter ac:name="colour">Green</ac:parameter>'
            '<ac:parameter ac:name="title">DONE</ac:parameter>'
            "</ac:structured-macro></p>"
        )
        assert confluence_storage_to_md(storage) == "State: **DONE**\n"

    def test_bodiless_macro_without_title_removed(self):
        storage = (
            '<p>a</p><ac:structured-macro ac:name="jira">'
            '<ac:parameter ac:name="key">PROJ-1</ac:parameter>'
            "</ac:structured-macro><p>b</p>"
        )
        assert confluence_storage_to_md(storage) == "a\n\nb\n"

    def test_layout_content_kept(self):
        storage = (
            '<ac:layout><ac:layout-section ac:type="two_equal">'
            "<ac:layout-cell><p>Left</p></ac:layout-cell>"
            "<ac:layout-cell><h2>Right</h2><p>text</p></ac:layout-cell>"
            "</ac:layout-section></ac:layout>"
        )
        assert confluence_storage_to_md(storage) == "Left\n\n## Right\n\ntext\n"

    def test_inline_comment_marker_keeps_text(self):
        storage = (
            '<p>Keep <ac:inline-comment-marker ac:ref="abc">this part</ac:inline-comment-marker>'
            " of the sentence.</p>"
        )
        assert confluence_storage_to_md(storage) == "Keep this part of the sentence.\n"

    def test_emoticon_becomes_fallback_text(self):
        storage = (
            '<p>Hi <ac:emoticon ac:name="smile" ac:emoji-shortname=":smile:"'
            ' ac:emoji-fallback="\U0001f604"/> there</p>'
        )
        assert confluence_storage_to_md(storage) == "Hi \U0001f604 there\n"

    def test_emoticon_without_fallback_removed(self):
        storage = '<p>Hi <ac:emoticon ac:name="smile"/> there</p>'
        assert confluence_storage_to_md(storage) == "Hi  there\n"

    def test_adf_extension_keeps_fallback(self):
        storage = (
            '<ac:adf-extension><ac:adf-node type="decision-list">'
            "<ac:adf-content><p>ignored</p></ac:adf-content></ac:adf-node>"
            "<ac:adf-fallback><p>Fallback text</p></ac:adf-fallback></ac:adf-extension>"
        )
        assert confluence_storage_to_md(storage) == "Fallback text\n"


class TestPanels:
    def test_info_panel_becomes_labeled_blockquote(self):
        storage = (
            '<ac:structured-macro ac:name="info">'
            "<ac:rich-text-body><p>useful info</p></ac:rich-text-body>"
            "</ac:structured-macro>"
        )
        out = confluence_storage_to_md(storage)
        assert "> **Info:** useful info" in out

    def test_panel_title_used_as_label(self):
        storage = (
            '<ac:structured-macro ac:name="warning">'
            '<ac:parameter ac:name="title">Danger Zone</ac:parameter>'
            "<ac:rich-text-body><p>be careful</p></ac:rich-text-body>"
            "</ac:structured-macro>"
        )
        out = confluence_storage_to_md(storage)
        assert "> **Danger Zone:** be careful" in out

    def test_multi_paragraph_panel(self):
        storage = (
            '<ac:structured-macro ac:name="note">'
            "<ac:rich-text-body><p>first</p><p>second</p></ac:rich-text-body>"
            "</ac:structured-macro>"
        )
        out = confluence_storage_to_md(storage)
        assert "> **Note:** first" in out
        assert "> second" in out

    def test_empty_panel_keeps_label(self):
        storage = (
            '<ac:structured-macro ac:name="tip"><ac:rich-text-body>'
            "</ac:rich-text-body></ac:structured-macro>"
        )
        out = confluence_storage_to_md(storage)
        assert "> **Tip:**" in out


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
        storage = '<p>see <ac:link><ri:page ri:content-title="Target Page" /></ac:link></p>'
        out = confluence_storage_to_md(storage)
        assert "Target Page" in out
