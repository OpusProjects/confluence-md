# Configuration

Everything needed to get from a fresh clone to a working setup: install the
dependencies, generate an API token, and store the credentials in a `.env` file.

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [1. Create an Atlassian API token](#1-create-an-atlassian-api-token)
- [2. Find your Confluence URL](#2-find-your-confluence-url)
- [3. Set up the `.env` file](#3-set-up-the-env-file)

## Prerequisites

The tool only needs a recent Python and its package manager; everything else
is installed in the next step.

- Python 3.10+
- pip

## Installation

Install the four runtime dependencies with a single pip command:

```bash
pip install -r src/requirements.txt
```

This installs the four dependencies: `atlassian-python-api`, `python-dotenv`,
`markdown` and `beautifulsoup4`.

## 1. Create an Atlassian API token

The script authenticates with an API token rather than your password.
Atlassian Cloud does **not** allow authentication with your regular password.

1. Go to [https://id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Log in with your Atlassian account
3. Click **Create API token**
4. Give it a descriptive label (e.g. `confluence-md`)
5. Click **Create** and **copy the token immediately** (it will not be shown again)

## 2. Find your Confluence URL

The base URL identifies your organisation's Confluence Cloud instance and
follows this pattern:

```
https://<your-org>.atlassian.net/wiki
```

You can find it in your browser address bar when you open Confluence.

## 3. Set up the `.env` file

The three credentials live in a `.env` file that the script loads at startup.
Copy the template from the project root and fill in your values:

```bash
cp .env.example .env
```

```env
CONFLUENCE_URL=https://<your-org>.atlassian.net/wiki
CONFLUENCE_EMAIL=your.email@company.com
CONFLUENCE_API_TOKEN=your-api-token-here
```

| Variable | Description |
|---|---|
| `CONFLUENCE_URL` | Base URL of your Confluence Cloud instance (ending with `/wiki`) |
| `CONFLUENCE_EMAIL` | Email address associated with your Atlassian account |
| `CONFLUENCE_API_TOKEN` | The API token generated in step 1 |

> **Never commit the `.env` file to version control.** It is already listed in
> this repository's `.gitignore`.
