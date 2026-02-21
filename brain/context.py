from config import MAX_PROMPT_TOKENS, CHARS_PER_TOKEN, SYSTEM_GUARDRAILS

THREAD_CONTEXT_BUDGET = 8000   # tokens typical, 12000 worst case
THREAD_CONTEXT_MAX = 12000


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def assemble_messages(
    perception: str,
    identity: str,
    personality: str,
    brandon_facts: list[str],
    learned_facts: list[str],
    history: list[dict],
    user_message: str,
    session_summaries: list[str] | None = None,
    retrieved_memories: list[dict] | None = None,
) -> tuple[list[dict], int]:
    budget = MAX_PROMPT_TOKENS

    # P0 + P1 + P6: fixed costs (perception, identity, guardrails, user message) — never trimmed
    fixed_system = perception + "\n\n" + identity + "\n\n" + SYSTEM_GUARDRAILS
    fixed_cost = estimate_tokens(fixed_system) + estimate_tokens(user_message)

    if fixed_cost >= budget:
        return (
            [
                {"role": "system", "content": fixed_system},
                {"role": "user", "content": user_message},
            ],
            fixed_cost,
        )

    remaining = budget - fixed_cost
    system_parts = [fixed_system]

    # P2: personality — include whole or drop
    if personality:
        personality_cost = estimate_tokens(personality)
        if personality_cost <= remaining:
            system_parts.append(personality)
            remaining -= personality_cost

    # P3: facts (seed + learned) — seed facts first, then learned newest-first
    facts_header = "[What you know about Brandon]\n"
    header_cost = estimate_tokens(facts_header)

    included_seed = []
    if brandon_facts:
        for fact in brandon_facts:
            fact_line = f"- {fact}"
            fact_cost = estimate_tokens(fact_line)
            if fact_cost <= remaining - header_cost:
                included_seed.append(fact_line)
                remaining -= fact_cost

    included_learned = []
    if learned_facts:
        for fact in reversed(learned_facts):  # newest first
            fact_line = f"- {fact}"
            fact_cost = estimate_tokens(fact_line)
            if fact_cost <= remaining - header_cost:
                included_learned.append(fact_line)
                remaining -= fact_cost

    all_facts = included_seed + list(reversed(included_learned))
    if all_facts:
        if header_cost <= remaining:
            facts_section = facts_header + "\n".join(all_facts)
            system_parts.append(facts_section)
            remaining -= header_cost
        else:
            # Can't fit header, reclaim fact tokens
            for fact_line in all_facts:
                remaining += estimate_tokens(fact_line)

    # P4: retrieved memories — associative recall from all memory types
    if retrieved_memories:
        for mem in retrieved_memories:
            mem_line = f"[Memory] {mem['text']}"
            mem_cost = estimate_tokens(mem_line)
            if mem_cost <= remaining:
                system_parts.append(mem_line)
                remaining -= mem_cost

    # P5: session summaries — oldest first, drop oldest first
    if session_summaries:
        for summary in session_summaries:
            summary_cost = estimate_tokens(summary)
            if summary_cost <= remaining:
                system_parts.append(summary)
                remaining -= summary_cost

    # P6: conversation history — most recent backward, stop at first that doesn't fit
    included_history: list[dict] = []
    for msg in reversed(history):
        msg_cost = estimate_tokens(msg["content"])
        if msg_cost <= remaining:
            included_history.insert(0, msg)
            remaining -= msg_cost
        else:
            break

    system_content = "\n\n".join(system_parts)
    tokens_used = budget - remaining

    return (
        [{"role": "system", "content": system_content}]
        + included_history
        + [{"role": "user", "content": user_message}],
        tokens_used,
    )


def assemble_thread_context(
    perception: str,
    identity: str,
    personality: str,
    relationship_file: str,
    thread_summary: str,
    recent_messages: list[dict],
    user_message: str,
    searched_messages: list[dict] | None = None,
) -> tuple[list[dict], int]:
    """Assemble context for a thread reply — smaller budget than general context."""
    budget = THREAD_CONTEXT_MAX

    # Fixed: perception + identity + guardrails + user message
    fixed_system = perception + "\n\n" + identity + "\n\n" + SYSTEM_GUARDRAILS
    fixed_cost = estimate_tokens(fixed_system) + estimate_tokens(user_message)

    if fixed_cost >= budget:
        return [
            {"role": "system", "content": fixed_system},
            {"role": "user", "content": user_message},
        ], fixed_cost

    remaining = budget - fixed_cost
    system_parts = [fixed_system]

    # Personality
    if personality:
        cost = estimate_tokens(personality)
        if cost <= remaining:
            system_parts.append(personality)
            remaining -= cost

    # Relationship file
    if relationship_file:
        rel_section = f"[Your relationship with the other participant]\n{relationship_file}"
        cost = estimate_tokens(rel_section)
        if cost <= remaining:
            system_parts.append(rel_section)
            remaining -= cost

    # Thread summary
    if thread_summary:
        summary_section = f"[Thread summary]\n{thread_summary}"
        cost = estimate_tokens(summary_section)
        if cost <= remaining:
            system_parts.append(summary_section)
            remaining -= cost

    # Searched messages (optional context from keyword search)
    if searched_messages:
        for msg in searched_messages:
            line = f"[Earlier in thread] {msg['author']}: {msg['content']}"
            cost = estimate_tokens(line)
            if cost <= remaining:
                system_parts.append(line)
                remaining -= cost

    # Recent messages as conversation history — newest first, drop oldest
    included_history: list[dict] = []
    for msg in reversed(recent_messages):
        cost = estimate_tokens(msg["content"])
        if cost <= remaining:
            included_history.insert(0, msg)
            remaining -= cost
        else:
            break

    system_content = "\n\n".join(system_parts)
    tokens_used = budget - remaining

    return (
        [{"role": "system", "content": system_content}]
        + included_history
        + [{"role": "user", "content": user_message}],
        tokens_used,
    )
