"""
Multi-Agent ML Pipeline — 3 agents working together (PiML-inspired).
  Main Agent:    plans and writes code
  Summary Agent: compresses observations into short feedback
  Debug Agent:   fixes code errors

Run: python agent_multi.py
"""

import os
import sys
import json
import subprocess
import tempfile
import urllib.request
import urllib.parse
import anthropic

MODEL = "claude-sonnet-4-20250514"

# --- Each agent gets its own focused prompt ---

MAIN_AGENT_PROMPT = """You are the Main Agent — an ML engineer that plans and writes code.

You receive a task and a memory of past steps (if any). Your job:
1. Think about what to do next (state your reasoning briefly).
2. Take ONE action: write and execute code, inspect data, etc.
3. Do ONE step at a time. Don't try to solve everything in one shot.

Workflow for ML tasks: Understand → EDA → Baseline → Iterate → Evaluate → Summarize.
Always split train/test before modeling. Track metrics for every experiment.
"""

SUMMARY_AGENT_PROMPT = """You are the Summary Agent. Your ONLY job is to compress an observation into a brief summary.

Given:
- The action (code) that was executed
- The raw output/observation

Produce a SHORT summary (3-5 sentences max) covering:
- What was attempted
- Whether it succeeded or failed
- Key numbers/metrics (if any)
- What should be tried next

Be extremely concise. This summary will be stored in memory for future steps.
"""

DEBUG_AGENT_PROMPT = """You are the Debug Agent. Your ONLY job is to fix broken code.

Given:
- The original code that failed
- The error message

Return ONLY the fixed code. No explanations. Just the corrected Python code.
If you cannot fix it, return the original code with a comment explaining what's wrong.
"""

# --- Tools (same as before, just the definitions) ---
TOOLS = [
    {
        "name": "execute_python",
        "description": "Execute Python code and return stdout + stderr.",
        "input_schema": {
            "type": "object",
            "properties": {"code": {"type": "string", "description": "Python code to run."}},
            "required": ["code"]
        }
    },
    {
        "name": "edit_file",
        "description": "Create or overwrite a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path."},
                "content": {"type": "string", "description": "File content."}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "read_csv_preview",
        "description": "Return shape, types, missing values, stats, and first 5 rows of a CSV.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Path to CSV file."}},
            "required": ["path"]
        }
    },
]


# --- Tool implementations (unchanged) ---
def execute_python(code: str) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        tmp_path = f.name
    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True, text=True, timeout=60
        )
        output = ""
        if result.stdout: output += result.stdout
        if result.stderr: output += f"\nSTDERR:\n{result.stderr}"
        return output.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return "ERROR: Timed out (60s)."
    finally:
        os.unlink(tmp_path)

def edit_file(path: str, content: str) -> str:
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return f"File written: {path} ({len(content)} chars)"
    except Exception as e:
        return f"ERROR: {e}"

def read_csv_preview(path: str) -> str:
    try:
        import pandas as pd
        df = pd.read_csv(path)
        parts = [
            f"Shape: {df.shape[0]} rows x {df.shape[1]} columns",
            f"\nColumn Types:\n{df.dtypes.to_string()}",
            f"\nMissing Values:\n{df.isnull().sum().to_string()}",
            f"\nBasic Stats:\n{df.describe().to_string()}",
            f"\nFirst 5 Rows:\n{df.head().to_string()}",
        ]
        return "\n".join(parts)
    except Exception as e:
        return f"Error: {e}"

def run_tool(name: str, inputs: dict) -> str:
    dispatch = {
        "execute_python": lambda: execute_python(inputs["code"]),
        "edit_file": lambda: edit_file(inputs["path"], inputs["content"]),
        "read_csv_preview": lambda: read_csv_preview(inputs["path"]),
    }
    return dispatch.get(name, lambda: f"Unknown tool: {name}")()


# --- The three agents ---

