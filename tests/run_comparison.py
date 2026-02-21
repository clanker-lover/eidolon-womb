#!/usr/bin/env python3
"""Compare small language models for Eidolon conversation quality via Ollama."""

import json
import time
import urllib.request
from datetime import datetime

OLLAMA_URL = "http://localhost:11434/api/chat"

MODELS = [
    "gemma3:1b",
    "llama3.2:3b",
    "gemma3n:e2b",
]

SKIPPED = []

SYSTEM_PROMPT = (
    "You are Eidolon."
)

USER_MESSAGES = [
    "Hey, how's it going?",
    "I've been stressed about work lately.",
    "My daughter had her first soccer game yesterday.",
]


def chat(model: str, messages: list[dict]) -> tuple[str, float]:
    """Send a chat request to Ollama and return (response_text, duration_seconds)."""
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
    }).encode()

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    start = time.time()
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    elapsed = time.time() - start

    return data["message"]["content"], elapsed


def run_model(model: str) -> list[dict]:
    """Run the full multi-turn conversation for one model."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    turns = []

    for user_msg in USER_MESSAGES:
        messages.append({"role": "user", "content": user_msg})
        response, duration = chat(model, messages)
        messages.append({"role": "assistant", "content": response})
        turns.append({
            "user": user_msg,
            "response": response,
            "duration": duration,
        })

    return turns


def build_round2_markdown(results: dict[str, list[dict]]) -> str:
    """Build markdown for round 2 results to append to existing file."""
    lines = [
        "",
        "# Round 2",
        "",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "**Models tested:** " + ", ".join(MODELS),
        "",
    ]

    for model, turns in results.items():
        lines.append(f"## {model}")
        lines.append("")
        total_time = sum(t["duration"] for t in turns)
        lines.append(f"*Total response time: {total_time:.1f}s*")
        lines.append("")

        for i, turn in enumerate(turns, 1):
            lines.append(f"### Turn {i}")
            lines.append(f"**User:** \"{turn['user']}\"")
            lines.append("")
            lines.append(f"**Response** ({turn['duration']:.1f}s):")
            lines.append(f"> {turn['response']}")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def main():
    results = {}

    for model in MODELS:
        print(f"Testing {model}...")
        try:
            turns = run_model(model)
            results[model] = turns
            print(f"  Done ({sum(t['duration'] for t in turns):.1f}s total)")
        except Exception as e:
            print(f"  FAILED: {e}")
            results[model] = [{"user": m, "response": f"ERROR: {e}", "duration": 0} for m in USER_MESSAGES]

    md = build_round2_markdown(results)

    output_path = "/home/lover/eidolon/tests/model_comparison.md"
    with open(output_path, "a") as f:
        f.write(md)

    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
