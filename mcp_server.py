"""
MCP Server — Exposes filesystem tools (read_file, list_directory) via MCP protocol.
This runs as a subprocess — the agent starts it and talks to it over stdin/stdout.
"""

import os
from mcp.server.fastmcp import FastMCP

# Create the MCP server
mcp = FastMCP("filesystem-tools")


@mcp.tool()
def read_file(path: str) -> str:
    """Read the contents of a file and return it as text."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if len(content) > 10000:
            return content[:10000] + f"\n... (truncated, file is {len(content)} chars)"
        return content
    except Exception as e:
        return f"Error reading file: {e}"


@mcp.tool()
def list_directory(path: str = ".") -> str:
    """List files and directories at the given path."""
    try:
        entries = os.listdir(path)
        result = []
        for entry in sorted(entries):
            full = os.path.join(path, entry)
            if os.path.isdir(full):
                result.append(f"[DIR]  {entry}/")
            else:
                size = os.path.getsize(full)
                result.append(f"[FILE] {entry} ({size} bytes)")
        return "\n".join(result) if result else "(empty directory)"
    except Exception as e:
        return f"Error listing directory: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
