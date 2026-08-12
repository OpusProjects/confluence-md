# Usage

The script has three subcommands. `--` options are always optional modifiers.

- [`upload` — create a new child page](#upload--create-a-new-child-page)
- [`edit` — replace the content of an existing page](#edit--replace-the-content-of-an-existing-page)
- [`download` — save a page as Markdown](#download--save-a-page-as-markdown)

```
python src/confluence_md.py upload   <file.md> <parent_url> <title>
python src/confluence_md.py edit     <file.md> <page_url>   [--title "..."]
python src/confluence_md.py download <page_url>             [output.md]
```

---

## `upload` — create a new child page

Creates a new page as a child of the given parent. Aborts with an error if a
page with the same title already exists in the space — use `edit` in that case.

```bash
python src/confluence_md.py upload <file.md> <parent_url> <title>
python src/confluence_md.py upload <folder>  <parent_url> --recursive [--force]
```

| Argument | Required | Description |
|---|---|---|
| `file.md` | Yes | Path to the local Markdown file (or a folder with `--recursive`) |
| `parent_url` | Yes | URL of the Confluence page under which the new page will be created |
| `title` | Yes* | Title for the new page (*not used with `--recursive`) |
| `--recursive` | No | Upload a folder of `.md` files as a page tree |
| `--force` | No | With `--recursive`: update even if a page changed on Confluence since download |

**Recursive mode** mirrors the layout written by `download --recursive`: every
`<name>.md` in the folder becomes a page under the parent, and a sibling
`<name>/` folder holds its children. For each file, the page title comes from
the leading `# Heading` (falling back to the filename); the target page is
chosen by the file's version marker if present, then by title lookup in the
space, and a new page is created otherwise. Files whose marker version no
longer matches the remote page are skipped with a warning unless `--force`
is given.

**Examples:**

```bash
python src/confluence_md.py upload release_notes.md \
  "https://myorg.atlassian.net/wiki/spaces/ENG/pages/123456789" \
  "Release Notes Q2 2026"
```

The parent URL is the page in Confluence under which the new page will appear.
Open that page in your browser and copy the address bar URL.

---

## `edit` — replace the content of an existing page

Overwrites the body of an existing Confluence page with the content of a local
Markdown file. No new page is created.

```bash
python src/confluence_md.py edit <file.md> <page_url> [--title "New Title"]
```

| Argument | Required | Description |
|---|---|---|
| `file.md` | Yes | Path to the local Markdown file whose content will replace the page body |
| `page_url` | Yes | URL of the existing Confluence page to overwrite |
| `--title` | No | Rename the page at the same time. If omitted, the existing title is kept |
| `--force` | No | Overwrite even if the page changed on Confluence since it was downloaded |

**Behaviour:**

- The page history is preserved — the change appears as a new version.
- The existing content is fully replaced. If you want to keep parts of it,
  download the page first, edit the Markdown, then run `edit`.
- Files produced by `download` carry a version marker comment. If the page
  has been edited on Confluence since your download, `edit` aborts instead of
  overwriting those changes — re-download and merge, or pass `--force`.

**Examples:**

```bash
# Replace body, keep current title
python src/confluence_md.py edit updated_doc.md \
  "https://myorg.atlassian.net/wiki/spaces/ENG/pages/123456789"

# Replace body and rename
python src/confluence_md.py edit updated_doc.md \
  "https://myorg.atlassian.net/wiki/spaces/ENG/pages/123456789" \
  --title "Updated Documentation"
```

**Typical workflow — download, edit locally, push back:**

```bash
python src/confluence_md.py download "https://myorg.atlassian.net/wiki/spaces/ENG/pages/123456789"
# edit the resulting .md file in your editor
python src/confluence_md.py edit My_Page_Title.md \
  "https://myorg.atlassian.net/wiki/spaces/ENG/pages/123456789"
```

---

## `download` — save a page as Markdown

Fetches a Confluence page and writes it to a local `.md` file.

```bash
python src/confluence_md.py download <page_url> [output.md] [--recursive]
```

| Argument | Required | Description |
|---|---|---|
| `page_url` | Yes | URL of the Confluence page to download |
| `output.md` | No | Output file path. Defaults to the page title with spaces replaced by underscores |
| `--recursive` | No | Also download all descendant pages, mirroring the page tree as folders |

Images embedded from page attachments are saved into a `<name>_attachments/`
folder next to the output file (created only when the page has such images).

The first line of the output file is a version marker comment
(`<!-- confluence-md page_id=... version=... -->`). Leave it in place: `edit`
uses it to detect concurrent changes, and strips it before uploading.

With `--recursive`, each page's children are written into a folder named
after the page, so the folder tree mirrors the Confluence page tree.
Confluence links between pages of the tree are rewritten as relative links
between the Markdown files:

```
Root_Page.md
Root_Page/
├── Child_Page.md
└── Child_Page/
    └── Grand_Child.md
```

**Examples:**

```bash
# Output filename derived from page title
python src/confluence_md.py download \
  "https://myorg.atlassian.net/wiki/spaces/ENG/pages/123456789"

# Explicit output path
python src/confluence_md.py download \
  "https://myorg.atlassian.net/wiki/spaces/ENG/pages/123456789" \
  my_local_copy.md
```
