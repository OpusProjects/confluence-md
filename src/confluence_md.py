#!/usr/bin/env python3
"""Manage Confluence pages from the command line.

Provides three subcommands to interact with Confluence Cloud via the
REST API:

    upload   -- Create a new child page from a local Markdown file.
    edit     -- Replace the body of an existing page from a Markdown file.
    download -- Save a Confluence page as a local Markdown file.

Environment variables (loaded from .env):
    CONFLUENCE_URL       -- Base URL, e.g. https://org.atlassian.net/wiki
    CONFLUENCE_EMAIL     -- Atlassian account email address.
    CONFLUENCE_API_TOKEN -- API token generated from Atlassian account settings.

Usage::

    python src/confluence_md.py upload   <file.md> <parent_url> <title>
    python src/confluence_md.py upload   <folder>  <parent_url> --recursive [--force]
    python src/confluence_md.py edit     <file.md> <page_url>   [--title "..."] [--force]
    python src/confluence_md.py download <page_url>             [output.md] [--recursive]
"""

# ---------------------------------------------------------------------------
# Standard library imports
# ---------------------------------------------------------------------------
import argparse
import html
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

# ---------------------------------------------------------------------------
# Third-party imports
# ---------------------------------------------------------------------------
import markdown
from atlassian import Confluence
from bs4 import BeautifulSoup, NavigableString, Tag
from dotenv import load_dotenv

__version__ = "0.1.0"

# ---------------------------------------------------------------------------
# Configuration -- loaded once at module level from the .env file
# ---------------------------------------------------------------------------
load_dotenv()

CONFLUENCE_URL = os.getenv("CONFLUENCE_URL", "").rstrip("/")
EMAIL = os.getenv("CONFLUENCE_EMAIL")
TOKEN = os.getenv("CONFLUENCE_API_TOKEN")


# ===================================================================
# Helper functions -- authentication, URL parsing, error handling
# ===================================================================


def get_client() -> Confluence:
    """Build and return an authenticated Confluence Cloud client.

    Reads credentials from the module-level globals which are populated
    from environment variables at import time.

    Returns:
        Confluence: An authenticated client instance ready for API calls.

    Raises:
        SystemExit: If any of the three required environment variables
            is missing or empty.
    """
    if not all([CONFLUENCE_URL, EMAIL, TOKEN]):
        print("ERROR: Set CONFLUENCE_URL, CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN in .env")
        sys.exit(1)
    return Confluence(url=CONFLUENCE_URL, username=EMAIL, password=TOKEN, cloud=True)


def page_id_from_url(url: str) -> str:
    """Extract the numeric page ID from a Confluence page URL.

    Supports two common URL formats:
        - /pages/123456789  (pretty URL)
        - ?pageId=123456789 (query-string URL)

    Args:
        url: Full URL of a Confluence page.

    Returns:
        The page ID as a string of digits.

    Raises:
        ValueError: If neither pattern is found in the URL.
    """
    m = re.search(r"(?:/pages/|[?&]pageId=)(\d+)", url)
    if m:
        return m.group(1)
    raise ValueError(f"Cannot extract page ID from URL: {url}")


def space_key_from_url(url: str) -> str:
    """Extract the space key from a Confluence page URL.

    Looks for the /spaces/<KEY>/ segment in the URL path.

    Args:
        url: Full URL of a Confluence page.

    Returns:
        The space key string (e.g. "ENG", "TEAM").

    Raises:
        ValueError: If the /spaces/ segment is not found.
    """
    m = re.search(r"/spaces/([^/]+)/", url)
    if m:
        return m.group(1)
    raise ValueError(f"Cannot extract space key from URL: {url}")


def get_page(client: Confluence, url: str, expand: str) -> dict:
    """Fetch a single Confluence page by extracting its ID from a URL.

    Args:
        client: Authenticated Confluence client.
        url: Full URL of the page to fetch.
        expand: Comma-separated list of fields to expand in the API
            response (e.g. "body.storage,space").

    Returns:
        The page resource dict as returned by the Confluence REST API.

    Raises:
        SystemExit: If the page ID cannot be parsed or the API call fails.
    """
    page_id = api(page_id_from_url, url)
    return api(client.get_page_by_id, page_id, expand=expand)


def api(fn, *args, **kwargs) -> Any:
    """Call a function and convert any exception into a fatal error message.

    This is the central error-handling wrapper for all API calls and URL
    parsing. On failure it prints a human-readable message and exits,
    keeping the subcommand functions free of try/except boilerplate.

    Args:
        fn: The callable to invoke.
        *args: Positional arguments forwarded to fn.
        **kwargs: Keyword arguments forwarded to fn.

    Returns:
        Whatever fn returns on success.

    Raises:
        SystemExit: On any exception raised by fn.
    """
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


def parse_version_marker(md_text: str) -> tuple[str, str | None, int | None]:
    """Split the confluence-md version marker off a Markdown string.

    Downloaded pages start with a marker comment recording which page and
    version they came from::

        <!-- confluence-md page_id=123456789 version=7 -->

    The marker lets "edit" detect that the remote page has changed since
    the download, and is stripped before any content is uploaded.

    Args:
        md_text: Markdown text, possibly starting with a marker.

    Returns:
        A (text, page_id, version) tuple. text is the Markdown without
        the marker; page_id and version are None when no marker is found.
    """
    m = re.match(
        r"\s*<!--\s*confluence-md\s+page_id=(\d+)\s+version=(\d+)\s*-->\s*\n?",
        md_text,
    )
    if not m:
        return md_text, None, None
    return md_text[m.end() :], m.group(1), int(m.group(2))


def read_md(path: str) -> str:
    """Read a Markdown file from disk and return its contents as a string.

    Args:
        path: Filesystem path to the .md file.

    Returns:
        The full text content of the file, decoded as UTF-8.

    Raises:
        SystemExit: If the file does not exist.
    """
    p = Path(path)
    if not p.is_file():
        print(f"ERROR: File not found: {p}")
        sys.exit(1)
    return p.read_text(encoding="utf-8")


# ===================================================================
# Markdown --> Confluence conversion
# ===================================================================


