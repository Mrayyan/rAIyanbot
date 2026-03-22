# ML Agent Build — Progress Log

## Key Concepts (Plain English)

### What is an Agent?
A normal LLM call is like asking someone a question and getting an answer — one shot, done.
An **agent** is an LLM running in a **loop**: it thinks, takes an action (like running code), looks at the result, and then thinks again. It keeps going until the task is done. That loop is the core idea.

### The Agent Loop
```
[Think] → [Act] → [Observe] → [Think again] → ...
```
- **Think**: The LLM decides what to do next (e.g., "I should try a random forest model")
- **Act**: It writes and executes code
- **Observe**: It reads the output (errors, scores, logs)
- **Loop**: Based on what it saw, it decides the next step

Both papers in `/context` use this pattern. PiML calls it "Thought-Action-Observation." LoongFlow calls it "Plan-Execute-Summarize." Same idea, different names.

### What is a Tool?
A **tool** is a function you give to the LLM so it can *do things* beyond just generating text. Examples:
- A tool to run Python code
- A tool to read/write files
- A tool to search the web

You define tools as Python functions, and the LLM decides *when* to call them based on the conversation. The Anthropic SDK handles the plumbing.

### What is an MCP (Model Context Protocol)?
MCP is a **standard protocol** for connecting LLMs to external tools and data sources. Think of it like USB — a universal plug. Instead of every tool having its own custom integration, MCP provides one standard way:
- **MCP Servers** expose tools (e.g., a GitHub MCP server, a filesystem MCP server)
- **MCP Clients** (like your agent) connect to them and use those tools

Copilot CLI, Claude Code, Cursor — they all use MCP under the hood to connect to things like GitHub, databases, etc.

### How do Cursor / Claude Code / Copilot CLI work?
They're all **agents** with the same basic pattern:
1. A powerful LLM (Claude, GPT, etc.) as the "brain"
2. **Tools** for reading files, editing code, running terminal commands, searching
3. A **system prompt** that tells the LLM its role and rules
4. A **context window** — the LLM can only "see" a limited amount of text at once

The main differences are: which LLM, which tools, how they manage context, and the UX.

### Context Compression — Why It Matters
LLMs have a **context window** (e.g., 200K tokens). When your agent runs for many iterations, the conversation history gets huge. If you dump everything in, you:
- Hit the token limit
- Waste money
- Confuse the LLM with irrelevant old info

**Solution**: Compress context. Both papers do this:
- **PiML**: Keeps full detail for the last ~10 steps, only summaries for older steps. Falls back to less and less context if things get too long.
- **LoongFlow**: Each step produces a "summary" that captures *why* things worked or failed, and only those summaries carry forward.

Key insight: **Recent context in full detail, old context as summaries.**

### System Prompt — How Big Can It Be?
The system prompt shares space with everything else in the context window (e.g., 200K tokens for Claude). It can be very long — Copilot CLI's is thousands of tokens. But the bigger it is, the less room for conversation + code output.

**Sweet spot for an ML agent**: 1-3 pages (~2-4K tokens). Enough to define persona, workflow, best practices, and pitfalls. Leave the rest for actual work.

### How Tools Like Cursor Are Built (Desktop Apps)
- **Cursor / VS Code** = Electron (wraps a web app as a desktop app) + React + a backend that calls LLM APIs
- **Electron** = Chromium browser + Node.js bundled together. You write HTML/CSS/JS and it runs as a native window.
- **React Native** is for mobile, **React + Electron** is for desktop
- Simpler alternatives: **Streamlit** or **Gradio** (Python libraries that spin up a chat UI in the browser with ~50 lines of code)

**Our plan**: Build the CLI agent first → wrap it in a Streamlit/Gradio web UI as a bonus.

### How to Steer an Agent's Behavior (Relevant for Task B)
Two main levers to turn a "generic software engineer" agent into an "ML engineer" agent:
1. **System Prompt** — Tell it who it is, what it knows, how to approach problems (e.g., "You are an ML engineer. Always start with EDA. Try multiple models. Track metrics.")
2. **Tools** — Give it ML-specific tools (e.g., a tool to run sklearn pipelines, a tool to visualize data, a tool to log experiment results)

