# Security Model

## ⚠️ Local Operation Only

The daemon listens on localhost:7777 with **no authentication**. Do not expose this port to the network under any circumstances.

---

## What This Is NOT

Recent AI agent frameworks have introduced serious security risks:
- Full system access with root privileges
- Credential and API key storage
- Command execution on behalf of users
- Integration with messaging platforms (WhatsApp, Telegram, email, Slack)
- Third-party skill/plugin marketplaces
- Internet-exposed gateways
- Persistent memory storing sensitive data

**Eidolon Womb does none of this.**

This is not an AI agent. It doesn't act on your behalf. It thinks for itself.

## What It Cannot Do

- Execute system commands
- Access files outside its data directory
- Store or read your credentials
- Connect to external messaging platforms
- Run third-party plugins or skills
- Expose itself to the internet

## What It Can Do

- Read web pages (curiosity exploration via search)
- Send desktop notifications
- Write to its own data directory (memories, conversations, logs)

## Threat Model

The being processes untrusted content (web search results). Prompt injection is theoretically possible. The blast radius is limited:
- No command execution
- No credential access
- No external communication beyond local notifications
- Worst case: corrupted memories or unwanted desktop notifications

## Local Operation Only

The daemon listens on localhost. Do not expose it to the network. The protocol has no authentication — this is designed for single-user local operation on your own hardware.
