# Conversion equivalences

Every element listed below converts in both directions (upload and download).

## Formatting

| Markdown | Confluence | Direction |
|---|---|---|
| `**bold**` | **bold** (`<strong>`) | both |
| `*italic*` | *italic* (`<em>`) | both |
| `~~strikethrough~~` | ~~strikethrough~~ (`<del>`) | both |
| `` `inline code` `` | `inline code` (`<code>`) | both |
| `[text](url)` | link (`<a href="url">`) | both |
| `  \n` (two trailing spaces) | line break (`<br>`) | both |

## Block elements

| Markdown | Confluence | Direction |
|---|---|---|
| `# Heading 1` ... `###### Heading 6` | `<h1>` ... `<h6>` | both |
| `> quoted text` | blockquote (`<blockquote>`) | both |
| `---` | horizontal rule (`<hr>`) | both |
| `- item` | unordered list (`<ul>`) | both |
| `1. item` | ordered list (`<ol>`) | both |
| indented sub-items | nested lists | both |

## Code blocks

````
```python
def hello():
    print("world")
```
````

Converts to / from the Confluence `code` macro with `language=python`.
The language tag is preserved in both directions.

## Tables

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

## Table of Contents — `[TOC]`

**Upload:** A standalone `[TOC]` line in your Markdown becomes the Confluence
**Table of Contents macro**, which auto-generates a clickable TOC on the page.

**Download:** The TOC macro becomes a list of anchor links to the page headings:

```markdown
- [Introduction](#introduction)
  - [Getting Started](#getting-started)
  - [Configuration](#configuration)
    - [Advanced Options](#advanced-options)
```

Each link points to the corresponding `#heading-slug` within the Markdown file.

## Child Pages — `[CHILD_PAGES]`

**Upload:** A standalone `[CHILD_PAGES]` line in your Markdown becomes the
Confluence **Children Display macro**, which auto-lists all child pages.

**Download:** The Children Display macro becomes a list of links to the child
pages:

```markdown
- [Child Page One](https://myorg.atlassian.net/wiki/spaces/ENG/pages/111111111)
- [Child Page Two](https://myorg.atlassian.net/wiki/spaces/ENG/pages/222222222)
```

To re-upload and keep the dynamic macro, replace the links with `[CHILD_PAGES]`.

## Known limitations

- **Images and attachments** are not converted. Confluence image macros are
  stripped on download.
- **Info / Note / Warning / Tip panels** are stripped on download. Their text
  content is lost.
- **Confluence-specific macros** (other than `code`, `toc`, `children`) are
  stripped on download.
- **Internal page links** (links to other Confluence pages) are converted to
  plain text on download — the link label survives, the target does not.
- **Nested block elements inside blockquotes** (e.g. lists, tables) are
  flattened to inline text.
