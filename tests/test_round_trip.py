"""Round-trip tests: Markdown --> storage format --> Markdown.

The project's core promise is that a page survives a download -> edit ->
upload cycle without losing structure, so these tests push Markdown
through both pipelines and assert the structure comes back.
"""

from confluence_md import confluence_storage_to_md, md_to_confluence_storage


def round_trip(md: str) -> str:
    return confluence_storage_to_md(md_to_confluence_storage(md))


def test_headings_and_paragraphs():
    out = round_trip("# One\n\nText here.\n\n## Two\n\nMore text.")
    assert "# One" in out
    assert "## Two" in out
    assert "Text here." in out


def test_inline_formatting():
    out = round_trip("**bold** *italic* ~~struck~~ `code` [link](https://e.com)")
    assert "**bold**" in out
    assert "*italic*" in out
    assert "~~struck~~" in out
    assert "`code`" in out
    assert "[link](https://e.com)" in out


def test_code_block_with_language():
    out = round_trip('```python\nprint("hi")\n```')
    assert "```python" in out
    assert 'print("hi")' in out


def test_table():
    out = round_trip("| A | B |\n|---|---|\n| 1 | 2 |")
    assert "| A | B |" in out
    assert "| --- | --- |" in out
    assert "| 1 | 2 |" in out


def test_nested_list():
    out = round_trip("- parent\n    - child\n- sibling")
    assert "- parent" in out
    assert "  - child" in out
    assert "- sibling" in out


def test_child_pages_marker():
    assert "[CHILD_PAGES]" in round_trip("[CHILD_PAGES]")


def test_blockquote():
    assert "> wise words" in round_trip("> wise words")