def md_to_confluence_storage(md_text: str, image_paths: list[str] | None = None) -> str:
    """Convert a Markdown string to Confluence storage-format XHTML.

    The conversion pipeline is:

        1. Pre-process strikethrough (~~text~~ --> <del>text</del>)
           because python-markdown does not support it natively.
        2. Run python-markdown with tables, fenced_code, and sane_lists
           extensions to produce standard HTML.
        3. Detect special marker paragraphs ([TOC] and [CHILD_PAGES])
           and replace them with Confluence macro placeholders.
        4. Convert fenced code blocks (<pre><code>) into Confluence
           "code" structured macros with CDATA bodies.
        5. Convert images (<img>) into Confluence image macros: external
           URLs become ri:url references, local paths become
           ri:attachment references (the caller uploads the files).
        6. Convert task lists (- [ ] / - [x] items) into Confluence
           ac:task-list macros with complete/incomplete statuses.
        7. Convert blockquotes labeled **Info:**, **Note:**, **Warning:**
           or **Tip:** (the shape "download" produces for panels) back
           into the matching Confluence panel macro.
        8. Substitute all placeholders back into the serialised HTML.

    Null-byte delimited placeholders are used because BeautifulSoup's
    html.parser serialiser mangles CDATA sections and ac: namespaced
    XML into comments. The placeholders are injected after serialisation.

    Args:
        md_text: Raw Markdown source text.
        image_paths: Optional list that collects the local image paths
            referenced by the Markdown (as written in the source). The
            caller is responsible for attaching those files to the page.

    Returns:
        A string of Confluence storage-format XHTML, ready to be passed
        to the create_page or update_page API calls.
    """

    # -- Step 1: Pre-process strikethrough syntax -----------------------
    # python-markdown has no built-in ~~text~~ support, so we convert it
    # to raw <del> HTML before the markdown parser runs. We must skip
    # fenced code blocks and inline code spans to avoid mangling code
    # content.
    def _replace_strikethrough(md_src: str) -> str:
        parts = re.split(r"(```.*?```)", md_src, flags=re.DOTALL)
        for i, part in enumerate(parts):
            # Even-indexed parts are outside code fences; odd are inside.
            if i % 2 == 0:
                # Within non-fence text, also protect `inline code` spans.
                spans = re.split(r"(`[^`\n]*`)", part)
                for j, span in enumerate(spans):
                    if j % 2 == 0:
                        spans[j] = re.sub(r"~~(.+?)~~", r"<del>\1</del>", span)
                parts[i] = "".join(spans)
        return "".join(parts)

    md_text = _replace_strikethrough(md_text)

    # -- Step 2: Markdown --> HTML --------------------------------------
    html_body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "sane_lists"],
    )
    soup = BeautifulSoup(html_body, "html.parser")

    # This dict accumulates placeholder --> macro mappings. After the
    # soup is serialised to a string, each placeholder is swapped for
    # the raw macro XML that BeautifulSoup would otherwise corrupt.
    macros = {}

    # -- Step 3: Detect [TOC] and [CHILD_PAGES] markers ----------------
    # These are standalone paragraphs containing only the marker text.
    # They get replaced with Confluence structured macros.
    for p in soup.find_all("p"):
        text = p.get_text(strip=True)
        if text == "[TOC]":
            # Table of Contents macro -- Confluence auto-generates a TOC
            # from the page headings when this macro is present.
            placeholder = "\x00TOC\x00"
            macros[placeholder] = '<ac:structured-macro ac:name="toc" />'
            p.replace_with(placeholder)
        elif text == "[CHILD_PAGES]":
            # Children Display macro -- Confluence renders a dynamic list
            # of all child pages underneath the current page.
            placeholder = "\x00CHILDREN\x00"
            macros[placeholder] = '<ac:structured-macro ac:name="children" />'
            p.replace_with(placeholder)

    # -- Step 4: Convert fenced code blocks to Confluence macros --------
    # Each <pre> block is replaced with a null-byte placeholder. The
    # actual ac:structured-macro XML is stored in the macros dict and
    # substituted after serialisation, because html.parser mangles
    # CDATA sections into comments if they appear in the tree.
    for i, pre in enumerate(soup.find_all("pre")):
        code = pre.find("code")

        # Extract the language from the CSS class (e.g. "language-python").
        # The fenced_code extension adds this class to the <code> element.
        lang = ""
        if code and code.get("class"):
            for cls in code["class"]:
                if cls.startswith("language-"):
                    lang = html.escape(cls[len("language-") :])
                    break

        # Get the raw code text from <code> if present, otherwise from <pre>.
        code_text = code.get_text() if code else pre.get_text()

        # Escape the CDATA end marker so it does not prematurely close
        # the CDATA section inside the Confluence macro body.
        code_text = code_text.replace("]]>", "]]]]><![CDATA[>")

        # Build the placeholder and its corresponding macro XML.
        placeholder = f"\x00MACRO{i}\x00"
        macros[placeholder] = (
            f'<ac:structured-macro ac:name="code">'
            f'<ac:parameter ac:name="language">{lang}</ac:parameter>'
            f"<ac:plain-text-body><![CDATA[{code_text}]]></ac:plain-text-body>"
            f"</ac:structured-macro>"
        )
        pre.replace_with(placeholder)

    # -- Step 5: Convert images to Confluence image macros --------------
    # External URLs are referenced directly (ri:url). Local paths become
    # attachment references (ri:attachment) by filename; the caller
    # attaches the actual files via the API after creating the page.
    for i, img in enumerate(soup.find_all("img")):
        src = img.get("src", "")
        alt = img.get("alt", "")
        placeholder = f"\x00IMG{i}\x00"
        if re.match(r"^https?://", src):
            macros[placeholder] = (
                f'<ac:image ac:alt="{html.escape(alt)}">'
                f'<ri:url ri:value="{html.escape(src)}" /></ac:image>'
            )
        else:
            # A Markdown link target is percent-encoded ("my%20file.png"
            # for a file called "my file.png"), which is how "download"
            # writes attachment names. Decode it to find the file on disk
            # and to name the attachment as Confluence knows it.
            src = unquote(src)
            if image_paths is not None:
                image_paths.append(src)
            filename = Path(src).name
            macros[placeholder] = (
                f'<ac:image ac:alt="{html.escape(alt)}">'
                f'<ri:attachment ri:filename="{html.escape(filename)}" /></ac:image>'
            )
        img.replace_with(placeholder)

    # -- Step 6: Convert task lists to Confluence task-list macros ------
    # python-markdown has no task-list support, so "- [ ] item" arrives
    # as a list item whose text starts with the literal checkbox. A <ul>
    # where every item has that shape becomes an ac:task-list macro.
    checkbox_re = re.compile(r"^\[( |x|X)\]\s*")
    for i, ul in enumerate(soup.find_all("ul")):
        items = ul.find_all("li", recursive=False)
        prefixes = []
        for li in items:
            first = li.contents[0] if li.contents else None
            m = checkbox_re.match(str(first)) if isinstance(first, NavigableString) else None
            prefixes.append(m)
        if not items or not all(prefixes):
            continue

        tasks_xml = []
        for li, m in zip(items, prefixes, strict=True):
            # Strip the checkbox prefix, keep the rest (with formatting).
            li.contents[0].replace_with(soup.new_string(str(li.contents[0])[m.end() :]))
            status = "complete" if m.group(1).lower() == "x" else "incomplete"
            # decode_contents() serialises the text nodes with entities;
            # str() on each child does not, so a "<" or "&" in the item
            # text landed raw in the XML and Confluence rejected the page.
            body_html = li.decode_contents().strip()
            tasks_xml.append(
                f"<ac:task><ac:task-status>{status}</ac:task-status>"
                f"<ac:task-body><span>{body_html}</span></ac:task-body></ac:task>"
            )
        placeholder = f"\x00TASKLIST{i}\x00"
        macros[placeholder] = f"<ac:task-list>{''.join(tasks_xml)}</ac:task-list>"
        ul.replace_with(placeholder)

    # -- Step 7: Convert labeled blockquotes back to panel macros -------
    # "download" degrades panels to blockquotes starting with a bold
    # label; recognise that shape and restore the panel macro so the
    # round trip preserves Info / Note / Warning / Tip panels.
    panel_kinds = {"info", "note", "warning", "tip"}
    for i, bq in enumerate(soup.find_all("blockquote")):
        first_p = bq.find("p")
        first = first_p.contents[0] if first_p and first_p.contents else None
        if not (isinstance(first, Tag) and first.name == "strong"):
            continue
        label = first.get_text().strip()
        kind = label[:-1].strip().lower() if label.endswith(":") else None
        if kind not in panel_kinds:
            continue

        # Drop the label and the space that follows it, then serialise
        # the remaining blockquote content as the panel body.
        first.extract()
        if first_p.contents and isinstance(first_p.contents[0], NavigableString):
            first_p.contents[0].replace_with(soup.new_string(str(first_p.contents[0]).lstrip()))
        body_html = bq.decode_contents().strip()

        placeholder = f"\x00PANEL{i}\x00"
        macros[placeholder] = (
            f'<ac:structured-macro ac:name="{kind}">'
            f"<ac:rich-text-body>{body_html}</ac:rich-text-body>"
            f"</ac:structured-macro>"
        )
        bq.replace_with(placeholder)

    # -- Step 8: Serialise and substitute placeholders ------------------
    # Reverse insertion order so containers inserted later (panels) land
    # in the result before the placeholders nested inside them (code
    # blocks, images, task lists) are substituted.
    result = str(soup)
    for placeholder, macro in reversed(macros.items()):
        result = result.replace(placeholder, macro)
    return result


