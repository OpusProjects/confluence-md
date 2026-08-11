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
    python src/confluence_md.py edit     <file.md> <page_url>   [--title "..."]
    python src/confluence_md.py download <page_url>             [output.md]
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
        6. Substitute all placeholders back into the serialised HTML.

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
            if image_paths is not None:
                image_paths.append(src)
            filename = Path(src).name
            macros[placeholder] = (
                f'<ac:image ac:alt="{html.escape(alt)}">'
                f'<ri:attachment ri:filename="{html.escape(filename)}" /></ac:image>'
            )
        img.replace_with(placeholder)

    # -- Step 6: Serialise and substitute placeholders ------------------
    result = str(soup)
    for placeholder, macro in macros.items():
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
            else:
                # Unknown inline tag -- just keep the inner text.
                parts.append(inner)
    return "".join(parts)


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
        lines.append(f"{prefix} {_inline_md(li).strip()}")

        # Recurse into each nested list with one more indent level.
        for nested in nested_lists:
            lines.extend(_render_list(nested, indent + 1))
    return lines


def confluence_storage_to_md(storage_html: str, attachment_prefix: str = "") -> str:
    """Convert Confluence storage-format XHTML to a Markdown string.

    The conversion pipeline is:

        1. Replace Confluence "code" macros with fenced code blocks.
        2. Replace the "toc" macro with a null-byte placeholder (resolved
           at the end once all headings have been collected).
        3. Replace the "children" macro with a [CHILD_PAGES] marker
           (resolved later in cmd_download with real child page links).
        4. Replace internal page links (ac:link) with their visible text
           so the link label survives the cleanup step.
        5. Replace panel macros (info, note, warning, tip, panel) with
           blockquotes carrying a bold label, so their content survives.
        6. Replace images (ac:image) with Markdown image syntax:
           attachment references point into attachment_prefix, external
           URL references keep their URL.
        7. Decompose (remove) all remaining ac: and ri: namespaced
           elements that have no Markdown equivalent.
        8. Walk top-level elements and convert each to Markdown:
           headings, paragraphs, lists, tables, blockquotes, hr, etc.
        9. If a TOC placeholder is present, build the table of contents
           from the collected headings and substitute it in.

    Args:
        storage_html: Raw Confluence storage-format XHTML string,
            typically from page["body"]["storage"]["value"].
        attachment_prefix: Path prefix (e.g. "My_Page_attachments/")
            prepended to attachment filenames in image links. The caller
            downloads the attachment files to that location.

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
    # available here without extra API calls, so the link degrades to
    # its label rather than vanishing with the rest of the ac: cleanup.
    for link in soup.find_all("ac:link"):
        body = link.find("ac:link-body") or link.find("ac:plain-text-link-body")
        text = body.get_text() if body else ""
        if not text:
            # No explicit body: fall back to the linked page's title.
            ref = link.find(["ri:page", "ri:attachment", "ri:user"])
            text = ref.get("ri:content-title", "") if ref else ""
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
    # URL. Anything else (e.g. user avatars) is dropped.
    for image in soup.find_all("ac:image"):
        alt = image.get("ac:alt", "")
        attachment = image.find("ri:attachment")
        url = image.find("ri:url")
        if attachment is not None:
            filename = attachment.get("ri:filename", "")
            image.replace_with(
                soup.new_string(f"![{alt or filename}]({attachment_prefix}{filename})")
            )
        elif url is not None:
            image.replace_with(soup.new_string(f"![{alt}]({url.get('ri:value', '')})"))
        else:
            image.decompose()

    # -- Step 7: Remove all remaining Confluence-specific elements -----
    # ac: elements are structured macros and their sub-elements.
    # ri: elements are resource identifiers (e.g. for attachments).
    # Neither has a Markdown equivalent.
    for tag in soup.find_all(re.compile(r"^(ac|ri):")):
        tag.decompose()

    # -- Step 8: Walk top-level elements and convert to Markdown -------
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

    # -- Step 9: Generate the Table of Contents ------------------------
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


def cmd_upload(args) -> None:
    """Create a new Confluence page from a local Markdown file.

    The page is created as a child of the parent page identified by the
    provided URL. If a page with the same title already exists in the
    space, the command aborts with an error and suggests using "edit".
    Local images referenced by the Markdown are uploaded as attachments.

    Args:
        args: Parsed argparse namespace with attributes:
            file       -- Path to the local .md file.
            parent_url -- URL of the parent Confluence page.
            title      -- Title for the new page.
    """
    client = get_client()

    # Extract the parent page ID and space key from the URL.
    parent_id = api(page_id_from_url, args.parent_url)
    space_key = api(space_key_from_url, args.parent_url)

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


def cmd_download(args) -> None:
    """Download a Confluence page and save it as a local Markdown file.

    Fetches the page body in storage format, converts it to Markdown,
    and writes it to disk. If the page contained a "children" macro,
    the child pages are fetched from the API and rendered as a list
    of Markdown links. Images referencing page attachments are saved
    into a "<name>_attachments/" folder next to the output file.

    The output filename defaults to a sanitised version of the page title
    if not explicitly provided.

    Args:
        args: Parsed argparse namespace with attributes:
            page_url -- URL of the Confluence page to download.
            output   -- Optional output file path (defaults to title-based name).
    """
    client = get_client()

    # Fetch the page with its storage body, space and version metadata.
    page = get_page(client, args.page_url, expand="body.storage,space,version")
    title = page["title"]
    page_id = page["id"]
    space_key = page["space"]["key"]
    version = page.get("version", {}).get("number")

    # Determine the output file path first -- the attachments folder is
    # named after it and image links must point there.
    if args.output:
        out_path = Path(args.output)
    else:
        # Derive a safe filename from the page title: strip special chars,
        # collapse whitespace into underscores, remove leading/trailing underscores.
        safe_title = re.sub(r"\s+", "_", re.sub(r"[^\w\s-]", "", title)).strip("_")
        out_path = Path(f"{safe_title}.md")
    att_dir = out_path.with_name(f"{out_path.stem}_attachments")

    # Convert the Confluence storage format XHTML to Markdown. Image
    # links to attachments point into the attachments folder.
    md_text = confluence_storage_to_md(
        page["body"]["storage"]["value"], attachment_prefix=f"{att_dir.name}/"
    )

    # Resolve [CHILD_PAGES] markers by fetching actual child pages from
    # the API and rendering them as a Markdown list of links.
    if "[CHILD_PAGES]" in md_text:
        children = api(client.get_page_child_by_type, page_id, type="page")

        # The API may return a dict with "results" or a plain list,
        # depending on the atlassian-python-api version.
        child_list = children.get("results", []) if isinstance(children, dict) else (children or [])

        # Build a Markdown bullet list with each child as a link.
        child_lines = []
        for child in child_list:
            child_url = f"{CONFLUENCE_URL}/spaces/{space_key}/pages/{child['id']}"
            child_lines.append(f"- [{child['title']}]({child_url})")
        md_text = md_text.replace("[CHILD_PAGES]", "\n".join(child_lines))

    # Download the attachments referenced by image links into the
    # attachments folder, matching them to the page's attachments by name.
    referenced = re.findall(rf"!\[[^\]]*\]\({re.escape(att_dir.name)}/([^)]+)\)", md_text)
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
    up.add_argument("file", help="Path to the .md file")
    up.add_argument("parent_url", help="URL of the parent Confluence page")
    up.add_argument("title", help="Title for the new Confluence page")
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
    dl.set_defaults(func=cmd_download)

    # Dispatch to the selected subcommand handler.
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
