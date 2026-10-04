"""
Talks to a model running locally in Ollama.

Privacy guard rails:
  1. The Ollama address must be localhost, otherwise we stop.
  2. Ollama "cloud" models (which run on remote servers) are refused.
  3. The HTTP session ignores proxy settings, so requests can't be routed
     through a corporate or system proxy.
"""
import json
import re
from urllib.parse import urlparse

import requests

import config

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class LocalLLMError(RuntimeError):
    pass


def _session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False  # ignore HTTP(S)_PROXY env vars: traffic stays on this machine
    return s


def assert_local(url: str, model: str) -> None:
    host = urlparse(url).hostname
    if host not in LOCAL_HOSTS:
        raise LocalLLMError(
            f"Refusing to send CIM text to '{host}'. OLLAMA_URL must be localhost."
        )
    if "cloud" in model.lower():
        raise LocalLLMError(
            f"'{model}' is an Ollama cloud model, which runs on remote servers. "
            "Pick a model that is downloaded to this computer."
        )


def list_local_models(url: str = config.OLLAMA_URL) -> list[str]:
    """Names of models downloaded into Ollama (cloud models filtered out)."""
    assert_local(url, "")
    try:
        r = _session().get(f"{url}/api/tags", timeout=5)
        r.raise_for_status()
    except requests.RequestException as e:
        raise LocalLLMError(
            "Can't reach Ollama on this computer. Is the Ollama app running?"
        ) from e
    names = [m["name"] for m in r.json().get("models", [])]
    return [n for n in names if "cloud" not in n.lower()]


def parse_json(text: str) -> dict:
    """Pull the JSON object out of a model reply (tolerates stray text)."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in reply")
    return json.loads(text[start : end + 1])


def chat_json(
    system: str,
    user: str,
    model: str = config.DEFAULT_MODEL,
    url: str = config.OLLAMA_URL,
    retries: int = 1,
) -> dict:
    """Send one prompt to the local model and return its JSON answer."""
    assert_local(url, model)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "format": "json",  # Ollama constrains the output to valid JSON
        "options": {"temperature": config.TEMPERATURE, "num_ctx": config.NUM_CTX},
    }
    last_error = None
    for _ in range(retries + 1):
        try:
            r = _session().post(
                f"{url}/api/chat", json=payload, timeout=config.REQUEST_TIMEOUT
            )
            r.raise_for_status()
            return parse_json(r.json()["message"]["content"])
        except (requests.RequestException, ValueError, KeyError) as e:
            last_error = e
    raise LocalLLMError(f"Local model call failed: {last_error}")
