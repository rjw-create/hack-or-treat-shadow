# gemma4-project

Hack or Treat hackathon entry (2026-10-31) for one category only: **Best use of Gemma 4**.
Candidate ideas are in `2026-10-31-ideas.md`. Chosen: **Shadow**, browser automations learned from one
recorded demonstration, run and self-repaired by local Gemma 4 (see README.md).

## Focus
- Gemma 4 must be essential to the project, not swappable for any chatbot. Favor what only open, local weights allow.
- Don't add ElevenLabs or other categories' features; separate projects cover those.
- This machine has a GPU shared with another hackathon project. Ask before starting long GPU jobs (training, large models).

## Status
- Stack: Python 3.11 in `.venv`, Playwright (only pip dependency), Ollama for Gemma 4 (E4B checker, 26B A4B planner if it runs well).
- Hardware: Intel Arc 140V integrated GPU, no CUDA, 32 GB shared RAM.
- Verify: `./scripts/check.sh` (Git Bash). Runs without a model; tests use a fake LLM.
- Model output is a JSON plan from a fixed action set, never code. Keep it that way; the runner only visits localhost.