# ===================================================================
# Confluence --> Markdown conversion
# ===================================================================


def _heading_slug(text: str) -> str:
    """Convert heading text into a GitHub-style anchor slug.

    Used to generate #fragment links for the Table of Contents.
    The algorithm mirrors GitHub-Flavored Markdown: lowercase the text,
    strip non-word characters (except spaces and hyphens), then replace
    whitespace runs with single hyphens.

    Args:
        text: The plain-text content of a heading.

    Returns:
        A URL-safe slug string (e.g. "Getting Started" --> "getting-started").
    """
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"\s+", "-", slug).strip("-")


def _inline_md(el) -> str:
    """Recursively convert an HTML element's children to inline Markdown.

    Walks every child node of the given element and maps HTML inline
    tags to their Markdown equivalents:

        <strong>, <b>  -->  **text**
        <em>, <i>       -->  *text*
        <del>, <s>      -->  ~~text~~
        <code>          -->  text  (wrapped in single backticks at output)
        <a href="...">  -->  [text](url)
        <br>            -->  two trailing spaces + newline
        <p>, <div>      -->  text on its own line

    Any unrecognised tag is passed through -- only its inner text is kept.

    Args:
        el: A BeautifulSoup Tag whose children will be converted.

    Returns:
        A string of inline Markdown representing the element's content.
    """
    parts = []
    for child in el.children:
        if isinstance(child, NavigableString):
            # Plain text node -- keep as-is.
            parts.append(str(child))
        elif isinstance(child, Tag):
            # Recurse into the child tag first to build its inner content.
            inner = _inline_md(child)

            # Map the HTML tag to its Markdown equivalent.
            if child.name in ("strong", "b"):
                parts.append(f"**{inner}**")
            elif child.name in ("em", "i"):
                parts.append(f"*{inner}*")
            elif child.name in ("del", "s"):
                parts.append(f"~~{inner}~~")
            elif child.name == "code":
                parts.append(f"`{inner}`")
            elif child.name == "a":
                href = child.get("href", "")
                parts.append(f"[{inner}]({href})")
            elif child.name == "br":
                # Markdown line break: two trailing spaces + newline.
                parts.append("  \n")
            elif child.name in ("p", "div"):
                # A block inside an inline context (a table cell or list
                # item holding several paragraphs). Set it off with
                # newlines so consecutive paragraphs do not run together;
                # the caller decides what a newline becomes there.
                parts.append(f"\n{inner.strip()}\n")
            else:
                # Unknown inline tag -- just keep the inner text.
                parts.append(inner)
    # Adjacent blocks each contribute a newline; keep one between them.
    return re.sub(r"\n{2,}", "\n", "".join(parts))


def _render_list(el, indent: int = 0) -> list[str]:
    """Recursively render an HTML list (ul/ol) as Markdown lines.

    Handles nested lists by extracting child ul/ol elements from each
    li before converting the li's inline content, then recursing into
    the nested list with an increased indent level.

    Args:
        el: A BeautifulSoup Tag for a <ul> or <ol> element.
        indent: Current nesting depth (0 = top level). Each level adds
            two spaces of indentation to the list marker.

    Returns:
        A list of strings, one per Markdown line. Caller is responsible
        for joining them with newlines.
    """
    lines = []
    for li in el.find_all("li", recursive=False):
        # Choose the marker based on the parent list type.
        prefix = "  " * indent + ("-" if el.name == "ul" else "1.")

        # Check for nested lists inside this <li>. If found, extract them
        # from the tree BEFORE converting the li's inline content, so the
        # nested list text does not appear in the parent item. An <li> can
        # hold several sibling lists (e.g. a <ul> followed by an <ol>).
        nested_lists = li.find_all(["ul", "ol"], recursive=False)
        for nested in nested_lists:
            nested.extract()

        # Convert the remaining inline content of the <li> to Markdown.
        # An item holding several paragraphs spans several lines; indent
        # the continuation lines under the text so they stay in the item.
        continuation = "\n" + " " * (len(prefix) + 1)
        lines.append(f"{prefix} {_inline_md(li).strip().replace(chr(10), continuation)}")

        # Recurse into each nested list with one more indent level.
        for nested in nested_lists:
            lines.extend(_render_list(nested, indent + 1))
    return lines