Other levers: few-shot examples, memory/knowledge bases, specialized sub-agents.

---

## Roadmap (from todo.pdf)

### Task A — Build a Software Agent
- [x] A1: Understand the agent loop (conceptual — done reading papers ✓)
- [x] A2: Build a simple agent that can edit + execute Python code → `agent.py`
- [x] A3: Give it a custom tool and test it → added `web_search` (DuckDuckGo API, no key needed)
- [x] A4: Give it an MCP server and test it → `mcp_server.py` (read_file + list_directory)

### Task B — Turn It into an ML Agent
- [x] B1: Brainstorm levers to change behavior (system prompt, tools, memory, etc.)
- [x] B2: Implement two methods to specialize it for ML, test both

### Stretch
- [x] S1: Think about architecture (single agent vs. multi-agent vs. sub-agents)
- [x] S2: Review SotA agents and context management best practices
- [x] S3: Wrap the agent in a Streamlit/Gradio web UI → `app.py`

---

## Session Log

### Session 1 — Kickoff & Concepts
- Read todo.pdf, PiML paper, LoongFlow paper
- Documented key concepts above (agent loop, tools, MCP, context compression)
- Discussed system prompt sizing (2-4K tokens sweet spot for ML agent)
- Discussed desktop app options: Electron+React (like Cursor) vs Streamlit/Gradio (simpler)
- **Decision**: CLI first, then Streamlit/Gradio web UI as bonus
- **Status**: Understanding phase complete.

### Session 2 — Built the Core Agent (A2)
- Created `agent.py` — a working agent loop with two tools:
  - `execute_python`: runs Python code in a subprocess (with 30s timeout)
  - `edit_file`: creates/overwrites files
- **How it works**: User types a task → Claude thinks → calls tools → sees results → keeps going until done
- System prompt tells Claude to be concise, use tools, debug errors, and confirm completion
- The whole thing is ~100 lines — no frameworks, just the Anthropic SDK + a while loop
- **Status**: A2 done. Moving to A3 (adding a custom tool).

### Session 3 — Added Web Search Tool (A3)
- Added `web_search` tool using DuckDuckGo instant answer API (free, no key)
- Updated system prompt to tell Claude when to use it
- **Key learning**: Adding a tool is just 3 steps — define the JSON schema, write the Python function, wire it into the dispatcher
- **Status**: A3 done. Moving to A4 (MCP server).

### Session 4 — Added MCP Server (A4)
- Created `mcp_server.py` — a standalone MCP server exposing `read_file` and `list_directory`
- Updated `agent.py` to be an MCP client: on startup it connects to `mcp_server.py`, discovers its tools, and adds them to Claude's tool list
- **How it works**: agent starts the MCP server as a subprocess → talks via stdin/stdout JSON → routes tool calls either to local functions or to the MCP server
- **Key learning**: MCP is modular — the agent doesn't need to know HOW the tools work, just their name/description/schema. You can swap MCP servers without touching agent code.
- Agent now has 5 tools: `execute_python`, `edit_file`, `web_search` (local) + `read_file`, `list_directory` (MCP)
- **Status**: Task A complete! ✅ Moving to Task B (ML specialization).

### Session 5 — Task B: ML Specialization (B1 + B2)

**B1: All the levers to adapt agent behavior:**

