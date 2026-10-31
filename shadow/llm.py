"""Minimal client for the local Ollama HTTP API (standard library only).

Model tags come from environment variables:
  SHADOW_PLANNER_MODEL  plans and repairs (e.g. gemma4:e4b)
  SHADOW_CHECKER_MODEL  checks each step (e.g. gemma4:e4b)
"""
import base64
import json
import os
import urllib.error
import urllib.request

ROLE_ENV = {"planner": "SHADOW_PLANNER_MODEL", "checker": "SHADOW_CHECKER_MODEL"}
# Ollama unloads an idle model after 5 minutes by default; a demo can pause longer than that
# between commands, and reloading costs about 30 s on this machine.
KEEP_ALIVE = "30m"
PREFLIGHT_TIMEOUT_S = 10


class LLMError(RuntimeError):
    pass


def ollama_url():
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    return host if host.startswith("http") else "http://" + host


def model_for(role):
    name = os.environ.get(ROLE_ENV[role])
    if not name:
        raise LLMError(f"Set {ROLE_ENV[role]} to an Ollama model tag, e.g. gemma4:e4b (see `ollama list`).")
    return name


def request_json(path, body=None, timeout_s=600):
    """GET (body None) or POST to Ollama and return the parsed reply, with errors a person can act on."""
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(ollama_url() + path, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return json.load(resp)
    # HTTPError is a subclass of URLError, so it must be caught first: the server answered, with an error.
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        try:
            detail = json.loads(detail).get("error", detail)
        except (json.JSONDecodeError, AttributeError):
            pass
        raise LLMError(f"Ollama returned HTTP {e.code} for {path}: {detail}") from e
    except urllib.error.URLError as e:
        raise LLMError(f"Could not reach Ollama at {ollama_url()} ({e.reason}). "
                       "Start the Ollama app or run `ollama serve`.") from e
    except TimeoutError as e:
        raise LLMError(f"Ollama did not answer {path} within {timeout_s} s.") from e


def installed_models():
    return {m.get("name") for m in request_json("/api/tags", timeout_s=PREFLIGHT_TIMEOUT_S).get("models", [])}


def preflight(roles):
    """Fail fast, before a browser opens, if a role has no model set, Ollama is down, or a model isn't pulled."""
    wanted = {role: model_for(role) for role in roles}
    have = installed_models()
    # Ollama lists a tag given without a version as name:latest.
    missing = sorted({tag for tag in wanted.values() if tag not in have and f"{tag}:latest" not in have})
    if missing:
        raise LLMError("Not pulled in Ollama: " + ", ".join(missing) + ". Run: "
                       + "; ".join(f"ollama pull {tag}" for tag in missing))
    return wanted


def warmup(roles):
    """Load each role's model into memory now, so the first real call isn't slow. Returns the tags loaded."""
    tags = sorted(set(preflight(roles).values()))
    for tag in tags:
        # An empty prompt makes Ollama load the model without generating anything.
        request_json("/api/generate", {"model": tag, "prompt": "", "keep_alive": KEEP_ALIVE})
    return tags


def chat_json(role, prompt, images_png=(), schema=None, timeout_s=600, think=None):
    """Send one prompt (plus optional PNG bytes) and return the parsed JSON reply.

    think=False turns off Gemma 4's hidden reasoning (on by default in Ollama); None keeps the model default.
    """
    body = {
        "model": model_for(role),
        "stream": False,
        "format": schema or "json",
        "options": {"temperature": 0},
        "keep_alive": KEEP_ALIVE,
        "messages": [{
            "role": "user",
            "content": prompt,
            "images": [base64.b64encode(png).decode("ascii") for png in images_png],
        }],
    }
    if think is not None:
        body["think"] = think
    reply = request_json("/api/chat", body, timeout_s=timeout_s)
    text = reply.get("message", {}).get("content", "")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMError(f"Model did not return valid JSON: {text[:300]!r}") from e
