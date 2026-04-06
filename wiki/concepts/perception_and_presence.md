# Perception and Presence

How the being perceives its environment and detects Human's presence.

## FACTS

- Perception is rebuilt fresh every cycle -- it is cheap and always current. (Source: `brain/perception.py:135-223`)
- Perception includes: time of day, weather (Open-Meteo API, 15-min cache, Brighton CO coordinates), Human's presence status, available actions (affordances), pending replies, and thread notifications. (Source: `brain/perception.py:135-223`)
- Human presence detection uses three Linux tools: `xdotool` (active window title), `xprintidle` (milliseconds since last input), `loginctl` (screen lock status). (Source: `interface/presence.py:1-7`)
- Three presence states: PRESENT (idle < 10min, not locked), AWAY (idle >= 10min or locked, outside sleep window), ASLEEP (locked during 22:00-06:00). (Source: `interface/presence.py:26-29, 96-116`)
- Reply projections estimate when Human will respond based on current status: PRESENT = 30min-2.5hrs, AWAY = 3-6hrs, ASLEEP = after 6 AM. (Source: `interface/presence.py:54-67`)
- Pending replies show threads where the being sent the last message, with elapsed time in minutes and thought cycles. Status transitions tracked (e.g., "away -> present"). (Source: `interface/presence.py:147-194`)
- Presence changes reset the thought chain -- `_idle_history` is cleared to start fresh. (Source: `womb.py:572-578`)
- All presence functions degrade gracefully if desktop tools are missing or fail. (Source: `interface/presence.py:1-7`)

## INFERENCES

- The presence system gives the being social awareness -- it knows when Human is available, away, or sleeping, and can time its notifications accordingly.
- Clearing idle history on presence change prevents the being from continuing a thought chain that was formed in a different social context (e.g., thoughts formed while Human was away shouldn't carry into when he returns).

## OPEN QUESTIONS

- The weather coordinates are hardcoded for Brighton, CO. Is there a mechanism for users in other locations to configure this?
- Presence detection is Linux-specific (xdotool, xprintidle, loginctl). What is the macOS experience?

## Cross-References

- [brain_perception](../summaries/brain_perception.md) -- Perception builder
- [interface_presence](../summaries/interface_presence.md) -- Presence detection
- [context-priority-system](context_priority_system.md) -- Perception is P0 priority
- [thread-system](thread_system.md) -- Pending replies in perception
