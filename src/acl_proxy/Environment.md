# Environment Variables (App Settings)

This document outlines the required environment variables to configure the Azure Functions proxy (`mcp.asisaga.com`) for GitHub MCP access and server-side ACL enforcement.

---

## Required Settings

- `GITHUB_MCP_PAT`  
  A GitHub Personal Access Token with at least `repo` and `read:packages` scopes.  
  Used to authenticate requests forwarded to GitHub’s MCP server.

- `MCP_OWNER`  
  The GitHub username or organization that owns the target data repository.  
  Example: `ASISaga`

- `MCP_REPO`  
  The name of the data repository you’re proxying.  
  Example: `Manas`

- `ACL_READ_ONLY`  
  A comma-delimited list of glob patterns specifying which files or folders are readable.  
  Example:

---

## How to Apply

1. In the Azure Portal, navigate to your Function App → **Configuration**.
2. Under **Application settings**, click **New application setting** for each variable above.
3. Enter the **Name** and **Value** exactly as shown.
4. Save changes and restart your Function App to apply the new settings.