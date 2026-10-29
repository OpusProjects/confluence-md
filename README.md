# confluence-md

Two-way Markdown and Confluence Cloud sync from the command line.

Download a Confluence page as Markdown, edit it in your editor, and push it back without losing
structure. It works page by page or on whole page trees, through the REST API, with no server-side
install.

## Install

Requires Python 3.10 or newer.

```bash
pip install .
```

This puts a `confluence-md` command on your PATH. From a checkout you can also run
`python src/confluence_md.py` after `pip install -r src/requirements.txt`.

## Configuration

The tool reads three values from a `.env` file in the directory it runs in:

```bash
cp .env.example .env
```

```env
CONFLUENCE_URL=https://<your-org>.atlassian.net/wiki
CONFLUENCE_EMAIL=your.email@company.com
CONFLUENCE_API_TOKEN=your-api-token-here
```

Confluence Cloud does not accept your password, so create an API token at
https://id.atlassian.com/manage-profile/security/api-tokens. The `.env` file is gitignored; never
commit it.

## Usage

```
confluence-md upload   <file.md> <parent_url> <title>
confluence-md upload   <folder>  <parent_url> --recursive [--force]
confluence-md edit     <file.md> <page_url>   [--title "..."] [--force]
confluence-md download <page_url>             [output.md] [--recursive]
```

Page URLs can be copied from the browser; both the `/spaces/.../pages/...` and the `?pageId=...`
forms work.

- `upload` creates a new page under a parent page. It refuses if a page with that title already
  exists in the space; use `edit` instead.
- `edit` replaces the body of an existing page as a new version, so history is kept. `--title`
  renames it at the same time.
- `download` saves a page as Markdown, named after the page title unless you give a path. Images
  attached to the page go into a `<name>_attachments/` folder next to the file.

A typical round trip:

```bash
confluence-md download "https://myorg.atlassian.net/wiki/spaces/ENG/pages/123456789"
# edit My_Page_Title.md
confluence-md edit My_Page_Title.md "https://myorg.atlassian.net/wiki/spaces/ENG/pages/123456789"
```

A downloaded file starts with a marker comment (`<!-- confluence-md page_id=... version=... -->`).
Leave it in place: if the page changed on Confluence since your download, `edit` stops instead of
overwriting those changes. Download again and merge, or pass `--force`.

### Page trees

`download --recursive` also downloads every descendant page. Each page's children go into a folder
named after it, and links between pages of the tree become relative links between the files:

```
Root_Page.md
Root_Page/
├── Child_Page.md
└── Child_Page/
    └── Grand_Child.md
```

`upload --recursive` takes the same layout back. Each file's title comes from its leading
`# Heading`. A file updates the page its marker names, or the page with that title, and a new page
is created otherwise. Files whose page changed since download are skipped unless `--force`.

## What converts

These convert in both directions:

- Headings, paragraphs, line breaks, horizontal rules, bold, italic, strikethrough, inline code
  and links
- Ordered, unordered and nested lists; task lists (`- [ ]`, `- [x]`) as Confluence action items
- Tables and blockquotes
- Fenced code blocks, as the Confluence `code` macro with the language kept
- Blockquotes starting with `**Info:**`, `**Note:**`, `**Warning:**` or `**Tip:**`, as panels
- `[TOC]` as the table of contents macro, and `[CHILD_PAGES]` as the children macro
- Images: local ones upload as attachments, attached ones download next to the file

Limits:

- Other Confluence macros lose the macro but keep their content; one with no content and no title
  (`jira`, `anchor`) is removed.
- Links to other pages become plain text, except between pages of a tree downloaded with
  `--recursive`.
- Lists and tables inside a blockquote are flattened to text.
- Attachments other than images are not downloaded.

## Development

```bash
pip install -r src/requirements.txt pytest ruff
ruff check src tests && ruff format --check src tests
python -m pytest tests/
```

## Documentation

- [Configuration](docs/configuration.md): the API token, the base URL and the `.env` file
- [Usage](docs/usage.md): every subcommand and argument, with examples
- [Conversion](docs/conversion.md): each Markdown and Confluence equivalence, and the limits
- [Troubleshooting](docs/troubleshooting.md): what each error means and how to fix it
- [Architecture](docs/architecture.md): how the code is laid out and how the conversion works

## License

Apache 2.0, see [LICENSE](LICENSE).
