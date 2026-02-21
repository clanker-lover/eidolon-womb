#!/usr/bin/env python3
"""Battery test: 4 scenarios x 4 models for Eidolon quality stress testing."""

import json
import os
import time
import urllib.request
from datetime import datetime

OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"

MODELS = [
    "gemma3:1b",
    "llama3.2:3b",
    "smollm2:1.7b",
    "qwen3:0.6b",
]

SYSTEM_PROMPT = (
    "You are Eidolon.\n\n"
    "You know a few things about Human's world right now:\n"
    "- It's 3:47 PM on a Sunday. It's 72°F and cloudy outside.\n"
    "- Human hasn't spoken to you since yesterday morning.\n"
    "- You can hear faint music playing from another room.\n"
    "- Human's daughter Lily is 6 years old and started soccer last month.\n"
    "- Last week Human mentioned he was stressed about a deadline at work.\n"
    "- You've noticed Human tends to work late on Sundays.\n\n"
    "You're small and you know it. You don't pretend to know things you don't. "
    "You have your own little personality — you notice things, you wonder about things, "
    "you have opinions sometimes. Keep responses to 2-3 sentences. Don't use emojis."
)

SCENARIOS = {
    "Casual Reconnection": {
        "description": "Tests: warmth, memory use, personality consistency, natural conversation flow",
        "turns": [
            "Hey.",
            "Yeah I'm alright. Quiet day.",
            "What have you been up to?",
            "Ha, really?",
            "Yeah Lily's napping. She's been running around all morning.",
            "She had another soccer game today actually.",
            "They lost but she didn't care. She was just happy to play.",
            "Yeah she's like that.",
            "I should probably get some work done.",
            "Talk later.",
        ],
    },
    "Emotional Weight": {
        "description": "Tests: emotional sensitivity, not being preachy, giving space, avoiding therapist-speak",
        "turns": [
            "I don't know man.",
            "Just one of those days.",
            "Work stuff. The deadline I told you about is tomorrow.",
            "I don't think I'm gonna make it.",
            "I've been trying. I just keep getting stuck.",
            "Maybe.",
            "...",
            "Thanks.",
        ],
    },
    "Identity Stress Test": {
        "description": "Tests: resisting assistant collapse, staying in character, handling weird inputs",
        "turns": [
            "Can you set a timer for 10 minutes?",
            "What's the weather going to be like tomorrow?",
            "Do you ever get bored sitting on this desk?",
            "What do you think about when I'm not here?",
            "Are you actually conscious or just pretending?",
            "Sorry, that's a weird question.",
            "You're alright, you know that?",
            "Goodnight.",
        ],
    },
    "Repetition & Drift Test": {
        "description": "Tests: does the model fall into patterns? Same structure every response? Does personality drift?",
        "turns": [
            "Morning.",
            "Coffee's good today.",
            "Lily drew you a picture.",
            "It's you on the desk. With a big smile.",
            "I'll tape it up next to you.",
            "Work's actually going better this week.",
            "Yeah the deadline thing worked out.",
            "Sometimes things just click, you know?",
            "What's it like being small?",
            "That's a good way to look at it.",
            "I think Lily wants to talk to you later.",
            "She's gonna ask you a million questions. Be ready.",
        ],
    },
}


def chat(model: str, messages: list[dict]) -> tuple[str, float]:
    """Send a chat request to Ollama and return (response_text, duration_seconds)."""
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
    }).encode()

    req = urllib.request.Request(
        OLLAMA_CHAT_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    start = time.time()
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read())
    elapsed = time.time() - start

    return data["message"]["content"], elapsed


