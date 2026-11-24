# Claude Desktop MCP configuration

Add this entry to Claude Desktop's MCP configuration:

```json
{
  "mcpServers": {
    "superloop-help-agent": {
      "command": "C:\\dev\\superloop-help-agent\\.venv\\Scripts\\python.exe",
      "args": [
        "C:\\dev\\superloop-help-agent\\src\\mcp_server.py"
      ],
      "cwd": "C:\\dev\\superloop-help-agent"
    }
  }
}
```

This exposes the read-only help search, allow-listed article retrieval and synthetic account lookup tools. The MCP server runs over stdio.
