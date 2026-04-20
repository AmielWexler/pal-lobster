# Ontology Definitions — Pal Lobster

All object types and link types live in the **APBG-Dev Ontology** under namespace `vahej4tu`.

- **Ontology RID:** `ri.ontology.main.ontology.a4c72975-6b1e-4c42-88b0-523b9870ad84`
- **Namespace:** `vahej4tu`
- **Merge proposal:** `ri.branch..proposal.a931a2f1-c821-45a2-9bef-db6c6f9e460e`
  - URL: `https://accenture.palantirfoundry.com/workspace/developer-branching/proposal/ri.branch..proposal.a931a2f1-c821-45a2-9bef-db6c6f9e460e`
  - **Must be approved in Foundry UI** before object types appear in Ontology Viewer

---

## Object Types

### `vahej4tu.lobster-conversation`

Chat session between a user and OpenClaw.

**Backing dataset:** `ri.foundry.main.dataset.a41cdaa5-a6e0-4314-bc75-a533042a7d2f`

| Property | Type | Notes |
|---|---|---|
| `conversationId` | String | Primary key |
| `title` | String | First 80 chars of first user message |
| `createdAt` | Timestamp | ISO-8601 UTC |

---

### `vahej4tu.lobster-message`

Individual message turn within a conversation.

**Backing dataset:** `ri.foundry.main.dataset.c8ef81bd-515f-4eff-9796-9806b173f08a`

| Property | Type | Notes |
|---|---|---|
| `messageId` | String | Primary key (UUID) |
| `conversationId` | String | Foreign key → lobster-conversation |
| `role` | String | `"user"` or `"assistant"` |
| `content` | String | Full message text |
| `createdAt` | Timestamp | ISO-8601 UTC |

---

### `vahej4tu.lobster-agent-state`

Agent configuration and runtime state.

**Backing dataset:** `ri.foundry.main.dataset.17f1b457-d2af-4e6e-90b7-77fbdc3e39df`

| Property | Type | Notes |
|---|---|---|
| `agentId` | String | Primary key |
| `name` | String | Display name |
| `status` | String | e.g. `"idle"`, `"running"` |
| `config` | String | JSON blob of agent config |
| `updatedAt` | Timestamp | ISO-8601 UTC |

---

### `vahej4tu.lobster-skill`

Tool or skill definition available to agents.

**Backing dataset:** `ri.foundry.main.dataset.6c78316f-5745-4d3e-a850-4937ec107945`

| Property | Type | Notes |
|---|---|---|
| `skillId` | String | Primary key |
| `name` | String | Display name |
| `description` | String | Used by the model as tool description |
| `schema` | String | JSON Schema of tool parameters |

---

### `vahej4tu.lobster-memory-chunk`

Long-term memory fragment for semantic recall.

**Backing dataset:** `ri.foundry.main.dataset.c160bcbc-f553-479d-8887-be998c52f7d7`

| Property | Type | Notes |
|---|---|---|
| `chunkId` | String | Primary key |
| `agentId` | String | Foreign key → lobster-agent-state |
| `content` | String | Memory text — **enable semantic search** in Ontology Manager |
| `importance` | Double | 0.0–1.0 score |
| `createdAt` | Timestamp | ISO-8601 UTC |

> Enable **Semantic Search** on the `content` property in Ontology Manager to support vector similarity recall.

---

## Link Types

### `vahej4tu.lobster-conversation-messages`

Conversation → Messages (1:many)

- **RID:** `ri.ontology.main.relation.73f0f7c0-f37e-4443-a038-ddb172662978`
- Side A: `vahej4tu.lobster-conversation` (ONE)
- Side B: `vahej4tu.lobster-message` (MANY)

---

### `vahej4tu.lobster-agent-skills`

Agent ↔ Skills (many:many)

- **RID:** `ri.ontology.main.relation.a25fcc5b-3ae4-...` *(truncated — see foundry-objects.json)*
- Junction dataset: `ri.foundry.main.dataset.287d8b03-680a-453b-9f62-aea104af6473`

---

### `vahej4tu.lobster-agent-memory`

Agent → Memory Chunks (1:many)

- **RID:** `ri.ontology.main.relation.0af7576d-cf3...` *(truncated — see foundry-objects.json)*
- Side A: `vahej4tu.lobster-agent-state` (ONE)
- Side B: `vahej4tu.lobster-memory-chunk` (MANY)

---

## How Writes Work

`backend/app/services/ontology.py` writes rows via the **Foundry Dataset Transaction API**:

1. `POST /api/v1/datasets/{rid}/transactions` — opens an APPEND transaction
2. `PUT .../files/upload?filePath=<uuid>.jsonl` — uploads a single JSONL row
3. `POST .../transactions/{txn}/commit` — commits

Foundry's incremental build pipeline picks up the new files and updates the ontology objects. **If objects don't appear in Ontology Viewer:**
1. Confirm the merge proposal above has been approved.
2. Navigate to each backing dataset in Foundry and trigger a **Build** manually (or configure a scheduled build).

The token used for writes comes from `context.auth_token` (the invoking user's OAuth token), not `MODULE_AUTH_TOKEN`.

---

## Verifying Registration

After the merge proposal is approved:

1. Open **Ontology Manager** in the APBG-Dev workspace.
2. Search for `lobster-` — all 5 object types should appear under namespace `vahej4tu`.
3. After a chat interaction through the CM, navigate to the `lobster-conversation` dataset and trigger a build; the new row should appear in the object type.

---

## Naming Convention

All API names are prefixed `lobster-` to avoid collision with other types in the shared `vahej4tu` namespace.

## Property Type Notes

- `Long Text` — use for `content` fields that may exceed 1 000 characters
- `Timestamp` — all date fields; stored as ISO-8601 UTC strings in JSONL, Foundry parses them
- `Double` — use for `importance` score on memory chunks
- Enable **Semantic Search** on `lobster-memory-chunk.content` for vector similarity recall (Phase 4)