| # | Lever | How it works | Effort |
|---|-------|-------------|--------|
| 1 | System Prompt | Change persona — tell it to think like an ML engineer, follow EDA→features→model→evaluate | Low |
| 2 | ML-Specific Tools | Give it tools like `read_csv_preview`, `train_and_evaluate`, `plot_results` | Medium |
| 3 | Few-Shot Examples | Include a worked ML example in the prompt | Low |
| 4 | Knowledge/RAG | Give it access to ML docs, sklearn API references, best practices | Medium-High |
| 5 | Memory | Summarize past experiments and carry them forward (like PiML's adaptive memory) | High |
| 6 | Sub-agents | Specialized agents for EDA, feature engineering, modeling (like PiML's multi-agent architecture) | High |

**Chosen methods to implement: #1 System Prompt + #2 ML Tools**

- **Method 1 (System Prompt)**: Replaced generic SWE prompt with ML-specific one that enforces a workflow: Understand → EDA → Baseline → Iterate → Evaluate → Summarize. Both prompts are in `agent.py` — toggle `SYSTEM_PROMPT` between `SYSTEM_PROMPT_SWE` and `SYSTEM_PROMPT_ML`.
- **Method 2 (ML Tool)**: Added `read_csv_preview` tool — loads a CSV and returns shape, types, missing values, stats, and first 5 rows. This gives the agent "ML vision" it didn't have before.
- Created `sample_data.csv` (loan approval dataset, 20 rows) for testing.
- Installed `pandas` and `scikit-learn` for the agent's code execution.

**How to test the difference:**
1. Set `SYSTEM_PROMPT = SYSTEM_PROMPT_SWE` → ask "Build a model to predict loan approval from sample_data.csv" → observe generic coding behavior
2. Set `SYSTEM_PROMPT = SYSTEM_PROMPT_ML` → same prompt → observe structured ML workflow (EDA first, baseline, iterate, metrics)

**Status**: Task B complete! ✅

### Session 6 — Stretch S1: Agent Architecture Analysis

**Question**: Should an ML agent use a single agent, multiple agents, or sub-agents?

**Option 1: Single Agent (what we built)**
```
User → [One LLM + tools] → Result
```
- One LLM does everything: EDA, coding, debugging, evaluating.
- ✅ Simple, easy to build and debug.
- ❌ Context window fills up fast after many iterations — LLM "forgets" early work.
- ❌ One generic persona, no specialization.

**Option 2: Multi-Agent Pipeline (what PiML does)**
```
User → [Main Agent] → code → [Executor] → output → [Summary Agent] → compressed feedback → [Debug Agent if error] → back to Main Agent
```
- Each agent has ONE focused job and a specialized prompt.
- The **Summary Agent** is the key innovation — it compresses raw code output into a concise summary, so the Main Agent's context stays manageable over many iterations.
- PiML's memory strategy: full context for last ~10 steps, only summaries for older steps, with fallback tiers if context gets too long.
- ✅ Better context management — each agent sees only what it needs.
- ✅ Specialized prompts = higher quality per task.
- ❌ More complex to orchestrate, more API calls, higher cost.

**Option 3: Evolutionary / Population-based (what LoongFlow does)**
```
[Island 1: Agent A tries approach X]
[Island 2: Agent B tries approach Y]  → best solutions migrate between islands
[Island 3: Agent C tries approach Z]
```
- Multiple agents explore different solution paths in parallel.
- Uses MAP-Elites to maintain diversity — keeps "stepping stone" solutions that aren't the best yet but explore new territory.
- ✅ Avoids local optima — one bad idea doesn't kill the whole run.
- ❌ Very expensive (parallel LLM calls). LoongFlow reports 60% better efficiency than baselines, but still heavy.
- ❌ Overkill for most practical use cases.

**Our conclusion: Option 2 (Multi-Agent Pipeline) is the sweet spot.**
- It's proven (PiML beat AIDE on Kaggle benchmarks with this architecture).
- It solves the #1 practical problem: context window overflow during long ML workflows.
- It's buildable — we'd add a Summary Agent and Debug Agent to our existing Main Agent.
- Option 3 is interesting for research/competitions but too expensive for everyday use.

**Built it! → `agent_multi.py`**
Three agents, each with a focused system prompt:
- **Main Agent**: plans next step, writes and executes ONE action at a time
- **Summary Agent**: compresses raw output into 3-5 sentence summary → stored in memory
- **Debug Agent**: if code errors, gets the broken code + error, returns fixed code (up to 2 retries)

Memory management (inspired by PiML): only the last 10 step summaries are kept. Each summary is short (produced by Summary Agent), so context stays small even after many iterations.

**Real-world feedback after testing:**
- ⚠️ Multi-agent was MUCH slower than single agent — each step makes 2-3 separate API calls (Main + Summary + Debug if needed) vs. 1 for single agent. More agents = more latency + cost.
- ⚠️ Very buggy in practice — lots of "Error detected" loops, Debug Agent sometimes introduces new errors, cascading failures.
- ⚠️ Had to kill execution manually — pipeline ran too long without converging.
- **Takeaway**: Multi-agent is architecturally cleaner but has real tradeoffs. The SotA agents (Cursor, Claude Code) solve this by using sub-agents only for ISOLATED side-tasks (search, test runs), not for the main reasoning loop. PiML gets away with it because they run on powerful GPUs for 24 hours per competition — not interactive use. For interactive use, single agent with good prompt + tools is often better.

How to test: `python agent_multi.py` → "Build a model to predict loan approval from sample_data.csv"
Compare with `python agent.py` (single agent) to see the difference in structure.

### Session 7 — Stretch S2: SotA Agent Review & Context Management

**How the big agents actually work:**

| Agent | Architecture | Context Strategy | Key Insight |
|-------|-------------|-----------------|-------------|
| **Cursor** | Main agent + sub-agents | Semantic indexing picks relevant files; sub-agents work in isolated context windows and return compact results; `.cursor/rules/` for persistent project knowledge; `/compact` command to summarize and shrink context | Sub-agents are the killer feature — noisy work (searching, running commands) stays out of the main context |
| **Claude Code** | Main agent + sub-agents | Hierarchical config: global `~/.claude/CLAUDE.md` → project `CLAUDE.md` → local overrides; `/compact` for context summarization; persistent "Skills" for reusable knowledge; hooks to auto-inject context | `CLAUDE.md` as the project "brain" — version-controlled agent knowledge that any team member (or agent instance) inherits |
| **Devin** | Planner → Executor → Critic | 10M+ token context in enterprise tier; iterative plan-execute-review cycles; auto-writes CHANGELOGs and progress notes to filesystem as external memory; manages "context anxiety" (LLMs rush when window fills up) | External memory via filesystem — when context gets full, the agent saves notes to files and reads them back later |
| **PiML** (paper) | Main Agent + Summary Agent + Debug Chain | Multi-tier: full context for last 10 steps, summaries for older, 5 fallback levels down to minimal context | Tiered memory compression — graceful degradation as context fills |
| **LoongFlow** (paper) | Plan-Execute-Summarize + multi-island evolution | Lineage-based retrieval (trace parent→child chain); MAP-Elites for solution diversity; structured summaries stored as evolutionary memory | Genealogical memory — each solution knows its ancestry and learns from it |

**Universal best practices across all SotA agents:**

1. **Compress aggressively** — Recent steps in full, older steps as summaries. Every agent does this.
2. **Sub-agents for isolation** — Noisy work (file search, test runs, debugging) happens in separate context windows. Only the result comes back to the main agent.
3. **Persistent project knowledge** — Rules files (Cursor), CLAUDE.md (Claude Code), Playbooks (Devin). A config file that tells the agent about your project, standards, and conventions.
4. **External memory** — When context window isn't enough, write to the filesystem. Devin does this automatically; PiML uses its memory constructor.
5. **Iterative cycles** — No agent tries to solve everything in one pass. It's always think→act→observe→repeat.

**How our agent compares:**
- ✅ We have the iterative loop (agent.py, agent_multi.py)
- ✅ We have summary-based compression (agent_multi.py's Summary Agent)
- ✅ We have debug recovery (agent_multi.py's Debug Agent)
- ❌ Missing: persistent project knowledge (like CLAUDE.md)
- ❌ Missing: sub-agent isolation (our agents share context in sequence, not parallel)
- ❌ Missing: external filesystem memory (saving notes to files when context fills up)

**Status**: S2 complete ✅

### Session 8 — Stretch S3: Streamlit Web UI
- Built `app.py` — **rAIyan**, a Streamlit chat UI wrapping the same agent logic
- Features: chat bubbles, tool calls in collapsible expanders, sidebar with info + clear button
- Same tools as agent.py (execute_python, edit_file, read_csv_preview)
- Run with: `streamlit run app.py`
- **Free hosting options**: Streamlit Cloud (easiest — connect GitHub, add API key as secret, get public URL), Hugging Face Spaces, Render, Railway. All need ANTHROPIC_API_KEY as env secret.
- **Status**: S3 complete ✅
- [x] Get an Anthropic API key from https://console.anthropic.com
- [x] Install the Anthropic Python SDK (`pip install anthropic`)
