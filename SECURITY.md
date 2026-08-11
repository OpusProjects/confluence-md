# Security Policy

## Supported versions

Only the latest release line receives security fixes.

| Version | Supported |
|---|---|
| 0.x (latest release) | Yes |
| older tags | No |

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Use GitHub's private vulnerability reporting instead:
[Report a vulnerability](https://github.com/OpusProjects/confluence-md/security/advisories/new)
— it opens a private thread with the maintainers.

Include what you can: affected subcommand or conversion path, reproduction
steps, and impact. You should hear back within a week. Once a fix ships, the
advisory is published and credited unless you prefer otherwise.

## Scope notes

- The Atlassian API token in `.env` authenticates as **your full account** —
  anyone who reads that file can act as you on every space you can reach.
  `.gitignore` excludes it; keep it that way and rotate the token if it leaks.
- The script runs **with your local user's privileges** and writes downloaded
  pages to the working directory. Page titles drive the default output
  filename; a hostile page title is sanitised, but review what you download
  from spaces you do not control.
- Markdown is uploaded **without sanitisation** — raw HTML in a Markdown file
  is passed through to the page body. Only upload files you trust to spaces
  you are authorised to edit.
