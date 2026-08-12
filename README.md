# Confluence MD

[![confluence-md CI](https://github.com/OpusProjects/confluence-md/actions/workflows/build.yaml/badge.svg)](https://github.com/OpusProjects/confluence-md/actions/workflows/build.yaml)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)

Two-way Markdown ↔ Confluence sync from the command line, written in Python.

Confluence MD allows you to create, edit and download Confluence Cloud
pages as local Markdown files — all through the REST API, with a
single-file script and no server-side install.

Round-tripping is the point: every supported element converts in both
directions, so a page can be downloaded, edited locally in your editor,
and pushed back without losing structure.

---

## ✨ Features

- **Three subcommands**: `upload` creates a page, `edit` replaces one, `download` saves it as Markdown
- **Bidirectional conversion**: headings, tables, lists, blockquotes, code and formatting round-trip
- **Code language preserved**: fenced blocks map to the Confluence `code` macro in both directions
- **Task lists**: `- [ ]` / `- [x]` become Confluence action items and back, checked state kept
- **Panels**: `**Note:**`-labeled blockquotes become Info/Note/Warning/Tip panels and back
- **Table of Contents**: `[TOC]` becomes the TOC macro on upload, anchor links on download
- **Child pages**: `[CHILD_PAGES]` becomes the Children macro on upload, page links on download
- **Images**: local images upload as attachments; page images download into a folder next to the file
- **Tree sync**: `--recursive` uploads or downloads whole page trees as folders, links rewritten
- **Edit safety**: `edit` refuses to overwrite pages changed since your download, unless `--force`
- **Version history preserved**: every update is a new page version, history never destroyed
- **Collision safety**: `upload` refuses to shadow an existing page title and points you to `edit`
- **Zero infrastructure**: one Python file, four pip dependencies, credentials in a local `.env`

---

## 📚 Documentation

| Document | What it covers |
|---|---|
| [Architecture](docs/architecture.md) | Module layout, the two pipelines, placeholders, version markers and tree sync |
| [Configuration](docs/configuration.md) | Creating the API token, finding your base URL, and the `.env` file |
| [Usage](docs/usage.md) | The three subcommands, every argument, examples and the download–edit–push workflow |
| [Conversion](docs/conversion.md) | Element-by-element Markdown ↔ Confluence equivalences, and known limitations |
| [Troubleshooting](docs/troubleshooting.md) | Symptom first: what each error means and how to fix it |

---

## 🤝 Contributing

Contributions are welcome: [CONTRIBUTING.md](CONTRIBUTING.md) covers the PR workflow, commit style, local checks and project rules.

Security issues: see [SECURITY.md](SECURITY.md) for private reporting.

---

## 👥 Authors

- [Blai Peidro](https://github.com/blaipr)

---

## ⚖️ License

[Apache 2.0](LICENSE)
