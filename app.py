"""
app.py
------
Streamlit front-end for the Marketing Multi-Agent Support system.

Run with:  streamlit run app.py

Requires a .env file (or real environment variables) with:
    OPENAI_API_KEY=sk-...
    OPENAI_MODEL=gpt-4o-mini   (optional)
No key is ever entered or shown in the UI.
"""

import os
import streamlit as st
from dotenv import load_dotenv

import config  # noqa: F401 -- import first so its warning/logging suppression
                # takes effect before agents.py pulls in autogen (and flaml)

load_dotenv()

st.set_page_config(page_title="MarketingAssist AI", page_icon="📣", layout="wide")

# ---------- Agent metadata ----------
AGENT_META = {
    "router": {"label": "Router", "icon": "🧭"},
    "web_search": {"label": "Web Search", "icon": "🌐"},
    "content": {"label": "Content", "icon": "✍️"},
    "campaign": {"label": "Campaign Strategy", "icon": "📈"},
    "social": {"label": "Social Media", "icon": "📱"},
    "seo": {"label": "SEO", "icon": "🔍"},
    "brand": {"label": "Brand Voice", "icon": "🎨"},
    "synthesizer": {"label": "Synthesizer", "icon": "🧩"},
}
SPECIALIST_KEYS = ["content", "campaign", "social", "seo", "brand"]

