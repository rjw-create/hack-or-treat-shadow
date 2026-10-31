"""Minimal client for the local Ollama HTTP API (standard library only).

Model tags come from environment variables because the exact Gemma 4 tag names
are confirmed at step 0, not assumed here:
  SHADOW_PLANNER_MODEL  plans and repairs (26B A4B if it runs well, else E4B)
  SHADOW_CHECKER_MODEL  checks screenshots after each step (E4B)
"""
import base64
import json
import os
import urllib.error
import urllib.request

ROLE_ENV = {"planner": "SHADOW_PLANNER_MODEL", "checker": "SHADOW_CHECKER_MODEL"}


class LLMError(RuntimeError):
    pass


def ollama_url():
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    return host if host.startswith("http") else "http://" + host


def model_for(role):
    name = os.environ.get(ROLE_ENV[role])
    if not name:
        raise LLMError(f"Set {ROLE_ENV[role]} to an Ollama model tag (see `ollama list`).")
    return name


def chat_json(role, prompt, images_png=(), schema=None, timeout_s=600, think=None):
    """Send one prompt (plus optional PNG bytes) and return the parsed JSON reply.

    think=False turns off Gemma 4's hidden reasoning (on by default in Ollama); None keeps the model default.
    """
    body = {
        "model": model_for(role),
        "stream": False,
        "format": schema or "json",
        "options": {"temperature": 0},
        "messages": [{
            "role": "user",
            "content": prompt,
            "images": [base64.b64encode(png).decode("ascii") for png in images_png],
        }],
    }
    if think is not None:
        body["think"] = think
    req = urllib.request.Request(
        ollama_url() + "/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            reply = json.load(resp)
    except urllib.error.URLError as e:
        raise LLMError(f"Could not reach Ollama at {ollama_url()}: {e}") from e
    text = reply.get("message", {}).get("content", "")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMError(f"Model did not return valid JSON: {text[:300]!r}") from e
