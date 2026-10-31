"""Plan schema: the only shape of model output Shadow will act on.

The model never writes code. It writes steps from a fixed set of actions, and these
functions reject anything else before the browser sees it.
"""
from urllib.parse import urlparse

ACTIONS = ("goto", "click", "fill", "select", "press")
NEEDS_TARGET = ("click", "fill", "select", "press")
NEEDS_VALUE = ("goto", "fill", "select", "press")
ALLOWED_HOSTS = ("localhost", "127.0.0.1")


class PlanError(ValueError):
    pass


def is_allowed_url(url):
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and parsed.hostname in ALLOWED_HOSTS


def validate_step(step, index=0):
    where = f"step {index + 1}"
    if not isinstance(step, dict):
        raise PlanError(f"{where}: must be an object")
    action = step.get("action")
    if action not in ACTIONS:
        raise PlanError(f"{where}: action {action!r} is not one of {ACTIONS}")
    for key in ("intent", "expected"):
        if not isinstance(step.get(key), str) or not step[key].strip():
            raise PlanError(f"{where}: {key!r} must be a non-empty string")
    if action in NEEDS_TARGET:
        target = step.get("target")
        if not (isinstance(target, dict)
                and isinstance(target.get("role"), str) and target["role"]
                and isinstance(target.get("name"), str) and target["name"]):
            raise PlanError(f"{where}: {action} needs target with 'role' and 'name'")
    if action in NEEDS_VALUE and not isinstance(step.get("value"), str):
        raise PlanError(f"{where}: {action} needs a string 'value'")
    if action == "goto" and not is_allowed_url(step["value"]):
        raise PlanError(f"{where}: URL {step['value']!r} is outside the localhost allowlist")
    return step


def validate_plan(plan):
    if not isinstance(plan, dict) or not isinstance(plan.get("steps"), list) or not plan["steps"]:
        raise PlanError("plan must be an object with a non-empty 'steps' list")
    for i, step in enumerate(plan["steps"]):
        validate_step(step, i)
    return plan


def locate(page, target):
    """The one place a target becomes a Playwright locator, shared by the runner and the compiler."""
    return page.get_by_role(target["role"], name=target["name"], exact=True)


def locator_code(target):
    # repr() makes model-supplied text safe to embed as a Python string literal.
    return f"page.get_by_role({target['role']!r}, name={target['name']!r}, exact=True)"
