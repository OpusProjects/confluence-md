# Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `ERROR: Set CONFLUENCE_URL ...` | `.env` file missing or incomplete | Ensure all three variables are set in `.env` |
| `403 FORBIDDEN` | Wrong email, invalid token, or insufficient permissions | Verify your email and regenerate the API token |
| `401 Unauthorized` | Expired or incorrect API token | Generate a new token |
| `Cannot extract page ID from URL` | The URL format is not recognised | Use the full browser URL of the page, not a shortened or redirected link |
| `ERROR: Page not found` | The page ID does not exist or you lack view permissions | Check the URL and your account's space permissions |
| `ERROR: File not found` | The local `.md` file path is wrong | Check the path and working directory |
| `ERROR: A page titled '...' already exists` | `upload` found an existing page with the same title, or `edit --title` would rename onto an existing page | For `upload`: use `edit` with that page's URL. For `edit`: choose a different `--title` |
