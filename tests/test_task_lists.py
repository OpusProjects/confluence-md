"""Tests for task list conversion in both pipelines."""

from confluence_md import confluence_storage_to_md, md_to_confluence_storage

TASK_LIST_STORAGE = (
    "<ac:task-list>"
    "<ac:task><ac:task-status>incomplete</ac:task-status>"
    "<ac:task-body><span>first task</span></ac:task-body></ac:task>"
    "<ac:task><ac:task-status>complete</ac:task-status>"
    "<ac:task-body><span>done task</span></ac:task-body></ac:task>"
    "</ac:task-list>"
)


class TestMarkdownToStorage:
    def test_checkbox_list_becomes_task_list(self):
        out = md_to_confluence_storage("- [ ] first task\n- [x] done task")
        assert "<ac:task-list>" in out
        assert "<ac:task-status>incomplete</ac:task-status>" in out
        assert "<ac:task-status>complete</ac:task-status>" in out
        assert "<span>first task</span>" in out
        assert "<ul>" not in out

    def test_uppercase_x_counts_as_complete(self):
        out = md_to_confluence_storage("- [X] shouted")
        assert "<ac:task-status>complete</ac:task-status>" in out

    def test_inline_formatting_preserved_in_task_body(self):
        out = md_to_confluence_storage("- [ ] fix the **big** bug")
        assert "<span>fix the <strong>big</strong> bug</span>" in out

    def test_special_characters_escaped_in_task_body(self):
        out = md_to_confluence_storage("- [ ] check a < b && c > d")
        assert "<span>check a &lt; b &amp;&amp; c &gt; d</span>" in out
        assert "a < b" not in out

    def test_mixed_list_stays_regular(self):
        out = md_to_confluence_storage("- [ ] task item\n- plain item")
        assert "ac:task-list" not in out
        assert "<ul>" in out

    def test_plain_list_untouched(self):
        out = md_to_confluence_storage("- one\n- two")
        assert "ac:task-list" not in out


class TestStorageToMarkdown:
    def test_task_list_becomes_checkboxes(self):
        out = confluence_storage_to_md(TASK_LIST_STORAGE)
        assert "- [ ] first task" in out
        assert "- [x] done task" in out

    def test_task_body_formatting_preserved(self):
        storage = (
            "<ac:task-list><ac:task>"
            "<ac:task-status>incomplete</ac:task-status>"
            "<ac:task-body><span>fix the <strong>big</strong> bug</span></ac:task-body>"
            "</ac:task></ac:task-list>"
        )
        out = confluence_storage_to_md(storage)
        assert "- [ ] fix the **big** bug" in out


class TestRoundTrip:
    def test_markdown_round_trip(self):
        md = "- [ ] first task\n- [x] done task"
        out = confluence_storage_to_md(md_to_confluence_storage(md))
        assert "- [ ] first task" in out
        assert "- [x] done task" in out

    def test_special_characters_round_trip(self):
        md = "- [ ] a < b & c\n- [x] d > e"
        out = confluence_storage_to_md(md_to_confluence_storage(md))
        assert "- [ ] a < b & c" in out
        assert "- [x] d > e" in out

    def test_storage_round_trip(self):
        md = confluence_storage_to_md(TASK_LIST_STORAGE)
        out = md_to_confluence_storage(md)
        assert "<ac:task-list>" in out
        assert "<ac:task-status>complete</ac:task-status>" in out