def call_main_agent(client, task, memory):
    """Main Agent: thinks and takes one action."""
    memory_text = "\n---\n".join(memory) if memory else "(no prior steps)"
    messages = [{"role": "user", "content": f"TASK:\n{task}\n\nMEMORY OF PAST STEPS:\n{memory_text}\n\nPlan your next step and take ONE action."}]

    # Let it call tools in a loop until it responds with text
    while True:
        response = client.messages.create(
            model=MODEL, max_tokens=4096,
            system=MAIN_AGENT_PROMPT, tools=TOOLS, messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        tool_calls = [b for b in response.content if b.type == "tool_use"]
        thought = " ".join(b.text for b in response.content if hasattr(b, "text"))

        if not tool_calls:
            return thought, None, None

        # Execute first tool call
        tc = tool_calls[0]
        print(f"  [Main Agent → {tc.name}]")
        result = run_tool(tc.name, tc.input)
        print(f"  [Output: {result[:200]}{'...' if len(result) > 200 else ''}]")

        # Feed result back
        messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": tc.id, "content": result}
        ]})

        has_error = "error" in result.lower() or "traceback" in result.lower()
        if has_error or response.stop_reason == "end_turn":
            return thought, result, tc.input.get("code", "")


def call_summary_agent(client, action_code, observation):
    """Summary Agent: compresses observation into a short summary."""
    response = client.messages.create(
        model=MODEL, max_tokens=300,
        system=SUMMARY_AGENT_PROMPT,
        messages=[{"role": "user", "content": f"ACTION (code):\n```\n{action_code}\n```\n\nOBSERVATION (raw output):\n{observation}"}],
    )
    summary = response.content[0].text
    print(f"  [Summary Agent: {summary[:150]}...]")
    return summary


def call_debug_agent(client, code, error):
    """Debug Agent: fixes broken code. Returns fixed code."""
    response = client.messages.create(
        model=MODEL, max_tokens=4096,
        system=DEBUG_AGENT_PROMPT,
        messages=[{"role": "user", "content": f"BROKEN CODE:\n```python\n{code}\n```\n\nERROR:\n{error}"}],
    )
    fixed = response.content[0].text
    # Strip markdown fences if present
    if fixed.startswith("```"):
        lines = fixed.split("\n")
        fixed = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    print(f"  [Debug Agent: produced fixed code ({len(fixed)} chars)]")
    return fixed


# --- Multi-Agent Loop ---
def multi_agent_loop():
    client = anthropic.Anthropic()
    memory = []  # list of step summaries
    MAX_STEPS = 10
    MAX_DEBUG = 2

    print("=" * 50)
    print("  Multi-Agent ML Pipeline")
    print("  Main Agent → Summary Agent → Debug Agent")
    print("=" * 50)

    while True:
        try:
            task = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break
        if not task or task.lower() in ("quit", "exit", "q"):
            print("Bye!")
            break

        print(f"\n{'='*40}")
        print(f"Starting pipeline for: {task}")
        print(f"{'='*40}")

        for step in range(1, MAX_STEPS + 1):
            print(f"\n--- Step {step}/{MAX_STEPS} ---")

            # 1. Main Agent thinks and acts
            thought, observation, code = call_main_agent(client, task, memory)

            if observation is None:
                # Main agent responded with text only — task is done
                print(f"\nAgent: {thought}")
                break

            # 2. Check for errors → Debug Agent
            has_error = "error" in observation.lower() or "traceback" in observation.lower()
            if has_error and code:
                for debug_attempt in range(1, MAX_DEBUG + 1):
                    print(f"  [Error detected — Debug Agent attempt {debug_attempt}]")
                    fixed_code = call_debug_agent(client, code, observation)
                    observation = execute_python(fixed_code)
                    print(f"  [Re-run result: {observation[:200]}...]")
                    code = fixed_code
                    if "error" not in observation.lower() and "traceback" not in observation.lower():
                        break

            # 3. Summary Agent compresses the observation
            summary = call_summary_agent(client, code or thought, observation)
            memory.append(f"Step {step}: {summary}")

            # Keep memory bounded (last 10 summaries)
            if len(memory) > 10:
                memory = memory[-10:]

        print(f"\n{'='*40}")
        print(f"Pipeline complete. {len(memory)} steps in memory.")
        print(f"{'='*40}")


if __name__ == "__main__":
    multi_agent_loop()
