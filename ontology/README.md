# Ontology Definitions — Pal Lobster

This directory contains the schema definitions for all Foundry Ontology object types and link types used by the Pal Lobster (OpenClaw on Foundry) project.

## Setup Instructions

Register these in Foundry Ontology Manager under the **APBG-Dev / Lobster pal** project.

### Object Types

| File | API Name | Purpose |
|---|---|---|
| `object-types/conversation.json` | `lobster-conversation` | Chat session between a user and OpenClaw |
| `object-types/message.json` | `lobster-message` | Individual message within a conversation |
| `object-types/agent-state.json` | `lobster-agent-state` | Agent configuration and runtime state |
| `object-types/skill.json` | `lobster-skill` | Stored tool/skill available to agents |
| `object-types/memory-chunk.json` | `lobster-memory-chunk` | Long-term memory fragment for semantic recall |

### Link Types

| File | API Name | Relationship |
|---|---|---|
| `link-types/conversation-messages.json` | `lobster-conversation-messages` | Conversation → Messages (1:many) |
| `link-types/agent-skills.json` | `lobster-agent-skills` | Agent ↔ Skills (many:many) |
| `link-types/agent-memory.json` | `lobster-agent-memory` | Agent → Memory Chunks (1:many) |

## Property Type Notes

- `long_text` — use Foundry's **Long Text** property type for content fields that may exceed 1000 chars
- `timestamp` — use Foundry's **Timestamp** type
- `float` — use Foundry's **Double** type for importance scores
- Enable **semantic search** on `lobster-memory-chunk.content` in Ontology Manager to support vector similarity recall

## Naming Convention

All API names are prefixed with `lobster-` to avoid collision with other object types in the shared ontology.
