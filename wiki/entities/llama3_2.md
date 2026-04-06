# llama3.2:3b

Default language model for the being's cognition.

## Role in Eidolon Womb

The 3B parameter Llama 3.2 model serves as the being's "vocal cords" -- providing language generation capability while the womb infrastructure provides the cognitive architecture. (Source: `docs/FAQ.md:19`)

## Configuration

- Model name: `llama3.2:3b` (configurable in `core/config.py:2`)
- Context window: 16,384 tokens (Source: `core/config.py:4`)
- Temperature: 0.7 default, varies by function (Source: `core/config.py:11`)

## Design Constraints

The binary intent system, action tag syntax, inner voice checks, and idle response cap (100 tokens) all exist specifically because 3B models have limitations:
- Cannot reliably produce structured output (JSON, function calls)
- Confabulate in longer outputs
- Hallucinate sensory experiences
- Slip into assistant mode
- Fall into abstract philosophy loops

(Source: `brain/intent.py:1-6`, `docs/ARCHITECTURE.md:76-78`)

## Hardware Requirements

Tested on Jetson Orin Nano 8GB and RTX 4060. Needs ~4GB memory. (Source: `README.md:83-84`)

## Alternatives

"Other sizes untested." The binary intent system is model-agnostic. (Source: `README.md:84`, `docs/ARCHITECTURE.md:227`)
