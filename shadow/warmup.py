"""Check the model setup and load the models before a demo.

Usage: python -m shadow.warmup
Exits 0 when Ollama is reachable, both model tags are set and pulled, and the models are loaded.
"""
import sys
import time

from shadow import llm


def main():
    t0 = time.perf_counter()
    try:
        tags = llm.warmup(["planner", "checker"])
    except llm.LLMError as e:
        print(f"Not ready: {e}")
        return 2
    print(f"Ready: loaded {', '.join(tags)} in {time.perf_counter() - t0:.1f} s (kept in memory for {llm.KEEP_ALIVE}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
