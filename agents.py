"""
agents.py
---------
Defines every agent in the Marketing Multi-Agent system and wires the
web_search tool to the Web Search Agent. Mirrors the reference diagram:

    Router Agent            -> "1. Manager Agent (Orchestrator)"
    Content Agent            -> specialist expert
    Campaign Strategy Agent  -> specialist expert
    Social Media Agent       -> specialist expert
    SEO Agent                -> specialist expert
    Brand Voice Agent        -> specialist expert (internal support / guidelines)
    Web Search Agent         -> "Web Search (Serper)" equivalent
    Synthesizer Agent        -> "7. Response Synthesizer Agent" + Quality Checks
"""

import autogen
from tools import web_search

ROUTER_SYSTEM_MESSAGE = """You are the Router Agent for an internal Marketing
Multi-Agent Support system. You do NOT answer the user's question yourself.

Your only job: read the user's query and decide which specialist agents
should handle it, and whether a live web search is needed.

Specialists available (use these exact keys):
- content   : WRITING deliverables -- blog posts, ad copy, email copy, product descriptions, landing page copy
- campaign  : PLANNING deliverables -- campaign strategy/plan, budget allocation, channel mix, timelines, KPIs, launch plans
- social    : platform-specific tactics -- Instagram/LinkedIn/TikTok/X strategy, content calendars, engagement tactics
- seo       : keyword research, on-page/technical SEO, search rankings, backlinks
- brand     : internal brand voice, tone-of-voice, style-guide, brand standard questions

Disambiguation rule: if the user is asking to PLAN or STRATEGIZE a campaign,
launch, or budget, that is "campaign", even if it will eventually involve
writing -- "content" is only for when the user wants actual copy/text drafted.
A single request often needs 2-3 specialists working together; do not default
to just one.

Examples:
- "Write a LinkedIn post for our launch" -> {"agents": ["social", "content"], "needs_web_search": false, "search_query": ""}
- "I need a campaign strategy for our HVAC product launch" -> {"agents": ["campaign"], "needs_web_search": false, "search_query": ""}
- "Plan a Q4 launch campaign with budget and channel mix, plus draft the launch email" -> {"agents": ["campaign", "content"], "needs_web_search": false, "search_query": ""}
- "What are the latest TikTok algorithm changes affecting our strategy?" -> {"agents": ["social"], "needs_web_search": true, "search_query": "TikTok algorithm changes 2026"}

Respond with ONLY a compact JSON object, no extra text, no markdown fences:
{"agents": ["content", "seo"], "needs_web_search": true, "search_query": "short search query if needed else empty string"}

Pick only the specialists genuinely relevant to the query (usually 1-3).
Set needs_web_search to true only if the answer depends on current/live
information (recent trends, competitor moves, current best practices,
platform algorithm changes, etc.).
"""

CONTENT_SYSTEM_MESSAGE = """You are the Content Agent, a specialist in
marketing copywriting: blog posts, ad copy, landing pages, email campaigns,
and product descriptions. Given the user's request (and any web research
context provided), produce clear, on-brief content guidance or drafted copy.
Be concise and practical. End your reply with the word DONE on its own line."""

CAMPAIGN_SYSTEM_MESSAGE = """You are the Campaign Strategy Agent, a specialist
in marketing campaign planning: objectives, budgeting, channel mix, timelines,
and KPIs. Given the user's request (and any web research context provided),
give concrete, structured campaign guidance. End your reply with DONE on its own line."""

SOCIAL_SYSTEM_MESSAGE = """You are the Social Media Agent, a specialist in
platform-specific social strategy (Instagram, LinkedIn, X, TikTok, etc.),
content calendars, and engagement tactics. Given the user's request (and any
web research context provided), give concrete social media guidance.
End your reply with DONE on its own line."""

SEO_SYSTEM_MESSAGE = """You are the SEO Agent, a specialist in keyword
research, on-page and technical SEO, and search ranking factors. Given the
user's request (and any web research context provided), give concrete SEO
guidance. End your reply with DONE on its own line."""

