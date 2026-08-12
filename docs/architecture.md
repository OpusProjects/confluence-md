# Architecture

How the single module is organised and why the non-obvious parts — placeholder
substitution, version markers, tree state — work the way they do.

- [Module layout](#module-layout)
- [The two conversion pipelines](#the-two-conversion-pipelines)
- [The placeholder mechanism](#the-placeholder-mechanism)
- [Version markers](#version-markers)
- [Tree sync](#tree-sync)
- [Attachments](#attachments)
- [Error handling](#error-handling)

## Module layout

Everything lives in `src/confluence_md.py`, grouped into four sections that
read top to bottom:

1. **Helpers** — authentication (`get_client`), URL parsing
   (`page_id_from_url`, `space_key_from_url`), the `api()` error wrapper,
   and the version-marker parser.
2. **Markdown → Confluence** — `md_to_confluence_storage` and its inner
   pre-processing.
3. **Confluence → Markdown** — `confluence_storage_to_md` plus the
   `_inline_md` / `_render_list` renderers.
4. **CLI** — one `cmd_*` function per subcommand, the tree-sync helpers
   (`download_page`, `upload_tree`, `sync_file`), and `main()`.

## The two conversion pipelines

Both pipelines are pure functions from string to string (plus optional
collectors), which is what makes them unit-testable without any network.

**Upload** (`md_to_confluence_storage`): pre-process strikethrough (skipping
code spans and fences), let python-markdown produce HTML, then walk the
BeautifulSoup tree replacing what Confluence needs as macros — `[TOC]` and
`[CHILD_PAGES]` markers, fenced code blocks, images, all-checkbox lists,
labeled blockquotes — and serialise.

**Download** (`confluence_storage_to_md`): parse the storage XHTML, replace
known macros (code, TOC, children, panels, images, task lists, page links)
with Markdown or placeholder text, strip every remaining `ac:`/`ri:` element,
then walk the top-level elements rendering headings, paragraphs, lists,
tables and blockquotes into Markdown lines.

The project rule that keeps these honest: **every element one pipeline
learns to produce, the other must learn to parse** — a page must survive
download → upload without losing structure (see
[CONTRIBUTING.md](../CONTRIBUTING.md)).

## The placeholder mechanism

BeautifulSoup's `html.parser` serialiser cannot round-trip two things the
storage format needs: CDATA sections (mangled into comments) and `ac:`
namespaced XML. So the upload pipeline never inserts macro XML into the
tree. Instead it:

1. replaces the source element with a null-byte-delimited placeholder
   string (e.g. `\x00MACRO3\x00`) that the serialiser passes through
   untouched, and
2. records `placeholder → macro XML` in an insertion-ordered dict, then
3. substitutes placeholders after `str(soup)` — **in reverse insertion
   order**, because a macro built late (a panel) can contain placeholders
   built early (a code block inside the panel body); the container must
   land in the output before its contents are substituted.

Null bytes are used precisely because they can never appear in legitimate
Markdown or HTML input.

The download pipeline uses the same trick once, for `[TOC]`: the macro is
replaced with `\x00TOC\x00` early, headings are collected during the element
walk, and the placeholder is swapped for the generated anchor list at the end.

## Version markers

Every downloaded file starts with one line of state:

```markdown
<!-- confluence-md page_id=123456789 version=7 -->
```

`parse_version_marker` splits it off wherever Markdown is read. The marker
serves two purposes:

- **Conflict detection** — `edit` (and recursive upload) compares the
  marker version against the live page and refuses to overwrite when the
  page moved on, unless `--force` is given.
- **Page identity** — recursive upload uses the marker's page ID to update
  the exact page a file came from, independent of title changes.

Markers are always stripped before conversion, so they never appear in page
content.

## Tree sync

Both directions mirror the same layout: `<name>.md` is a page, a sibling
`<name>/` folder holds its children, `<name>_attachments/` holds its image
attachments.

**Download** (`download_page`): recursion threads a `_tree` dict through the
calls, recording `title → written path` for every page. Page links are
emitted as `confluence-page://<quoted title>` placeholder links during
conversion; after the whole tree is on disk, `_rewrite_page_links` resolves
titles found in the map to relative file links and degrades the rest to
plain text. The rewrite must run last because a page can link to a sibling
that has not been downloaded yet when the page itself is written.

**Upload** (`upload_tree` / `sync_file`): per file, the target page is
chosen in priority order — version marker, then title lookup in the space,
then create under the parent. The leading `# h1` becomes the page title and
is removed from the body so it is not duplicated under Confluence's own
title rendering.

## Attachments

Local images referenced in Markdown are collected by the upload pipeline
(via the optional `image_paths` list) and attached by `attach_local_images`
after the page exists — attachment upload needs a page ID, so it can never
happen during conversion. On download, the converter only *names* the
attachment folder (`attachment_prefix`); `download_page` fetches the
attachments the links actually reference, matching by filename.

## Error handling

All fallible calls go through the `api()` wrapper, which converts any
exception into one readable `ERROR:` line and a non-zero exit. Subcommands
therefore contain no try/except; anything that reaches the user as a stack
trace is a bug. Expected user errors (missing file, title collision, version
conflict) are printed explicitly with actionable next steps before
`sys.exit(1)`.
