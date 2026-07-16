"""
orchestrator.py
----------------
Code-driven orchestration of the agent pipeline (this is the "Manager
Agent" behavior from the diagram, made deterministic and inspectable
instead of a free-form AutoGen GroupChat):

  1. Router Agent decides which specialists + whether web search is needed
  2. (optional) Web Search Agent runs, results feed into specialists
  3. Each selected specialist runs, in turn, with the query + web context
  4. Synthesizer Agent merges everything + runs the quality checklist
  5. Every step is logged to logs/marketing_agent_logs.jsonl for the
     Observability & Logging panel in the Streamlit UI.
"""

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from tools import parse_sources_from_search_output

LOG_PATH = Path(__file__).parent / "logs" / "marketing_agent_logs.jsonl"
LOG_PATH.parent.mkdir(exist_ok=True)

# Deterministic safety net: if the query obviously contains these terms,
# make sure the matching specialist is included even if the LLM Router
# missed it. This doesn't override the Router's picks -- only adds to them.
KEYWORD_MAP = {
    "campaign": ["campaign strategy", "campaign plan", "launch plan", "channel mix",
                 "budget allocation", "marketing campaign", "kpis", "kpi"],
    "seo": ["seo", "search engine ranking", "keyword research", "backlink", "serp"],
    "social": ["social media", "instagram", "tiktok", "linkedin post", "facebook ad",
               "twitter", " x post", "content calendar"],
    "brand": ["brand guideline", "brand voice", "tone of voice", "style guide", "brand standard"],
    "content": ["blog post", "ad copy", "email copy", "product description",
                "landing page copy", "write copy", "draft a post"],
}


def _augment_routing_with_keywords(query: str, routing: dict) -> dict:
    query_lower = query.lower()
    agents = list(routing.get("agents", []))
    for agent_key, keywords in KEYWORD_MAP.items():
        if agent_key in agents:
            continue
        if any(kw in query_lower for kw in keywords):
            agents.append(agent_key)
    routing["agents"] = agents
    return routing


def _log(record: dict):
    record["timestamp"] = datetime.now(timezone.utc).isoformat()
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")


def _extract_json(text: str) -> dict:
    """Best-effort JSON extraction in case the model wraps output in
    markdown fences or adds stray text around the JSON object."""
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)


def _run_two_agent_chat(executor, agent, message: str) -> str:
    """Runs a single request/response turn between the shared executor
    and a given agent, returning the agent's final text reply."""
    executor.reset()
    agent.reset()
    chat_result = executor.initiate_chat(agent, message=message, silent=True)
    # Last non-empty message from the specialist agent
    for msg in reversed(chat_result.chat_history):
        if msg.get("name") == agent.name or msg.get("role") == "assistant":
            content = msg.get("content", "").strip()
            if content:
                return content
    return ""


def route_query(agents: dict, query: str) -> dict:
    raw = _run_two_agent_chat(agents["executor"], agents["router"], query)
    try:
        routing = _extract_json(raw)
    except Exception:
        # Safe fallback: send to content + brand if routing parse fails
        routing = {"agents": ["content", "brand"], "needs_web_search": False, "search_query": ""}
    routing = _augment_routing_with_keywords(query, routing)
    _log({"step": "routing", "input": query, "output": routing})
    return routing


def run_web_research(agents: dict, search_query: str) -> tuple[str, list]:
    prompt = f"Research this and summarize: {search_query}"
    summary = _run_two_agent_chat(agents["executor"], agents["web_search"], prompt)

    # Pull the raw tool output back out of the chat history for sources
    sources = []
    for msg in agents["executor"].chat_messages.get(agents["web_search"], []):
        content = msg.get("content", "") or ""
        if "Source:" in content:
            sources.extend(parse_sources_from_search_output(content))

    _log({"step": "web_search", "input": search_query, "output": summary, "sources": sources})
    return summary, sources


def run_specialist(agents: dict, key: str, query: str, web_context: str) -> str:
    agent = agents[key]
    prompt = f"User request: {query}"
    if web_context:
        prompt += f"\n\nRelevant web research:\n{web_context}"
    output = _run_two_agent_chat(agents["executor"], agent, prompt)
    _log({"step": f"specialist:{key}", "input": prompt, "output": output})
    return output


def synthesize(agents: dict, query: str, specialist_outputs: dict) -> dict:
    combined = "\n\n".join(
        f"### {key.upper()} AGENT OUTPUT\n{value}" for key, value in specialist_outputs.items()
    )
    prompt = f"Original user query: {query}\n\nSpecialist outputs:\n{combined}"
    raw = _run_two_agent_chat(agents["executor"], agents["synthesizer"], prompt)
    try:
        result = _extract_json(raw)
    except Exception:
        result = {
            "final_answer": raw or "The system could not produce a synthesized answer.",
            "quality_check": {
                "accuracy": "unknown - parse failed",
                "completeness": "unknown - parse failed",
                "relevance": "unknown - parse failed",
                "clarity_tone": "unknown - parse failed",
            },
        }
    _log({"step": "synthesis", "input": prompt, "output": result})
    return result


def run_pipeline(agents: dict, query: str, on_update=None) -> dict:
    """Full end-to-end run. Returns everything the Streamlit UI needs:
    final answer, quality check, sources, a step-by-step trace, and the
    list of agents actually used for this specific request.

    on_update, if provided, is called as on_update(agent_key, status)
    with status in {"active", "done"} right before/after each agent
    runs -- this is what powers the live Workflow Activity panel.
    """

    def emit(agent_key: str, status: str):
        if on_update:
            on_update(agent_key, status)

    trace = []
    used_agents = []
    t0 = time.time()

    emit("router", "active")
    routing = route_query(agents, query)
    emit("router", "done")
    used_agents.append("router")
    trace.append({"agent": "Router Agent", "detail": routing})

    web_summary, sources = "", []
    if routing.get("needs_web_search") and routing.get("search_query"):
        emit("web_search", "active")
        web_summary, sources = run_web_research(agents, routing["search_query"])
        emit("web_search", "done")
        used_agents.append("web_search")
        trace.append({"agent": "Web Search Agent", "detail": web_summary})

    specialist_outputs = {}
    for key in routing.get("agents", []):
        if key not in agents:
            continue
        emit(key, "active")
        output = run_specialist(agents, key, query, web_summary)
        emit(key, "done")
        specialist_outputs[key] = output
        used_agents.append(key)
        trace.append({"agent": f"{key.capitalize()} Agent", "detail": output})

    if not specialist_outputs:
        # Guarantee at least one specialist runs so the user gets an answer
        emit("content", "active")
        output = run_specialist(agents, "content", query, web_summary)
        emit("content", "done")
        specialist_outputs["content"] = output
        used_agents.append("content")
        trace.append({"agent": "Content Agent (fallback)", "detail": output})

    emit("synthesizer", "active")
    synthesis = synthesize(agents, query, specialist_outputs)
    emit("synthesizer", "done")
    used_agents.append("synthesizer")
    trace.append({"agent": "Synthesizer Agent", "detail": synthesis})

    elapsed = round(time.time() - t0, 2)
    _log({"step": "pipeline_complete", "elapsed_seconds": elapsed, "query": query})

    return {
        "final_answer": synthesis.get("final_answer", ""),
        "quality_check": synthesis.get("quality_check", {}),
        "sources": sources,
        "trace": trace,
        "routing": routing,
        "elapsed_seconds": elapsed,
        "used_agents": used_agents,
    }