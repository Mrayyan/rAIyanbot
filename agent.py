"""
ML Agent — Simple agent loop with local tools + MCP server support.
Run: python agent.py
Make sure ANTHROPIC_API_KEY is set in your environment.
"""

import os
import sys
import json
import subprocess
import tempfile
import urllib.request
import urllib.parse
import asyncio
import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# --- Configuration ---
MODEL = "claude-sonnet-4-20250514"
SYSTEM_PROMPT = """You are a software engineer assistant. You can write and execute Python code.

Rules:
- Be concise in your responses.
- When asked to write code, use edit_file to save it, then execute_python to run it.
- Always show the user the output of executed code.
- If code has errors, debug and retry.
- When the task is complete, say so clearly.
- Use web_search when you need current information you don't know.
- Use read_file and list_directory to explore existing files.
"""

# --- Local Tool Definitions (JSON schema for Claude) ---
LOCAL_TOOLS = [
    {
        "name": "execute_python",
        "description": "Execute Python code and return the output. Use this to run scripts or test code.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The Python code to execute."
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "edit_file",
        "description": "Create or overwrite a file with the given content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to write to."
                },
                "content": {
                    "type": "string",
                    "description": "The content to write into the file."
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "web_search",
        "description": "Search the web and return top results. Use when you need current or factual information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query."
                }
            },
            "required": ["query"]
        }
    }
]


# --- Local Tool Implementations ---
def execute_python(code: str) -> str:
    """Run Python code in a subprocess and return stdout + stderr."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        f.flush()
        tmp_path = f.name
    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True, text=True, timeout=30
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"
        return output.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return "ERROR: Code execution timed out (30s limit)."
    finally:
        os.unlink(tmp_path)


def edit_file(path: str, content: str) -> str:
    """Write content to a file."""
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return f"File written: {path} ({len(content)} chars)"
    except Exception as e:
        return f"ERROR writing file: {e}"


def web_search(query: str) -> str:
    """Search the web using DuckDuckGo's instant answer API."""
    try:
        params = urllib.parse.urlencode({"q": query, "format": "json", "no_html": "1"})
        url = f"https://api.duckduckgo.com/?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "MLAgent/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        results = []
        if data.get("AbstractText"):
            results.append(f"Summary: {data['AbstractText']}")
            if data.get("AbstractSource"):
                results.append(f"Source: {data['AbstractSource']}")
        for topic in data.get("RelatedTopics", [])[:5]:
            if isinstance(topic, dict) and "Text" in topic:
                results.append(f"- {topic['Text']}")
        return "\n".join(results) if results else f"No instant results for '{query}'."
    except Exception as e:
        return f"Search error: {e}"


def run_local_tool(name: str, input_data: dict) -> str:
    """Dispatch a local tool call."""
    if name == "execute_python":
        return execute_python(input_data["code"])
    elif name == "edit_file":
        return edit_file(input_data["path"], input_data["content"])
    elif name == "web_search":
        return web_search(input_data["query"])
    return None


# --- The Agent Loop (async for MCP support) ---
async def agent_loop():
    client = anthropic.Anthropic()

    # Connect to MCP server
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["mcp_server.py"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as mcp_session:
            await mcp_session.initialize()

            # Discover MCP tools and convert to Claude's format
            mcp_tools_response = await mcp_session.list_tools()
            mcp_tool_names = set()
            mcp_tools_for_claude = []
            for tool in mcp_tools_response.tools:
                mcp_tool_names.add(tool.name)
                mcp_tools_for_claude.append({
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema,
                })

            # Combine local + MCP tools
            all_tools = LOCAL_TOOLS + mcp_tools_for_claude
            print(f"  Local tools: {[t['name'] for t in LOCAL_TOOLS]}")
            print(f"  MCP tools:   {list(mcp_tool_names)}")

            messages = []
            print("=" * 50)
            print("  ML Agent — Type a task, or 'quit' to exit")
            print("=" * 50)

            while True:
                try:
                    user_input = input("\nYou: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nBye!")
                    break

                if not user_input:
                    continue
                if user_input.lower() in ("quit", "exit", "q"):
                    print("Bye!")
                    break

                messages.append({"role": "user", "content": user_input})

                # Inner loop: keep going until Claude stops calling tools
                while True:
                    response = client.messages.create(
                        model=MODEL,
                        max_tokens=4096,
                        system=SYSTEM_PROMPT,
                        tools=all_tools,
                        messages=messages,
                    )

                    assistant_content = response.content
                    messages.append({"role": "assistant", "content": assistant_content})

                    tool_calls = [b for b in assistant_content if b.type == "tool_use"]

                    for block in assistant_content:
                        if hasattr(block, "text"):
                            print(f"\nAgent: {block.text}")

                    if not tool_calls:
                        break

                    tool_results = []
                    for tc in tool_calls:
                        print(f"\n  [Tool: {tc.name}]")

                        # Route to local or MCP
                        if tc.name in mcp_tool_names:
                            mcp_result = await mcp_session.call_tool(tc.name, tc.input)
                            result = mcp_result.content[0].text if mcp_result.content else "(no output)"
                        else:
                            result = run_local_tool(tc.name, tc.input)
                            if result is None:
                                result = f"Unknown tool: {tc.name}"

                        print(f"  [Result: {result[:200]}{'...' if len(result) > 200 else ''}]")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tc.id,
                            "content": result,
                        })

                    messages.append({"role": "user", "content": tool_results})


if __name__ == "__main__":
    asyncio.run(agent_loop())
