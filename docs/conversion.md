# Conversion equivalences

Every element listed below converts in both directions (upload and download).

- [Formatting](#formatting)
- [Block elements](#block-elements)
- [Code blocks](#code-blocks)
- [Tables](#tables)
- [Table of Contents — `[TOC]`](#table-of-contents--toc)
- [Child Pages — `[CHILD_PAGES]`](#child-pages--child_pages)
- [Images](#images)
- [Task lists](#task-lists)
- [Panels](#panels)
- [Known limitations](#known-limitations)

---

## Formatting

Inline styles map one-to-one between Markdown syntax and Confluence HTML tags:

| Markdown | Confluence | Direction |
|---|---|---|
| `**bold**` | **bold** (`<strong>`) | both |
| `*italic*` | *italic* (`<em>`) | both |
| `~~strikethrough~~` | ~~strikethrough~~ (`<del>`) | both |
| `` `inline code` `` | `inline code` (`<code>`) | both |
| `[text](url)` | link (`<a href="url">`) | both |
| `  \n` (two trailing spaces) | line break (`<br>`) | both |

---

## Block elements

Structural elements keep their shape in both directions:

| Markdown | Confluence | Direction |
|---|---|---|
| `# Heading 1` ... `###### Heading 6` | `<h1>` ... `<h6>` | both |
| `> quoted text` | blockquote (`<blockquote>`) | both |
| `---` | horizontal rule (`<hr>`) | both |
| `- item` | unordered list (`<ul>`) | both |
| `1. item` | ordered list (`<ol>`) | both |
| indented sub-items | nested lists | both |

---

## Code blocks

Fenced code blocks keep their content and language across the round trip:

````
```python
def hello():
    print("world")
```
````

Converts to / from the Confluence `code` macro with `language=python`.
The language tag is preserved in both directions.

---

## Tables

Markdown pipe tables map to Confluence tables and back:

```
| Name   | Role      |
|--------|-----------|
| Alice  | Engineer  |
| Bob    | Designer  |
```

Converts to / from Confluence `<table>`. Inline formatting (bold, italic,
links) inside cells is preserved. On download, pipe characters (`|`) inside
cells are escaped and line breaks are replaced with spaces so they cannot
break the Markdown table structure.

---

## Table of Contents — `[TOC]`

**Upload:** A standalone `[TOC]` line in your Markdown becomes the Confluence
**Table of Contents macro**, which auto-generates a clickable TOC on the page
and keeps itself up to date whenever the page's headings change.

**Download:** The TOC macro becomes a list of anchor links to the page headings:

```markdown
- [Introduction](#introduction)
  - [Getting Started](#getting-started)
  - [Configuration](#configuration)
    - [Advanced Options](#advanced-options)
```

Each link points to the corresponding `#heading-slug` within the Markdown file.

---

## Child Pages — `[CHILD_PAGES]`

**Upload:** A standalone `[CHILD_PAGES]` line in your Markdown becomes the
Confluence **Children Display macro**, which auto-lists all child pages of
the page and updates dynamically as children are added or removed.

**Download:** The Children Display macro becomes a list of links to the child
pages:

```markdown
- [Child Page One](https://myorg.atlassian.net/wiki/spaces/ENG/pages/111111111)
- [Child Page Two](https://myorg.atlassian.net/wiki/spaces/ENG/pages/222222222)
```

To re-upload and keep the dynamic macro, replace the links with `[CHILD_PAGES]`.

---

## Images

Images convert in both directions, with local files travelling as page
attachments:

**Upload:** `![alt](path/to/image.png)` with a local path uploads the file as
a page attachment and embeds it with the Confluence image macro. Relative
paths are resolved against the Markdown file's directory; missing files are
skipped with a warning. External images (`![alt](https://...)`) are embedded
by URL without uploading anything.

**Download:** images backed by page attachments are saved into a
`<name>_attachments/` folder next to the output file, and the Markdown links
point there, so the images render correctly in any local Markdown preview:

```markdown
![diagram](My_Page_attachments/diagram.png)
```

External images keep their URL. A download → upload round trip re-attaches
the same files.

---

## Task lists

Markdown checkbox lists map to Confluence action-item task lists and back,
including the checked state and inline formatting in the item text, so a
to-do list can be ticked off on either side and synced across:

```markdown
- [ ] open task
- [x] completed task
```

A list converts as a task list only when **every** item starts with a
checkbox; lists mixing checkbox and plain items stay regular bullet lists,
so no list is ever converted half-way into a mix of tasks and text.

---

## Panels

Confluence panels round-trip through labeled blockquotes. On download, an
Info / Note / Warning / Tip / Panel macro becomes a blockquote with a bold
label — the panel's own title if it has one, otherwise its kind:

```markdown
> **Warning:** this action cannot be undone.
```

On upload, a blockquote starting with `**Info:**`, `**Note:**`,
`**Warning:**` or `**Tip:**` is restored to the matching panel macro.
Blockquotes with any other label (e.g. a custom panel title like
`**Danger Zone:**`) stay regular blockquotes.

---

## Known limitations

Some Confluence elements have no Markdown equivalent and degrade or disappear
during conversion:

- **Non-image attachments** (PDFs, archives, ...) are not downloaded; only
  attachments referenced by an image macro are fetched.
- **Panels with a custom title** download as blockquotes labeled with that
  title; on re-upload they stay blockquotes (only the four standard labels
  are restored to panels).
- **Confluence-specific macros** (other than `code`, `toc`, `children` and
  the panel macros) are stripped on download.
- **Internal page links** are converted to plain text on single-page
  download. In `download --recursive`, links between pages of the downloaded
  tree become relative file links; only links to pages outside the tree
  degrade to plain text.
- **Nested block elements inside blockquotes** (e.g. lists, tables) are
  flattened to inline text.