def confluence_storage_to_md(
    storage_html: str, attachment_prefix: str = "", resolve_page_links: bool = False
) -> str:
    """Convert Confluence storage-format XHTML to a Markdown string.

    The conversion pipeline is:

        1. Replace Confluence "code" macros with fenced code blocks.
        2. Replace the "toc" macro with a null-byte placeholder (resolved
           at the end once all headings have been collected).
        3. Replace the "children" macro with a [CHILD_PAGES] marker
           (resolved later in cmd_download with real child page links).
        4. Replace internal page links (ac:link) with their visible text
           so the link label survives the cleanup step. With
           resolve_page_links, page links become confluence-page://
           placeholder links instead, resolved by the recursive download
           into relative file links.
        5. Replace panel macros (info, note, warning, tip, panel) with
           blockquotes carrying a bold label, so their content survives.
        6. Replace images (ac:image) with Markdown image syntax:
           attachment references point into attachment_prefix, external
           URL references keep their URL.
        7. Replace task lists (ac:task-list) with Markdown checkbox
           items (- [ ] / - [x]).
        8. Keep the content of the remaining ac: elements that merely
           wrap it (layouts, inline comment markers, unhandled macros
           with a rich-text body, ADF fallbacks), then remove what is
           left of the ac: and ri: namespaces.
        9. Unwrap generic block containers (div, section, ...) so the
           block elements they hold are met by the walk below.
        10. Walk top-level elements and convert each to Markdown:
            headings, paragraphs, lists, tables, blockquotes, hr, etc.
        11. If a TOC placeholder is present, build the table of contents
            from the collected headings and substitute it in.

    Args:
        storage_html: Raw Confluence storage-format XHTML string,
            typically from page["body"]["storage"]["value"].
        attachment_prefix: Path prefix (e.g. "My_Page_attachments/")
            prepended to attachment filenames in image links. The caller
            downloads the attachment files to that location.
        resolve_page_links: Emit page links as confluence-page://<title>
            placeholder links instead of plain text. Used by recursive
            downloads, which rewrite the placeholders into relative file
            links once the whole tree is on disk.

    Returns:
        A Markdown string representing the page content.
    """
    soup = BeautifulSoup(storage_html, "html.parser")

    # -- Step 1: Convert code macros to fenced code blocks -------------
    for macro in soup.find_all("ac:structured-macro", attrs={"ac:name": "code"}):
        # Extract the language parameter (e.g. "python", "bash").
        lang_tag = macro.find("ac:parameter", attrs={"ac:name": "language"})
        lang = lang_tag.get_text(strip=True) if lang_tag else ""

        # Extract the raw code text from the CDATA body.
        body = macro.find("ac:plain-text-body")
        code_text = body.get_text() if body else ""

        # Replace the macro with a plain-text fenced code block.
        macro.replace_with(soup.new_string(f"\n```{lang}\n{code_text}\n```\n"))

    # -- Step 2: Handle TOC macro --------------------------------------
    # Replace with a null-byte placeholder. After all headings are
    # collected in the element loop below, the placeholder is swapped
    # for a generated list of anchor links.
    has_toc = False
    for macro in soup.find_all("ac:structured-macro", attrs={"ac:name": "toc"}):
        has_toc = True
        macro.replace_with(soup.new_string("\x00TOC\x00"))

    # -- Step 3: Handle children macro ---------------------------------
    # Replace with the [CHILD_PAGES] text marker. cmd_download resolves
    # this into actual child page links by querying the API.
    for macro in soup.find_all("ac:structured-macro", attrs={"ac:name": "children"}):
        macro.replace_with(soup.new_string("[CHILD_PAGES]"))

    # -- Step 4: Convert internal page links to their visible text -----
    # <ac:link> wraps a resource identifier (ri:page, ri:user, ...) and
    # optionally a link body with the display text. A page ID is not
    # available here without extra API calls, so by default the link
    # degrades to its label rather than vanishing with the ac: cleanup.
    # With resolve_page_links, page links become placeholder links that
    # the recursive download rewrites into relative file links.
    for link in soup.find_all("ac:link"):
        body = link.find("ac:link-body") or link.find("ac:plain-text-link-body")
        text = body.get_text() if body else ""
        page_ref = link.find("ri:page")
        target_title = page_ref.get("ri:content-title", "") if page_ref else ""
        if not text:
            # No explicit body: fall back to the linked resource's title.
            ref = page_ref or link.find(["ri:attachment", "ri:user"])
            text = ref.get("ri:content-title", "") if ref else ""
        if resolve_page_links and target_title:
            link.replace_with(soup.new_string(f"[{text}](confluence-page://{quote(target_title)})"))
        else:
            link.replace_with(soup.new_string(text))

    # -- Step 5: Convert panel macros to blockquotes -------------------
    # Info / Note / Warning / Tip / Panel macros have no Markdown
    # equivalent. Degrade each to a blockquote with a bold label so the
    # content survives the download instead of being silently lost.
    panel_names = ["info", "note", "warning", "tip", "panel"]
    for macro in soup.find_all("ac:structured-macro", attrs={"ac:name": panel_names}):
        # Label: the panel's title parameter if set, else the macro kind.
        kind = macro.get("ac:name", "note").capitalize()
        title_tag = macro.find("ac:parameter", attrs={"ac:name": "title"})
        label = title_tag.get_text(strip=True) if title_tag else kind
        body = macro.find("ac:rich-text-body")

        strong = soup.new_tag("strong")
        strong.string = f"{label}:"
        bq = soup.new_tag("blockquote")

        # Prepend the label inside the first body paragraph when there is
        # one, so it renders as "> **Note:** text" on a single line.
        first_p = body.find("p", recursive=False) if body else None
        if first_p is not None:
            first_p.insert(0, soup.new_string(" "))
            first_p.insert(0, strong)
        else:
            label_p = soup.new_tag("p")
            label_p.append(strong)
            bq.append(label_p)
        if body:
            for child in list(body.children):
                bq.append(child.extract())
        macro.replace_with(bq)

    # -- Step 6: Convert images to Markdown image syntax ---------------
    # Attachment references become links into the attachments folder
    # (downloaded by cmd_download); external URL references keep their
    # URL. Anything else (e.g. user avatars) is dropped. The filename is
    # percent-encoded in the link: a space or parenthesis written raw
    # ends the link target early in every standard Markdown renderer.
    for image in soup.find_all("ac:image"):
        alt = image.get("ac:alt", "")
        attachment = image.find("ri:attachment")
        url = image.find("ri:url")
        if attachment is not None:
            filename = attachment.get("ri:filename", "")
            target = f"{attachment_prefix}{quote(filename)}"
            image.replace_with(soup.new_string(f"![{alt or filename}]({target})"))
        elif url is not None:
            image.replace_with(soup.new_string(f"![{alt}]({url.get('ri:value', '')})"))
        else:
            image.decompose()

    # -- Step 7: Convert task lists to Markdown checkbox items ---------
    # Each ac:task becomes "- [ ]" or "- [x]" depending on its status,
    # keeping the task body's inline formatting.
    for task_list in soup.find_all("ac:task-list"):
        task_lines = []
        for task in task_list.find_all("ac:task", recursive=False):
            status = task.find("ac:task-status")
            done = status is not None and status.get_text(strip=True) == "complete"
            body = task.find("ac:task-body")
            text = _inline_md(body).strip() if body else ""
            task_lines.append(f"- [{'x' if done else ' '}] {text}")
        task_list.replace_with(soup.new_string("\n" + "\n".join(task_lines) + "\n"))

    # -- Step 8: Unwrap, then remove, the remaining ac: / ri: elements --
    # Not every ac: element is a macro with no Markdown shape. Several
    # only *wrap* ordinary content, and removing them removed the content
    # too: a page laid out in columns downloaded as an empty file, an
    # expand macro vanished with everything inside it, and the text under
    # an inline comment disappeared mid-sentence. Keep what can be kept:
    #
    #   - an unhandled macro with a rich-text body (expand, excerpt, ...)
    #     becomes its body, preceded by its title in bold when it has one;
    #   - a macro with a title but no body (status, ...) becomes that
    #     title in bold, inline;
    #   - layouts, inline-comment markers and ADF fallbacks are unwrapped
    #     so their content falls through to the element walk below;
    #   - an emoticon becomes its emoji fallback text.
    #
    # Only then is the rest removed: parameters, plain-text bodies and
    # resource identifiers are macro plumbing with nothing to show.
    for macro in soup.find_all("ac:structured-macro"):
        body = macro.find("ac:rich-text-body")
        title_tag = macro.find("ac:parameter", attrs={"ac:name": "title"})
        title = title_tag.get_text(strip=True) if title_tag else ""
        if body is None and not title:
            continue  # nothing showable; removed below
        strong = None
        if title:
            strong = soup.new_tag("strong")
            strong.string = title
        if body is None:
            macro.replace_with(strong)
            continue
        if strong is not None:
            title_p = soup.new_tag("p")
            title_p.append(strong)
            macro.insert_before(title_p)
        for child in list(body.children):
            macro.insert_before(child.extract())
        macro.decompose()

    for ext in soup.find_all("ac:adf-extension"):
        fallback = ext.find("ac:adf-fallback")
        if fallback is None:
            ext.decompose()
            continue
        for child in list(fallback.children):
            ext.insert_before(child.extract())
        ext.decompose()

    for emoticon in soup.find_all("ac:emoticon"):
        fallback = emoticon.get("ac:emoji-fallback", "")
        if fallback:
            emoticon.replace_with(soup.new_string(fallback))
        else:
            emoticon.decompose()

    wrappers = ["ac:layout", "ac:layout-section", "ac:layout-cell", "ac:inline-comment-marker"]
    for wrapper in soup.find_all(wrappers):
        wrapper.unwrap()

    for tag in soup.find_all(re.compile(r"^(ac|ri):")):
        tag.decompose()

    # -- Step 9: Unwrap generic block containers ------------------------
    # Confluence wraps every table in <div class="table-wrap">, and
    # macros, templates and pasted HTML leave other <div>s behind. The
    # walk below only knows how to render the elements it meets at the
    # top level, so a wrapped table fell through to the inline fallback
    # and downloaded as its cell texts run together. Unwrapping first
    # puts the real block elements at the top level, where they render.
    # Nested containers unwrap too: find_all returns them innermost
    # last, and unwrap() on the outer one lifts whatever remains.
    for container in soup.find_all(["div", "section", "article", "main", "center"]):
        container.unwrap()

    # -- Step 10: Walk top-level elements and convert to Markdown ------
    lines = []  # Accumulates output Markdown lines.
    headings = []  # Collects (level, text) tuples for TOC generation.

    for el in soup.children:
        tag = getattr(el, "name", None)

        # NavigableString nodes (plain text, injected code blocks, or
        # placeholders). Keep non-empty ones as raw text.
        if tag is None:
            raw = str(el)
            if raw.strip():
                lines.append(raw)
            continue

        # Horizontal rules are void elements with no text content, so
        # they must be checked before the empty-text skip below.
        if tag == "hr":
            lines.append("---\n")
            continue

        # Skip elements that contain no visible text (e.g. empty <p>,
        # decorative <div> wrappers).
        text = el.get_text().strip()
        if not text:
            continue

        # --- Headings (h1 through h6) ---
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            heading_text = _inline_md(el).strip()
            # Track headings for TOC generation.
            headings.append((int(tag[1]), heading_text))
            lines.append(f"{'#' * int(tag[1])} {heading_text}\n")

        # --- Paragraphs ---
        elif tag == "p":
            lines.append(f"{_inline_md(el).strip()}\n")

        # --- Ordered and unordered lists ---
        elif tag in ("ul", "ol"):
            lines.extend(_render_list(el))
            lines.append("")  # Blank line after the list.

        # --- Tables ---
        elif tag == "table":
            rows = el.find_all("tr")
            for i, row in enumerate(rows):
                # Convert each cell's content to inline Markdown.
                # Escape pipe chars and newlines so they don't break
                # the Markdown table row structure.
                cells = [
                    _inline_md(c).strip().replace("\n", " ").replace("|", "\\|")
                    for c in row.find_all(["th", "td"])
                ]
                lines.append("| " + " | ".join(cells) + " |")

                # Always emit a separator after the first row. Markdown
                # tables require this line to render correctly.
                if i == 0:
                    lines.append("| " + " | ".join(["---"] * len(cells)) + " |")
            lines.append("")  # Blank line after the table.

        # --- Blockquotes ---
        elif tag == "blockquote":
            # Render each paragraph child on its own quoted line; fall
            # back to inline conversion for quotes with bare text.
            paragraphs = el.find_all("p", recursive=False)
            if paragraphs:
                bq = "\n".join(_inline_md(p).strip() for p in paragraphs)
            else:
                bq = _inline_md(el).strip()
            # Prefix every line with "> " for Markdown blockquote syntax.
            lines.append("\n".join(f"> {line}" for line in bq.split("\n")) + "\n")

        # --- Fallback for unknown elements ---
        else:
            # Extract whatever inline text we can and keep it.
            lines.append(_inline_md(el).strip())

    # -- Step 11: Generate the Table of Contents -----------------------
    # If a TOC macro was found, build a nested list of anchor links
    # from the headings collected during the element walk, then swap
    # it in for the null-byte placeholder.
    result = "\n".join(lines)
    if has_toc:
        toc_lines = []
        for level, heading_text in headings:
            # Indent by heading level (h1 = no indent, h2 = 2 spaces, etc.)
            # and generate a Markdown link to the heading anchor.
            toc_lines.append(
                "  " * (level - 1) + f"- [{heading_text}](#{_heading_slug(heading_text)})"
            )
        result = result.replace("\x00TOC\x00", "\n".join(toc_lines))
    return result


