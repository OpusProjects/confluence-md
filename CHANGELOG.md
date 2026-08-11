# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **`--version` flag** printing the tool version.
- **Panel conversion on download** — Info / Note / Warning / Tip / Panel
  macros become blockquotes with a bold label (previously their content was
  lost). Multi-paragraph blockquotes now also render one quoted line per
  paragraph.

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
