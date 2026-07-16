# MarketingAssist AI — Multi-Agent Marketing Support (AutoGen + Streamlit)

Built from the reference "Manager → Specialist Agents → Synthesizer" architecture,
adapted for internal marketing team support with live web search instead of a
static knowledge base.

## Architecture

```
User (Streamlit chat)
        │
        ▼
  Router Agent  ──── decides which specialists + whether web search is needed
        │
        ├──▶ Content Agent            (copywriting, ad copy, email, blogs)
        ├──▶ Campaign Strategy Agent  (planning, budget, channel mix, KPIs)
        ├──▶ Social Media Agent       (platform tactics, content calendars)
        ├──▶ SEO Agent                (keywords, on-page/technical SEO)
        ├──▶ Brand Voice Agent        (internal tone/guideline support)
        └──▶ Web Search Agent  ──▶ DuckDuckGo (free, no API key)
                │
                ▼
        Synthesizer Agent ── merges all outputs + runs a 4-point quality
                              check (accuracy, completeness, relevance,
                              clarity/tone)
                │
                ▼
        Final answer + sources + agent trace → Streamlit UI
```

Unlike a free-form AutoGen `GroupChat`, routing here is **code-orchestrated**:
the Router Agent returns a small JSON routing decision, and `orchestrator.py`
calls each selected specialist in a controlled sequence. This makes the flow
deterministic, easy to debug, and easy to display step-by-step in the UI —
which matters both for grading/demoing the assignment and for real
observability.

## Files

| File | Purpose |
|---|---|
| `config.py` | Builds the LLM config from environment variables |
| `tools.py` | The `web_search` function (DuckDuckGo) + source parser |
| `agents.py` | Defines all 8 agents and registers the search tool |
| `orchestrator.py` | Routing → specialists → synthesis pipeline + JSONL logging |
| `app.py` | Streamlit UI: chat, memory, quality check panel, trace panel, sources, download |

## Setup

```bash
pip install -r requirements.txt
```

Set your API key (OpenAI or any OpenAI-compatible endpoint — AutoGen's classic
`pyautogen` speaks the OpenAI chat-completions schema):

```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="gpt-4o-mini"   # optional, this is the default
```

> **Using Claude instead of OpenAI?** `pyautogen` needs an OpenAI-compatible
> endpoint. The simplest path is running a small [LiteLLM](https://github.com/BerriAI/litellm)
> proxy in front of the Anthropic API and pointing `OPENAI_BASE_URL` at it —
> `config.py` already supports a custom `base_url`.

Or just paste the key into the sidebar when the app is running.

## Run

```bash
streamlit run app.py
```

## Extending this for your assignment

- **Add a real knowledge base later**: drop a RAG retriever into `tools.py`
  next to `web_search` and register it on the Brand Voice Agent — this
  reintroduces the "Knowledge Base (RAG)" box from the original diagram.
- **Persistent memory across sessions**: currently memory is per-browser-session
  (`st.session_state`). Swap in a SQLite/Redis-backed history if you need it
  to survive restarts.
- **Parallel specialist execution**: specialists currently run sequentially
  for simplicity/traceability. For speed, `run_specialist` calls in
  `run_pipeline` could be dispatched with `asyncio.gather` or a thread pool.
- **Logs**: every step is appended to `logs/marketing_agent_logs.jsonl` —
  useful for the "Observability & Analytics" / "Logging & History" parts of
  the original diagram if you want to build a dashboard on top of it.
