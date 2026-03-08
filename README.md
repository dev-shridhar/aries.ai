# DSA Agent

Agent that uses **Groq** (open-source LLM) and the **LeetCode MCP** server. All LeetCode data (problems, daily challenge, search, etc.) comes from MCP; Groq does the reasoning and tool calls.

## Requirements

- **Python 3.10+** (3.12 recommended; MCP SDK needs 3.10+)
- **Node.js / npx** (to run the LeetCode MCP server: `@jinzcdev/leetcode-mcp-server`)
- **Groq API key** ([console.groq.com](https://console.groq.com))

If you see an npm cache permission error when starting the agent, fix it once:

```bash
sudo chown -R $(whoami) ~/.npm
```

## Setup

```bash
# Use Python 3.10+ for the venv
python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt

# Copy and add your Groq API key (never commit .env)
cp .env.example .env
# Edit .env and set GROQ_API_KEY=your_key
```

## Run

**CLI (no frontend):**

```bash
source .venv/bin/activate
python agent.py "What is today's daily challenge?"
python agent.py "Get problem two-sum"
python agent.py "Search medium array problems"
```

**Web UI (frontend + API):**

```bash
source .venv/bin/activate
uvicorn api:app --reload
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000). The page lets you type a question and get the agent’s reply (same Groq + LeetCode MCP backend).

## How it works

1. **agent.py** loads `GROQ_API_KEY` from `.env`, starts the **LeetCode MCP server** via `npx -y @jinzcdev/leetcode-mcp-server` (stdio).
2. **mcp_leetcode_client.py** connects to that MCP server, lists its tools, and converts them to Groq tool format.
3. Groq (e.g. `llama-3.3-70b-versatile`) receives the user query and the tool list; it may return tool calls (e.g. `get_daily_challenge`, `get_problem`).
4. The agent runs those tool calls through the **MCP client** (`session.call_tool`), gets results from the LeetCode MCP server, and sends them back to Groq.
5. Groq then replies with a final answer.

So the only source of LeetCode data is the **LeetCode MCP**; there is no direct HTTP client to LeetCode in this repo.