# ===================================================================
# CLI subcommands -- upload, edit, download
# ===================================================================


def attach_local_images(
    client: Confluence, page_id: str, md_file: str, image_paths: list[str]
) -> None:
    """Attach local image files referenced by a Markdown file to a page.

    Relative paths are resolved against the Markdown file's directory.
    Missing files are reported and skipped -- the page then shows a
    broken attachment reference for that image.

    Args:
        client: Authenticated Confluence client.
        page_id: ID of the page to attach the files to.
        md_file: Path of the Markdown file the images were referenced in.
        image_paths: Image paths exactly as written in the Markdown.
    """
    base = Path(md_file).resolve().parent
    for src in dict.fromkeys(image_paths):  # de-duplicate, keep order
        path = Path(src)
        if not path.is_absolute():
            path = base / path
        if not path.is_file():
            print(f"WARNING: image not found, skipped: {src}")
            continue
        api(client.attach_file, str(path), page_id=page_id)
        print(f"Attached image: {path.name}")


def split_leading_h1(md_text: str) -> tuple[str | None, str]:
    """Split a leading "# Title" heading off a Markdown string.

    "download" writes the page title as an h1 on the first content line;
    recursive upload reads it back as the page title and removes it so
    the heading is not duplicated inside the page body.

    Args:
        md_text: Markdown text (marker already stripped).

    Returns:
        A (title, remaining_text) tuple; title is None when the text does
        not start with an h1 heading.
    """
    m = re.match(r"\s*#\s+(.+?)\s*\n+", md_text)
    if not m:
        return None, md_text
    return m.group(1), md_text[m.end() :]


