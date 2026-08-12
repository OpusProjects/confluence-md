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
