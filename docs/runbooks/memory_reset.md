# Runbook: Resetting the Aries Memory Palace

Instructions for a clean database reset during testing.

## Redis Reset
To clear all sensory and short-term memory:
```bash
redis-cli flushall
```

## MongoDB Reset
To clear episodic memory and user profiles:
```bash
echo "db.dropDatabase()" | mongosh dsa_agent
```

## ChromaDB Reset
To clear all semantic embeddings:
```bash
rm -rf backend/chroma_db/
```

## Full Reset Workflow
1. Stop the backend server.
2. Run the commands above.
3. Restart the backend server.
4. Rerun `backend/tests/verify_langchain_migration.py`.