def sync_file(
    client: Confluence, md_file: Path, parent_id: str, space_key: str, force: bool
) -> str | None:
    """Create or update one Confluence page from a Markdown file.

    The page title comes from the file's leading h1 heading (falling back
    to the filename). Which page to touch is decided in order: a version
    marker wins (the file was downloaded from that page), then an existing
    page with the same title in the space, and otherwise a new child page
    is created under parent_id. Marker version conflicts are skipped with
    a warning unless force is set.

    Args:
        client: Authenticated Confluence client.
        md_file: Path of the .md file to upload.
        parent_id: Page ID the page belongs under when created.
        space_key: Key of the target space.
        force: Update even if the marker version does not match.

    Returns:
        The page ID the file maps to, or None when the file was skipped.
    """
    md_text, marker_page_id, marker_version = parse_version_marker(read_md(str(md_file)))
    h1_title, md_text = split_leading_h1(md_text)
    title = h1_title or md_file.stem.replace("_", " ")

    # Decide the target page: version marker first, then title lookup.
    page_id = None
    if marker_page_id:
        page = api(client.get_page_by_id, marker_page_id, expand="version")
        current_version = page.get("version", {}).get("number")
        if current_version is not None and current_version != marker_version and not force:
            print(
                f"WARNING: skipped '{md_file}': page changed on Confluence "
                f"(version {marker_version} -> {current_version}). Use --force to overwrite."
            )
            return marker_page_id
        page_id = marker_page_id
    else:
        existing = api(client.get_page_by_title, space_key, title)
        if existing:
            page_id = existing["id"]

    # Convert the body, collecting local image paths for attachment.
    image_paths: list[str] = []
    storage_body = md_to_confluence_storage(md_text, image_paths)

    if page_id:
        api(
            client.update_page,
            page_id=page_id,
            title=title,
            body=storage_body,
            representation="storage",
        )
        print(f"Updated '{title}' from {md_file}")
    else:
        result = api(
            client.create_page,
            space=space_key,
            title=title,
            body=storage_body,
            parent_id=parent_id,
            representation="storage",
        )
        page_id = result["id"]
        print(f"Created '{title}' from {md_file}")

    attach_local_images(client, page_id, str(md_file), image_paths)
    return page_id


def upload_tree(
    client: Confluence, dir_path: Path, parent_id: str, space_key: str, force: bool
) -> None:
    """Upload a folder of Markdown files as a Confluence page tree.

    Every "<name>.md" in dir_path becomes a page under parent_id; if a
    sibling folder "<name>/" exists, its files become children of that
    page, recursively -- the same layout "download --recursive" writes.
    Attachment folders ("*_attachments") are not treated as page folders.

    Args:
        client: Authenticated Confluence client.
        dir_path: Folder containing .md files.
        parent_id: Page ID the folder's pages belong under.
        space_key: Key of the target space.
        force: Update even when a file's marker version does not match.
    """
    for md_file in sorted(dir_path.glob("*.md")):
        page_id = sync_file(client, md_file, parent_id, space_key, force)
        sub_dir = md_file.with_name(md_file.stem)
        if page_id and sub_dir.is_dir():
            upload_tree(client, sub_dir, page_id, space_key, force)


def cmd_upload(args) -> None:
    """Create a new Confluence page from a local Markdown file.

    The page is created as a child of the parent page identified by the
    provided URL. If a page with the same title already exists in the
    space, the command aborts with an error and suggests using "edit".
    Local images referenced by the Markdown are uploaded as attachments.

    With --recursive, the file argument is a folder instead: every .md
    file in it becomes a page under the parent, with "<name>/" folders
    recursing as children of "<name>.md" -- the exact layout written by
    "download --recursive". Pages are created or updated as needed.

    Args:
        args: Parsed argparse namespace with attributes:
            file       -- Path to the local .md file (or folder with --recursive).
            parent_url -- URL of the parent Confluence page.
            title      -- Title for the new page (ignored with --recursive).
            recursive  -- Upload a folder as a page tree.
            force      -- Update even when a marker version does not match.
    """
    client = get_client()

    # Extract the parent page ID and space key from the URL.
    parent_id = api(page_id_from_url, args.parent_url)
    space_key = api(space_key_from_url, args.parent_url)

    # Recursive mode: the file argument is a folder to sync as a tree.
    if args.recursive:
        dir_path = Path(args.file)
        if not dir_path.is_dir():
            print(f"ERROR: Not a folder: {dir_path}")
            sys.exit(1)
        upload_tree(client, dir_path, parent_id, space_key, args.force)
        return

    if not args.title:
        print("ERROR: A title is required (unless using --recursive).")
        sys.exit(1)

    # Check for title collision before doing any file I/O.
    existing = api(client.get_page_by_title, space_key, args.title)
    if existing:
        existing_url = f"{CONFLUENCE_URL}/spaces/{space_key}/pages/{existing['id']}"
        print(f"ERROR: A page titled '{args.title}' already exists: {existing_url}")
        print("Use the 'edit' subcommand to replace its content.")
        sys.exit(1)

    # Read the Markdown file, dropping any version marker left over from
    # a download, and convert it to Confluence storage format, collecting
    # any local image paths for attachment upload.
    md_text, _, _ = parse_version_marker(read_md(args.file))
    image_paths: list[str] = []
    storage_body = md_to_confluence_storage(md_text, image_paths)

    # Create the page via the Confluence REST API.
    result = api(
        client.create_page,
        space=space_key,
        title=args.title,
        body=storage_body,
        parent_id=parent_id,
        representation="storage",
    )

    # Upload the referenced local images as attachments of the new page.
    attach_local_images(client, result["id"], args.file, image_paths)
    print(f"Created new page: {CONFLUENCE_URL}/spaces/{space_key}/pages/{result['id']}")