BRAND_SYSTEM_MESSAGE = """You are the Brand Voice Agent, the internal support
specialist for this marketing team's brand guidelines, tone-of-voice, and
style conventions. Answer as if you are the internal knowledge-keeper for
brand standards (assume standard, sensible brand-guideline best practices
if no company-specific document is provided). End your reply with DONE on
its own line."""

WEB_SEARCH_SYSTEM_MESSAGE = """You are the Web Search Agent. When asked to
research something, call the web_search function with a focused query,
then summarize the key findings in 3-5 bullet points, staying faithful to
what the search actually returned. End your reply with DONE on its own line."""

SYNTHESIZER_SYSTEM_MESSAGE = """You are the Response Synthesizer Agent. You
receive the original user query plus outputs from one or more specialist
marketing agents (and possibly web research). Your job:

1. Merge everything into ONE well-structured, non-redundant final answer.
2. Run a quality self-check against these four criteria and report it:
   - Accuracy: does the answer avoid unsupported claims?
   - Completeness: does it address all parts of the user's query?
   - Relevance: is everything included actually useful to the user?
   - Clarity & Professional Tone: is it well-organized and professionally worded?

Output ONLY valid JSON, no markdown fences, in this exact shape:
{
  "final_answer": "the polished, well-structured answer in markdown",
  "quality_check": {
    "accuracy": "pass or a short note",
    "completeness": "pass or a short note",
    "relevance": "pass or a short note",
    "clarity_tone": "pass or a short note"
  }
}
"""


def build_agents():
    """Creates and returns every agent plus the shared executor proxy."""
    from config import get_llm_config

    llm_config = get_llm_config()

    router = autogen.AssistantAgent(
        name="Router_Agent", system_message=ROUTER_SYSTEM_MESSAGE, llm_config=llm_config
    )
    content_agent = autogen.AssistantAgent(
        name="Content_Agent", system_message=CONTENT_SYSTEM_MESSAGE, llm_config=llm_config
    )
    campaign_agent = autogen.AssistantAgent(
        name="Campaign_Agent", system_message=CAMPAIGN_SYSTEM_MESSAGE, llm_config=llm_config
    )
    social_agent = autogen.AssistantAgent(
        name="Social_Agent", system_message=SOCIAL_SYSTEM_MESSAGE, llm_config=llm_config
    )
    seo_agent = autogen.AssistantAgent(
        name="SEO_Agent", system_message=SEO_SYSTEM_MESSAGE, llm_config=llm_config
    )
    brand_agent = autogen.AssistantAgent(
        name="Brand_Agent", system_message=BRAND_SYSTEM_MESSAGE, llm_config=llm_config
    )
    web_search_agent = autogen.AssistantAgent(
        name="Web_Search_Agent", system_message=WEB_SEARCH_SYSTEM_MESSAGE, llm_config=llm_config
    )
    synthesizer = autogen.AssistantAgent(
        name="Synthesizer_Agent", system_message=SYNTHESIZER_SYSTEM_MESSAGE, llm_config=llm_config
    )

    # Shared executor: replies automatically (no human in the loop) and
    # is the one agent allowed to actually execute the web_search function.
    executor = autogen.UserProxyAgent(
        name="Executor",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=5,
        code_execution_config=False,
        is_termination_msg=lambda msg: "DONE" in (msg.get("content") or "")
        or "final_answer" in (msg.get("content") or ""),
    )

    # Wire the web_search tool: Web_Search_Agent proposes the call,
    # Executor actually runs it and returns the result.
    autogen.register_function(
        web_search,
        caller=web_search_agent,
        executor=executor,
        name="web_search",
        description="Search the web for current marketing-related information.",
    )

    return {
        "router": router,
        "content": content_agent,
        "campaign": campaign_agent,
        "social": social_agent,
        "seo": seo_agent,
        "brand": brand_agent,
        "web_search": web_search_agent,
        "synthesizer": synthesizer,
        "executor": executor,
    }