# Aries Database Schema Design

This document defines the structure of our three-tier memory system. This schema is designed for maximum speed (Redis), intelligence (ChromaDB), and persistence (MongoDB).

---

## 1. 🔥 Redis: Sensory & Short-Term Memory
Role: *Live state management and conversation buffering.*

### Key: `session:state:{session_id}`
| Field | Type | Description |
| :--- | :--- | :--- |
| `current_code` | `string` | The full content of the user's editor. |
| `current_problem` | `JSON` | `{ slug, title, difficulty, language }` |
| `active_view` | `string` | 'home', 'problems', 'solve' |
| `is_listening` | `bool` | VAD state tracking. |

### Key: `session:history:{session_id}`
Stored using LangChain's `RedisChatMessageHistory`.
*   **Structure**: List of serialized `BaseMessage` objects (`HumanMessage`, `AIMessage`).

---

## 2. ⚡ ChromaDB: Semantic Memory (The Memory Palace)
Role: *Vector search for technical concepts and personalized user facts.*

### Collection: `memory_palace`
| Field | Type | Description |
| :--- | :--- | :--- |
| **Document** | `text` | The raw fact (e.g., "Shridhar prefers Python for Graph problems"). |
| **Embedding** | `vector(768)`| Nomic-embed-text vector representation. |
| **Metadata** | `JSON` | See below. |

**Metadata Structure:**
```json
{
  "username": "Shridhar",
  "category": "user_preference" | "technical_gap" | "problem_summary",
  "source_session": "session_id",
  "importance": 1-5,
  "timestamp": "2024-03-15T..."
}
```

---

## 3. 🧊 MongoDB: Episodic Memory
Role: *Permanent archival of every conversation turn and system event.*

### Collection: `episodes`
```json
{
  "_id": "ObjectId",
  "session_id": "string",
  "username": "string",
  "interactions": [
    {
      "role": "user" | "aries",
      "content": "string",
      "timestamp": "ISODate",
      "actions": [
        { "tool": "RUN_CODE", "result": "..." }
      ]
    }
  ],
  "final_code_snapshot": "string",
  "summary": "string"
}
```

---

## 🔄 Data Movement Flow
1.  **Incoming Audio**: Transcript added to **Redis** history.
2.  **Aries Decision**: If he learns something new, he writes to **ChromaDB**.
3.  **Session End**: The entire **Redis** history and code state are flushed to **MongoDB** as a permanent "Episode."