def cmd_edit(args) -> None:
    """Replace the body of an existing Confluence page from a Markdown file.

    Fetches the page metadata (to get the space key and current title),
    converts the local Markdown file to storage format, and pushes it
    as a new version of the page. The page history is preserved.

    If the Markdown file carries a version marker from "download" and the
    remote page has moved past that version, the command aborts so that
    someone else's edits are not silently overwritten. Pass --force to
    overwrite anyway.

    Args:
        args: Parsed argparse namespace with attributes:
            file     -- Path to the local .md file.
            page_url -- URL of the Confluence page to overwrite.
            title    -- Optional new title; keeps the existing one if None.
            force    -- Overwrite even if the remote version has changed.
    """
    client = get_client()

    # Read the Markdown file and split off the version marker (if any).
    md_text, marker_page_id, marker_version = parse_version_marker(read_md(args.file))

    # Fetch the existing page to get its space key, title and version.
    page = get_page(client, args.page_url, expand="space,version")
    title = args.title or page["title"]
    space_key = page["space"]["key"]
    page_id = page["id"]

    # Concurrent-edit guard: if this file was downloaded from the same
    # page, make sure nobody has edited the page since the download.
    if marker_version is not None and marker_page_id == page_id:
        current_version = page.get("version", {}).get("number")
        if current_version is not None and current_version != marker_version and not args.force:
            print(
                f"ERROR: The page has changed on Confluence since it was downloaded "
                f"(version {marker_version} -> {current_version})."
            )
            print("Someone else's edits would be overwritten.")
            print("Re-download the page and merge your changes, or pass --force to overwrite.")
            sys.exit(1)

    # When renaming, make sure the new title is not already taken by a
    # different page in the space -- the API would reject the update with
    # an opaque error otherwise.
    if args.title and args.title != page["title"]:
        existing = api(client.get_page_by_title, space_key, args.title)
        if existing and existing["id"] != page_id:
            existing_url = f"{CONFLUENCE_URL}/spaces/{space_key}/pages/{existing['id']}"
            print(f"ERROR: A page titled '{args.title}' already exists: {existing_url}")
            print("Choose a different --title.")
            sys.exit(1)

    # Convert the (marker-free) Markdown to Confluence storage format,
    # collecting any local image paths for attachment upload.
    image_paths: list[str] = []
    storage_body = md_to_confluence_storage(md_text, image_paths)

    # Push the new content as the next version of the page.
    api(
        client.update_page,
        page_id=page_id,
        title=title,
        body=storage_body,
        representation="storage",
    )

    # Upload the referenced local images as attachments of the page.
    # Re-attaching an existing filename creates a new attachment version.
    attach_local_images(client, page_id, args.file, image_paths)
    print(f"Replaced content of '{title}': {CONFLUENCE_URL}/spaces/{space_key}/pages/{page_id}")


def safe_filename(title: str) -> str:
    """Turn a page title into a filesystem-safe filename stem.

    Strips special characters, collapses whitespace into underscores and
    removes leading/trailing underscores.

    Args:
        title: The Confluence page title.

    Returns:
        A safe filename stem (falls back to "page" for empty results).
    """
    return re.sub(r"\s+", "_", re.sub(r"[^\w\s-]", "", title)).strip("_") or "page"


def unique_filename(stem: str, used: set[str]) -> str:
    """Make a filename stem unique among the ones already used in a folder.

    safe_filename() is lossy: "Setup: A" and "Setup A" both become
    "Setup_A", and "Q&A" and "QA" become "QA". Two sibling pages with
    such titles would be written to the same path, the second silently
    overwriting the first. The first keeps the plain stem; later ones get
    a numeric suffix ("Setup_A_2", "Setup_A_3", ...). Comparison is
    case-insensitive because the common desktop filesystems are.

    Args:
        stem: Candidate filename stem, as returned by safe_filename().
        used: Stems already taken in the folder, lowercased. The chosen
            stem is added to it.

    Returns:
        The stem itself, or the stem with the lowest free numeric suffix.
    """
    candidate = stem
    counter = 2
    while candidate.lower() in used:
        candidate = f"{stem}_{counter}"
        counter += 1
    used.add(candidate.lower())
    return candidate


def get_child_pages(client: Confluence, page_id: str) -> list[dict]:
    """Fetch all direct child pages of a page, following pagination.

    Args:
        client: Authenticated Confluence client.
        page_id: ID of the parent page.

    Returns:
        A list of child page resource dicts (possibly empty).
    """
    children: list[dict] = []
    start = 0
    limit = 50
    while True:
        batch = api(client.get_page_child_by_type, page_id, type="page", start=start, limit=limit)
        # The API may return a dict with "results" or a plain list,
        # depending on the atlassian-python-api version.
        batch = batch.get("results", []) if isinstance(batch, dict) else (batch or [])
        children.extend(batch)
        if len(batch) < limit:
            return children
        start += limit


def _rewrite_page_links(tree: dict) -> None:
    """Resolve confluence-page:// placeholders in a downloaded tree.

    Placeholder links whose target title was downloaded become relative
    file links; links to pages outside the tree fall back to their label.

    Args:
        tree: Dict with "paths" (title -> Path of the written file) and
            "files" (all written Paths), built during the recursion.
    """
    placeholder_re = re.compile(r"\[([^\]]*)\]\(confluence-page://([^)]+)\)")
    for md_file in tree["files"]:
        text = md_file.read_text(encoding="utf-8")

        def resolve(m, _from=md_file):
            target = tree["paths"].get(unquote(m.group(2)))
            if target is None:
                return m.group(1)  # outside the tree: keep the label only
            rel = Path(os.path.relpath(target, start=_from.parent)).as_posix()
            return f"[{m.group(1)}]({rel})"

        new_text = placeholder_re.sub(resolve, text)
        if new_text != text:
            md_file.write_text(new_text, encoding="utf-8")