# ---------- Design tokens + one-time CSS ----------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@500&display=swap');

    :root {
        --ink: #0F172A;
        --canvas: #FFFFFF;
        --panel: #F8FAFC;
        --indigo: #4F46E5;
        --amber: #D97706;
        --green: #16A34A;
        --border: #E2E8F0;
    }

    /* ---- Typography ---- */
    .ma-hero {
        font-family: 'Space Grotesk', sans-serif; font-weight: 700;
        font-size: 2.4rem; line-height: 1.15; margin-bottom: 0.2rem;
        background: linear-gradient(90deg, var(--indigo) 0%, var(--amber) 100%);
        -webkit-background-clip: text; background-clip: text; color: transparent;
    }
    .ma-subtitle {
        font-family: 'Inter', sans-serif; color: #64748B; font-size: 0.95rem;
        margin-bottom: 1.2rem;
    }
    .ma-eyebrow {
        font-family: 'JetBrains Mono', monospace; font-size: 0.7rem;
        letter-spacing: 0.08em; text-transform: uppercase; color: #94A3B8;
        margin: 0.6rem 0 0.4rem 0;
    }
    .ma-sidebar-title {
        font-family: 'Space Grotesk', sans-serif; font-weight: 700;
        font-size: 1.3rem; color: var(--ink); margin-bottom: 0;
    }
    .ma-model-chip {
        font-family: 'JetBrains Mono', monospace; font-size: 0.75rem;
        background: var(--panel); border: 1px solid var(--border);
        padding: 3px 8px; border-radius: 6px; color: var(--indigo);
    }

    /* ---- Agent badges ---- */
    .agent-badge {
        display: inline-block; padding: 6px 12px; margin: 3px;
        border-radius: 999px; font-family: 'JetBrains Mono', monospace;
        font-size: 12px; font-weight: 500;
        border: 1.5px solid var(--border); color: #475569; background: var(--panel);
        transition: all 0.15s ease;
    }
    .agent-badge.active {
        border-color: var(--amber); color: #92400E; background: #FEF3C7;
        animation: pulse 1.1s infinite;
    }
    .agent-badge.done {
        border-color: var(--green); color: #15803D; background: #DCFCE7;
    }
    @keyframes pulse {
        0%   { box-shadow: 0 0 0 0 rgba(217,119,6,0.35); }
        70%  { box-shadow: 0 0 0 6px rgba(217,119,6,0); }
        100% { box-shadow: 0 0 0 0 rgba(217,119,6,0); }
    }
    @media (prefers-reduced-motion: reduce) {
        .agent-badge.active { animation: none; }
    }

    /* ---- Pipeline signature strip ---- */
    .pipeline-strip {
        display: flex; align-items: center; flex-wrap: wrap; gap: 10px;
        background: var(--panel); border: 1px solid var(--border);
        border-radius: 12px; padding: 14px 18px; margin-bottom: 1.2rem;
    }
    .pipeline-node {
        font-family: 'JetBrains Mono', monospace; font-size: 12px;
        background: var(--canvas); border: 1.5px solid var(--border);
        border-radius: 8px; padding: 6px 10px; color: var(--ink);
    }
    .pipeline-node.emphasis { border-color: var(--indigo); color: var(--indigo); }
    .pipeline-arrow { color: #94A3B8; font-size: 16px; }
    .pipeline-group { display: flex; flex-wrap: wrap; gap: 6px; }
    </style>
    """,
    unsafe_allow_html=True,
)


def render_agent_badges(state: dict) -> str:
    """state: {agent_key: 'idle' | 'active' | 'done'}"""
    spans = []
    for key, meta in AGENT_META.items():
        status = state.get(key, "idle")
        css_class = f"agent-badge {status}" if status != "idle" else "agent-badge"
        spans.append(f'<span class="{css_class}">{meta["icon"]} {meta["label"]}</span>')
    return "".join(spans)


def render_pipeline_strip() -> str:
    """The static signature element: shows the real Router -> Specialists ->
    Synthesizer flow as a legend, visible throughout the demo."""
    specialists_html = "".join(
        f'<span class="pipeline-node">{AGENT_META[k]["icon"]} {AGENT_META[k]["label"]}</span>'
        for k in SPECIALIST_KEYS
    )
    return f"""
    <div class="pipeline-strip">
        <span class="pipeline-node emphasis">🧭 Router</span>
        <span class="pipeline-arrow">→</span>
        <span class="pipeline-node">🌐 Web Search</span>
        <span class="pipeline-arrow">→</span>
        <div class="pipeline-group">{specialists_html}</div>
        <span class="pipeline-arrow">→</span>
        <span class="pipeline-node emphasis">🧩 Synthesizer</span>
    </div>
    """


# ---------- Cached agent build (so we don't rebuild 8 agents every query) ----------
@st.cache_resource(show_spinner=False)
def get_agents():
    from agents import build_agents
    return build_agents()


# ---------- Sidebar ----------
with st.sidebar:
    st.markdown('<div class="ma-sidebar-title">📣 MarketingAssist AI</div>', unsafe_allow_html=True)
    st.caption("Multi-Agent Architecture & Workflow — Internal Marketing Support")

    if not os.getenv("OPENAI_API_KEY"):
        st.error(
            "No API key found. Add OPENAI_API_KEY to a `.env` file in this "
            "folder (see README) and restart the app."
        )
        st.stop()

    st.markdown(
        f'<span class="ma-model-chip">{os.getenv("OPENAI_MODEL", "gpt-4o-mini")}</span> '
        f'<span style="color:#94A3B8; font-size:0.8rem;">(from .env)</span>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="ma-eyebrow">Agents Online</div>', unsafe_allow_html=True)
    st.markdown(render_agent_badges({}), unsafe_allow_html=True)

    st.markdown('<div class="ma-eyebrow">Live Workflow Activity</div>', unsafe_allow_html=True)
    workflow_placeholder = st.empty()
    workflow_placeholder.caption("Idle — waiting for a question.")

    st.divider()
    if st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ---------- Session state (Memory) ----------
if "messages" not in st.session_state:
    st.session_state.messages = []  # each: {role, content, meta}

# ---------- Hero ----------
st.markdown('<div class="ma-hero">MarketingAssist AI</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="ma-subtitle">Intelligent Orchestration · Specialized Marketing '
    'Expertise · Reliable Answers</div>',
    unsafe_allow_html=True,
)
st.markdown(render_pipeline_strip(), unsafe_allow_html=True)


def render_meta(meta: dict):
    m1, m2, m3 = st.columns(3)
    m1.metric("⏱ Response time", f"{meta.get('elapsed_seconds', '?')}s")
    m2.metric("🧩 Agents involved", len(set(meta.get("used_agents", []))))
    m3.metric("🌐 Sources found", len(meta.get("sources", [])))

    st.markdown('<div class="ma-eyebrow">Agents involved in this answer</div>', unsafe_allow_html=True)
    used = {k: "done" for k in meta.get("used_agents", [])}
    st.markdown(render_agent_badges(used), unsafe_allow_html=True)

    tabs = st.tabs(["🔍 Quality Check", "🧩 Agent Trace", "🌐 Sources"])

    with tabs[0]:
        qc = meta.get("quality_check", {})
        if qc:
            for k, v in qc.items():
                label = k.replace("_", " ").title()
                ok = isinstance(v, str) and v.strip().lower().startswith("pass")
                st.markdown(f"{'✅' if ok else '⚠️'} **{label}:** {v}")
        else:
            st.caption("No quality check data.")

    with tabs[1]:
        routing = meta.get("routing", {})
        st.markdown(f"**Routed to:** {', '.join(routing.get('agents', [])) or 'none'}")
        st.markdown(f"**Web search used:** {routing.get('needs_web_search', False)}")
        for step in meta.get("trace", []):
            with st.expander(f"🔹 {step['agent']}"):
                detail = step["detail"]
                if isinstance(detail, dict):
                    st.json(detail)
                else:
                    st.markdown(detail)

    with tabs[2]:
        sources = meta.get("sources", [])
        if sources:
            for s in sources:
                st.markdown(f"- [{s['title']}]({s['url']})")
        else:
            st.caption("No live web sources were used for this answer.")


# ---------- Render conversation history ----------
for msg in st.session_state.messages:
    avatar = "🧑‍💼" if msg["role"] == "user" else "📣"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])
        if msg.get("meta"):
            render_meta(msg["meta"])

# ---------- Chat input ----------
query = st.chat_input("Ask about content, campaigns, social, SEO, or brand guidelines...")

if query:
    st.session_state.messages.append({"role": "user", "content": query, "meta": None})
    with st.chat_message("user", avatar="🧑‍💼"):
        st.markdown(query)

    with st.chat_message("assistant", avatar="📣"):
        from orchestrator import run_pipeline

        agents = get_agents()
        live_state = {}

        def on_update(agent_key: str, status: str):
            live_state[agent_key] = status
            workflow_placeholder.markdown(render_agent_badges(live_state), unsafe_allow_html=True)

        with st.spinner("Agents at work..."):
            result = run_pipeline(agents, query, on_update=on_update)

        workflow_placeholder.caption("Idle — waiting for a question.")

        st.markdown(result["final_answer"])
        render_meta(result)

        st.download_button(
            "⬇️ Download this answer (Markdown)",
            data=result["final_answer"],
            file_name="marketing_assist_response.md",
            mime="text/markdown",
        )

    st.session_state.messages.append(
        {"role": "assistant", "content": result["final_answer"], "meta": result}
    )