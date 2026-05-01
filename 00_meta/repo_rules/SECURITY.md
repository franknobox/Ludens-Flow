# Security

Ludens-Flow can touch local files, workspace paths, MCP commands, model credentials, and Agent write permissions. Treat these areas as security-sensitive.

## Please Report Privately

Report these issues privately when possible:

- path traversal or workspace boundary bypass
- unexpected file creation, modification, or deletion outside approved workspaces
- unsafe MCP command execution
- API key or `.env` leakage
- permission bypass in Agent tool execution

## What To Include

- affected version or commit
- reproduction steps
- expected behavior and actual behavior
- whether local files, credentials, or external commands were involved

## Do Not Share Publicly

Do not paste API keys, `.env` contents, private project files, or sensitive local paths into public issues.

## Current Status

Ludens-Flow is an early-stage local development workbench. It should not be treated as a production-grade sandbox.