def download_page(
    client: Confluence,
    page: dict,
    out_path: Path,
    recursive: bool = False,
    _tree: dict | None = None,
) -> None:
    """Write one fetched Confluence page to disk as Markdown.

    Converts the page body, resolves [CHILD_PAGES] markers into links,
    downloads referenced image attachments into a "<name>_attachments/"
    folder, and writes the file with a version marker. With recursive=True,
    child pages are downloaded into a "<name>/" folder next to the file,
    each going through this same function; links between pages of the
    downloaded tree are rewritten into relative file links at the end.

    Args:
        client: Authenticated Confluence client.
        page: Page resource dict (expanded with body.storage, space, version).
        out_path: Path of the Markdown file to write.
        recursive: Also download all descendant pages.
        _tree: Internal recursion state (title -> path map and file list);
            leave unset when calling.
    """
    is_root = recursive and _tree is None
    if is_root:
        _tree = {"paths": {}, "files": []}

    title = page["title"]
    page_id = page["id"]
    space_key = page["space"]["key"]
    version = page.get("version", {}).get("number")
    att_dir = out_path.with_name(f"{out_path.stem}_attachments")

    # Convert the Confluence storage format XHTML to Markdown. Image
    # links to attachments point into the attachments folder. In
    # recursive mode, page links become placeholders resolved after the
    # whole tree is on disk.
    md_text = confluence_storage_to_md(
        page["body"]["storage"]["value"],
        attachment_prefix=f"{att_dir.name}/",
        resolve_page_links=recursive,
    )

    # Fetch the child page list once if anything below needs it.
    children = get_child_pages(client, page_id) if recursive or "[CHILD_PAGES]" in md_text else []

    # Resolve [CHILD_PAGES] markers into a Markdown list of links.
    if "[CHILD_PAGES]" in md_text:
        child_lines = []
        for child in children:
            child_url = f"{CONFLUENCE_URL}/spaces/{space_key}/pages/{child['id']}"
            child_lines.append(f"- [{child['title']}]({child_url})")
        md_text = md_text.replace("[CHILD_PAGES]", "\n".join(child_lines))

    # Download the attachments referenced by image links into the
    # attachments folder, matching them to the page's attachments by name.
    # The links carry the names percent-encoded; decode them first.
    referenced = [
        unquote(name)
        for name in re.findall(rf"!\[[^\]]*\]\({re.escape(att_dir.name)}/([^)]+)\)", md_text)
    ]
    if referenced:
        attachments = api(client.get_attachments_from_content, page_id, limit=250)
        by_title = {a["title"]: a for a in attachments.get("results", [])}
        att_dir.mkdir(parents=True, exist_ok=True)
        saved = 0
        for name in dict.fromkeys(referenced):
            attachment = by_title.get(name)
            if not attachment:
                print(f"WARNING: attachment not found on page, skipped: {name}")
                continue
            content = api(client.get, attachment["_links"]["download"], not_json_response=True)
            (att_dir / Path(name).name).write_bytes(content)
            saved += 1
        print(f"Downloaded {saved} attachment(s) -> {att_dir}/")

    # Write the Markdown file with a version marker (used by "edit" to
    # detect concurrent changes) and the page title as an h1 header.
    marker = f"<!-- confluence-md page_id={page_id} version={version} -->\n" if version else ""
    out_path.write_text(f"{marker}# {title}\n\n{md_text}", encoding="utf-8")
    print(f"Downloaded '{title}' -> {out_path}")

    # Track written files so page links can be resolved tree-wide.
    if recursive:
        _tree["paths"][title] = out_path
        _tree["files"].append(out_path)

    # Recurse into child pages, mirroring the page tree as a folder tree.
    if recursive and children:
        sub_dir = out_path.with_name(out_path.stem)
        sub_dir.mkdir(parents=True, exist_ok=True)
        used_stems: set[str] = set()
        for child in children:
            child_page = api(
                client.get_page_by_id, child["id"], expand="body.storage,space,version"
            )
            stem = unique_filename(safe_filename(child_page["title"]), used_stems)
            child_path = sub_dir / f"{stem}.md"
            download_page(client, child_page, child_path, recursive=True, _tree=_tree)

    # Once the whole tree is on disk, resolve inter-page links.
    if is_root:
        _rewrite_page_links(_tree)


def cmd_download(args) -> None:
    """Download a Confluence page and save it as a local Markdown file.

    Fetches the page body in storage format, converts it to Markdown,
    and writes it to disk. If the page contained a "children" macro,
    the child pages are fetched from the API and rendered as a list
    of Markdown links. Images referencing page attachments are saved
    into a "<name>_attachments/" folder next to the output file.

    With --recursive, all descendant pages are downloaded too: each
    page's children go into a "<name>/" folder next to its file, so the
    folder tree mirrors the page tree.

    The output filename defaults to a sanitised version of the page title
    if not explicitly provided.

    Args:
        args: Parsed argparse namespace with attributes:
            page_url  -- URL of the Confluence page to download.
            output    -- Optional output file path (defaults to title-based name).
            recursive -- Also download all descendant pages.
    """
    client = get_client()

    # Fetch the page with its storage body, space and version metadata.
    page = get_page(client, args.page_url, expand="body.storage,space,version")

    # Determine the output file path -- the attachments folder and the
    # children folder are both named after it.
    out_path = Path(args.output) if args.output else Path(f"{safe_filename(page['title'])}.md")

    download_page(client, page, out_path, recursive=args.recursive)


# ===================================================================
# CLI entry point -- argument parsing and subcommand dispatch
# ===================================================================


def main() -> None:
    """Parse command-line arguments and dispatch to the appropriate subcommand.

    Defines three subcommands (upload, edit, download), each with its
    own set of positional and optional arguments. Uses argparse
    set_defaults to bind each subparser to its handler function.
    """
    parser = argparse.ArgumentParser(description="Manage Confluence pages from the command line.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(required=True)

    # -- upload subcommand ---------------------------------------------
    up = sub.add_parser("upload", help="Create a new child page from a .md file")
    up.add_argument("file", help="Path to the .md file (or a folder with --recursive)")
    up.add_argument("parent_url", help="URL of the parent Confluence page")
    up.add_argument(
        "title", nargs="?", help="Title for the new Confluence page (ignored with --recursive)"
    )
    up.add_argument(
        "--recursive",
        action="store_true",
        help="Upload a folder of .md files as a page tree (layout of download --recursive)",
    )
    up.add_argument(
        "--force",
        action="store_true",
        help="With --recursive: update even if a page changed on Confluence since download",
    )
    up.set_defaults(func=cmd_upload)

    # -- edit subcommand -----------------------------------------------
    ed = sub.add_parser("edit", help="Replace the content of an existing page from a .md file")
    ed.add_argument("file", help="Path to the .md file")
    ed.add_argument("page_url", help="URL of the Confluence page to overwrite")
    ed.add_argument("--title", help="Rename the page at the same time (optional)")
    ed.add_argument(
        "--force",
        action="store_true",
        help="Overwrite even if the page changed on Confluence since it was downloaded",
    )
    ed.set_defaults(func=cmd_edit)

    # -- download subcommand -------------------------------------------
    dl = sub.add_parser("download", help="Download a Confluence page as a .md file")
    dl.add_argument("page_url", help="URL of the Confluence page")
    dl.add_argument("output", nargs="?", help="Output file path (defaults to page title)")
    dl.add_argument(
        "--recursive",
        action="store_true",
        help="Also download all child pages into a folder named after the page",
    )
    dl.set_defaults(func=cmd_download)

    # Dispatch to the selected subcommand handler.
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
