"""
config.py
---------
Central place to build the LLM config used by every AutoGen agent.

Reads credentials from environment variables so no keys are hard-coded.
Works with:
  - OpenAI directly            -> set OPENAI_API_KEY
  - Any OpenAI-compatible proxy (Azure, LiteLLM, Ollama, etc.) -> set OPENAI_BASE_URL

If you're running this for a class assignment and only have an
Anthropic key, the easiest path is to put a LiteLLM proxy in front of
Claude and point OPENAI_BASE_URL at it -- AutoGen only speaks the
OpenAI-style chat completions schema natively.
"""

import logging
import os
import warnings

from dotenv import load_dotenv

load_dotenv()

# flaml.automl is an optional AutoGen dependency for hyperparameter tuning
# that this project doesn't use -- silence its startup UserWarning.
warnings.filterwarnings("ignore", message=".*flaml.automl is not available.*")

# pyautogen's client does a client-side regex sanity-check on API key format
# that predates OpenAI's newer "sk-proj-..." project-scoped keys, so it logs
# a false-positive warning even when the key is valid and works fine against
# the real API. Silence it at the logging level (this does NOT affect
# whether the key actually works -- only whether this stale check complains).
logging.getLogger("autogen.oai.client").setLevel(logging.ERROR)


def get_llm_config(temperature: float = 0.3) -> dict:
    api_key = os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL")  # optional, for proxies
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    if not api_key:
        raise ValueError(
            "No API key found. Set OPENAI_API_KEY as an environment variable "
            "(or in a .env file) before starting the app."
        )

    config_entry = {"model": model, "api_key": api_key}
    if base_url:
        config_entry["base_url"] = base_url

    return {
        "config_list": [config_entry],
        "temperature": temperature,
        "timeout": 90,
        "cache_seed": None,  # disable caching so answers stay fresh per query
    }