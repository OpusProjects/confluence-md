# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **Concurrent-edit guard** — `download` embeds a version marker in the
  Markdown file; `edit` aborts when the remote page has changed since that
  download (pass `--force` to overwrite anyway). Markers are stripped before
  any upload.
- **`--version` flag** printing the tool version.
- **Recursive download** — `download --recursive` fetches the page and all
  its descendants, mirroring the Confluence page tree as a folder tree.
- **Task lists** — `- [ ]` / `- [x]` checkbox lists convert to Confluence
  action-item task lists and back, keeping the checked state.
- **Recursive upload** — `upload --recursive <folder> <parent_url>` syncs a
  folder of Markdown files as a page tree (the layout `download --recursive`
  writes), creating or updating pages as needed with the same version guard
  as `edit`.
- **Internal links in recursive downloads** — links between pages of the
  downloaded tree become relative links between the Markdown files instead
  of degrading to plain text.
- **Installable package** — `pip install .` now provides a `confluence-md`
  command on the PATH.
- **Image support** — local images referenced in Markdown are uploaded as
  page attachments and embedded; on download, attachment-backed images are
  saved into a `<name>_attachments/` folder and linked from the Markdown.
  External image URLs are embedded/kept without transfer.
- **Panel conversion on download** — Info / Note / Warning / Tip / Panel
  macros become blockquotes with a bold label (previously their content was
  lost). Multi-paragraph blockquotes now also render one quoted line per
  paragraph.
- **Panel conversion on upload** — blockquotes labeled `**Info:**`,
  `**Note:**`, `**Warning:**` or `**Tip:**` are restored to the matching
  panel macro, making panels round-trip.

### Fixed

- `download` dropped the content of Confluence elements that only wrap it:
  a page laid out in columns downloaded as an empty file, `expand` and
  other body-carrying macros vanished with everything inside them, and the
  text under an inline comment disappeared mid-sentence. Their content is
  now kept; `status` macros download as their title in bold and emoticons
  as their emoji.
- A `<` or `&` in a task-list item was written raw into the page body, so
  `upload` and `edit` of a checklist mentioning `a < b` or `R&D` were
  rejected by Confluence. The text is now escaped like the rest of the page.
- `download` flattened any table Confluence had wrapped in a
  `<div class="table-wrap">` — which is every table saved from the editor —
  to its cell texts run together, and did the same to headings, lists and
  paragraphs inside any other `<div>`. Wrappers are now transparent, and
  consecutive paragraphs inside a table cell or list item are kept apart
  (joined by a space in cells, as indented continuation lines in items).
- `download --recursive` silently lost a page when two siblings sanitised
  to the same filename (`Setup: A` and `Setup A` both became `Setup_A.md`,
  the second overwriting the first). Later siblings now get a numeric
  suffix (`Setup_A_2.md`).
- Image links written by `download` for attachments with a space or
  parenthesis in their name (`![a](Page_attachments/my file (1).png)`) did
  not render in standard Markdown viewers, and a percent-encoded link
  written by hand (`my%20file.png`) was uploaded under the encoded name and
  reported as a missing file. Filenames are now percent-encoded in links on
  download and decoded on upload.
- `download` fetched only the first page of a page's attachment list, so on
  pages with many attachments the images past the server's page size were
  reported as "attachment not found on page" and skipped. The whole list is
  now fetched.
- A `~~` inside a `~~~`-fenced code block (a shell here-doc, Lua, Perl) was
  turned into strikethrough on upload, corrupting the code. Tilde fences and
  fences longer than three characters are now protected like backtick ones.

## [0.1.0] - 2026-08-12

### Added

- **`upload` subcommand** — create a new Confluence Cloud page as a child of a
  parent page from a local Markdown file, refusing to shadow an existing title
  in the space.
- **`edit` subcommand** — replace the body of an existing page from a Markdown
  file as a new page version (history preserved), with optional `--title`
  rename.
- **`download` subcommand** — save any page as local Markdown, deriving the
  filename from the page title when no output path is given.
- **Bidirectional conversion** between Markdown and Confluence storage format:
  headings, paragraphs, tables, nested lists, blockquotes, horizontal rules,
  inline formatting (bold, italic, strikethrough, inline code, links, line
  breaks) and fenced code blocks with their language tag.
- **`[TOC]` marker** — maps to the Table of Contents macro on upload and to a
  generated list of heading anchor links on download.
- **`[CHILD_PAGES]` marker** — maps to the Children Display macro on upload
  and to a list of real child-page links on download.
- **`.env` configuration** via `CONFLUENCE_URL`, `CONFLUENCE_EMAIL` and
  `CONFLUENCE_API_TOKEN`.
