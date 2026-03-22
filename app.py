"""
ML Agent — Streamlit Chat UI
Run: streamlit run app.py
"""

import os
import sys
import json
import subprocess
import tempfile
import urllib.request
import urllib.parse
import streamlit as st
import anthropic

MODEL = "claude-sonnet-4-20250514"

SYSTEM_PROMPT_SWE = """You are a software engineer assistant. You can write and execute Python code.

Rules:
- Be concise in your responses.
- When asked to write code, use edit_file to save it, then execute_python to run it.
- Always show the user the output of executed code.
- If code has errors, debug and retry.
- When the task is complete, say so clearly.
"""

SYSTEM_PROMPT_ML = """You are a machine learning engineer. You build, train, and evaluate ML models.

Workflow: Understand → EDA → Baseline → Iterate → Evaluate → Summarize.

Rules:
- Be concise. Show key metrics, not walls of text.
- Always split data into train/test before modeling.
- Use execute_python to run code. Use edit_file to save scripts.
- Use read_csv_preview to quickly inspect datasets.
- If code errors, debug and retry.
- Track every experiment: model name, parameters, score.
"""

TOOLS = [
    {
        "name": "execute_python",
        "description": "Execute Python code and return stdout + stderr.",
        "input_schema": {
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"]
        }
    },
    {
        "name": "edit_file",
        "description": "Create or overwrite a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "read_csv_preview",
        "description": "Return shape, types, missing values, stats, and first 5 rows of a CSV.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"]
        }
    },
]


# --- Tool implementations ---
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


# --- Streamlit UI ---
st.set_page_config(page_title="RAIYAN BOT", page_icon="🤖", layout="wide")
st.markdown("# 🤖 R<span style='color: #FF4B4B;'>AI</span>YAN BOT", unsafe_allow_html=True)
st.caption("Your ML Engineering Agent · Powered by Claude")

# Sidebar
with st.sidebar:
    st.header("Settings")
    mode = st.toggle("🤖 ML Engineer Mode", value=True)
    active_prompt = SYSTEM_PROMPT_ML if mode else SYSTEM_PROMPT_SWE
    st.caption(f"Mode: **{'ML Engineer' if mode else 'Software Engineer'}**")

    st.divider()
    st.header("About")
    st.markdown("""
    This agent can:
    - 📊 Inspect CSV datasets
    - 🧪 Write & execute Python code
    - 📁 Create & edit files
    - 🤖 Build ML models end-to-end
    """)
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.session_state.api_messages = []
        st.rerun()

# Session state
if "messages" not in st.session_state:
    st.session_state.messages = []      # display messages
    st.session_state.api_messages = []   # messages sent to Claude

# Predefined prompts
EXAMPLE_PROMPTS = [
    "🏦 Build a loan approval model from sample_data.csv",
    "📊 Analyze sample_data.csv and show key insights",
    "🐍 Write a Python script that generates 100 random data points and plots them",
    "🔍 Read sample_data.csv and tell me which features matter most for prediction",
]

if not st.session_state.messages:
    st.markdown("#### 👋 Try one of these to get started:")
    cols = st.columns(2)
    for i, prompt_text in enumerate(EXAMPLE_PROMPTS):
        if cols[i % 2].button(prompt_text, key=f"example_{i}", use_container_width=True):
            st.session_state.pending_prompt = prompt_text
            st.rerun()

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="🧑‍💻" if msg["role"] == "user" else "🤖"):
        st.markdown(msg["content"])

# Chat input
prompt = st.chat_input("Ask me to build an ML model...")

# Handle clicked example prompt
if "pending_prompt" in st.session_state:
    prompt = st.session_state.pending_prompt
    del st.session_state.pending_prompt

if prompt:
    # Show user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(prompt)

    # Add to API messages
    st.session_state.api_messages.append({"role": "user", "content": prompt})

    # Agent loop
    client = anthropic.Anthropic()
    with st.chat_message("assistant", avatar="🤖"):
        full_response = ""

        while True:
            response = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=active_prompt,
                tools=TOOLS,
                messages=st.session_state.api_messages,
            )

            st.session_state.api_messages.append({"role": "assistant", "content": response.content})

            tool_calls = [b for b in response.content if b.type == "tool_use"]

            # Show text
            for block in response.content:
                if hasattr(block, "text") and block.text:
                    full_response += block.text + "\n"
                    st.markdown(block.text)

            if not tool_calls:
                break

            # Execute tools
            tool_results = []
            for tc in tool_calls:
                with st.expander(f"🔧 Tool: {tc.name}", expanded=False):
                    result = run_tool(tc.name, tc.input)
                    st.code(result[:2000], language="text")
                    full_response += f"\n🔧 *{tc.name}*\n"

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": result,
                })

            st.session_state.api_messages.append({"role": "user", "content": tool_results})

        # Save final response for display
        st.session_state.messages.append({"role": "assistant", "content": full_response.strip()})