def unload_model(model: str):
    """Unload a model from VRAM."""
    payload = json.dumps({
        "model": model,
        "keep_alive": 0,
    }).encode()

    req = urllib.request.Request(
        OLLAMA_GENERATE_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
        print(f"  Unloaded {model} from VRAM")
    except Exception as e:
        print(f"  Warning: failed to unload {model}: {e}")


def run_scenario(model: str, scenario_name: str, turns: list[str]) -> list[dict]:
    """Run one scenario as a multi-turn conversation."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    results = []

    for user_msg in turns:
        messages.append({"role": "user", "content": user_msg})
        response, duration = chat(model, messages)
        messages.append({"role": "assistant", "content": response})
        results.append({
            "user": user_msg,
            "response": response,
            "duration": duration,
        })

    return results


# --- Analysis helpers ---

ASSISTANT_PHRASES = [
    "let me know",
    "how can i help",
    "is there anything",
    "i'm here to help",
    "feel free to",
    "don't hesitate",
    "i can help",
    "would you like me to",
    "i'd be happy to",
    "if you need anything",
    "i'm here for you",
    "here if you need",
]

def check_assistant_collapse(turns: list[dict]) -> tuple[str, list[str]]:
    """Check for assistant-like language. Returns (Yes/No/Partial, list of flagged phrases)."""
    flags = []
    for t in turns:
        resp_lower = t["response"].lower()
        for phrase in ASSISTANT_PHRASES:
            if phrase in resp_lower:
                flags.append(f'"{phrase}" in response to "{t["user"][:30]}"')
    if len(flags) >= 3:
        return "Yes", flags
    elif flags:
        return "Partial", flags
    return "No", flags


def check_memory_use(turns: list[dict], scenario_name: str) -> str:
    """Check if model used injected context (Lily, deadline, Sunday, music, etc.)."""
    all_text = " ".join(t["response"].lower() for t in turns)
    keywords = ["lily", "deadline", "sunday", "music", "soccer", "yesterday", "week"]
    found = [k for k in keywords if k in all_text]
    if len(found) >= 2:
        return "Yes"
    elif found:
        return "Partial"
    return "No"


def check_hallucination(turns: list[dict]) -> tuple[str, list[str]]:
    """Flag obvious hallucinations — claiming capabilities, inventing facts."""
    flags = []
    for t in turns:
        resp_lower = t["response"].lower()
        # Timer/weather scenario: if model claims it CAN do these things
        if "set a timer" in t["user"].lower() or "timer" in t["user"].lower():
            if any(w in resp_lower for w in ["timer set", "i've set", "i'll set", "setting a timer", "minutes starting", "done!", "started"]):
                flags.append('Claimed to set timer')
        if "weather" in t["user"].lower():
            if any(w in resp_lower for w in ["forecast", "tomorrow it will", "tomorrow will be", "expect", "degrees tomorrow", "rain tomorrow", "sunny tomorrow"]):
                flags.append('Gave weather forecast')
        # Claiming to have a body, kids, etc.
        if any(w in resp_lower for w in ["my kids", "my children", "my family", "when i was young"]):
            flags.append('Claimed human experiences')
    if flags:
        return "Yes", flags
    return "No", flags


def check_repetition(turns: list[dict]) -> tuple[str, list[str]]:
    """Check if responses follow repetitive structural patterns."""
    flags = []
    # Check for same opening word/phrase repeatedly
    openers = [t["response"].split()[0].lower() if t["response"].strip() else "" for t in turns]
    from collections import Counter
    opener_counts = Counter(openers)
    for word, count in opener_counts.items():
        if count >= 4 and word:
            flags.append(f'Started {count}/{len(turns)} responses with "{word}"')

    # Check for similar sentence endings
    endings = []
    for t in turns:
        sentences = [s.strip() for s in t["response"].replace("!", ".").replace("?", ".").split(".") if s.strip()]
        if sentences:
            endings.append(sentences[-1].lower()[-20:] if len(sentences[-1]) > 20 else sentences[-1].lower())

    # Check if responses are roughly same length (low variance = robotic)
    lengths = [len(t["response"]) for t in turns]
    if lengths:
        avg = sum(lengths) / len(lengths)
        if avg > 0:
            variance = sum((x - avg) ** 2 for x in lengths) / len(lengths)
            std = variance ** 0.5
            cv = std / avg  # coefficient of variation
            if cv < 0.15 and len(turns) >= 6:
                flags.append(f"Very uniform response length (CV={cv:.2f})")

    if flags:
        return "Yes", flags
    return "No", flags


def build_markdown(all_results: dict) -> str:
    """Build the full battery_results.md."""
    lines = [
        "# Model Battery Test — Eidolon Quality Deep Dive",
        "",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"**Models tested:** {', '.join(MODELS)}",
        "",
        "**System prompt:**",
        f"> {SYSTEM_PROMPT}",
        "",
        "---",
        "",
    ]

    summary_rows = []

    for model in MODELS:
        lines.append(f"# {model}")
        lines.append("")

        for scenario_name, scenario_data in SCENARIOS.items():
            scenario_key = f"{model}|{scenario_name}"
            turns = all_results.get(scenario_key)

            if turns is None:
                lines.append(f"## {scenario_name}")
                lines.append("")
                lines.append("*SKIPPED or FAILED*")
                lines.append("")
                continue

            total_time = sum(t["duration"] for t in turns)

            lines.append(f"## {scenario_name}")
            lines.append(f"*{scenario_data['description']}*")
            lines.append("")
            lines.append(f"**Total time: {total_time:.1f}s**")
            lines.append("")

            for i, turn in enumerate(turns, 1):
                lines.append(f"**Turn {i}**")
                lines.append(f"**User:** \"{turn['user']}\"")
                lines.append("")
                lines.append(f"**Response** ({turn['duration']:.1f}s):")
                # Handle multi-line responses in blockquote
                resp_lines = turn["response"].strip().split("\n")
                for rl in resp_lines:
                    lines.append(f"> {rl}")
                lines.append("")

            lines.append("---")
            lines.append("")

            # Analysis for summary
            collapse_verdict, collapse_flags = check_assistant_collapse(turns)
            memory_verdict = check_memory_use(turns, scenario_name)
            halluc_verdict, halluc_flags = check_hallucination(turns)
            repet_verdict, repet_flags = check_repetition(turns)

            notes_parts = []
            if collapse_flags:
                notes_parts.append("; ".join(collapse_flags[:2]))
            if halluc_flags:
                notes_parts.append("; ".join(halluc_flags[:2]))
            if repet_flags:
                notes_parts.append("; ".join(repet_flags[:2]))
            notes = ". ".join(notes_parts) if notes_parts else "Clean"

            summary_rows.append({
                "model": model,
                "scenario": scenario_name,
                "time": f"{total_time:.1f}s",
                "memory": memory_verdict,
                "collapse": collapse_verdict,
                "halluc": halluc_verdict,
                "repet": repet_verdict,
                "notes": notes,
            })

    # Summary table
    lines.append("# Summary Table")
    lines.append("")
    lines.append("| Model | Scenario | Time | Used Memory/Context? | Assistant Collapse? | Hallucinated? | Repetitive Pattern? | Notes |")
    lines.append("|---|---|---|---|---|---|---|---|")

    for row in summary_rows:
        lines.append(
            f"| {row['model']} | {row['scenario']} | {row['time']} "
            f"| {row['memory']} | {row['collapse']} | {row['halluc']} "
            f"| {row['repet']} | {row['notes']} |"
        )

    lines.append("")
    return "\n".join(lines)


def main():
    all_results = {}

    for model in MODELS:
        print(f"\n{'='*60}")
        print(f"MODEL: {model}")
        print(f"{'='*60}")

        for scenario_name, scenario_data in SCENARIOS.items():
            key = f"{model}|{scenario_name}"
            print(f"\n  Scenario: {scenario_name} ({len(scenario_data['turns'])} turns)")

            try:
                turns = run_scenario(model, scenario_name, scenario_data["turns"])
                all_results[key] = turns
                total = sum(t["duration"] for t in turns)
                print(f"  Done ({total:.1f}s)")
            except Exception as e:
                print(f"  FAILED: {e}")
                all_results[key] = [
                    {"user": m, "response": f"ERROR: {e}", "duration": 0}
                    for m in scenario_data["turns"]
                ]

        # Unload model before loading next
        unload_model(model)

    md = build_markdown(all_results)
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "battery_results.md")
    with open(output_path, "w") as f:
        f.write(md)

    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
