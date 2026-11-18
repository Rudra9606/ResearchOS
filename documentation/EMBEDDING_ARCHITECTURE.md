# Embedding architecture

ResearchOS uses the configurable Sentence Transformers model
`all-MiniLM-L6-v2`. The installed model reports an output dimension of **384**;
the application validates every generated vector against `EMBEDDING_DIMENSION`
and the database column is `vector(384)`.

`EmbeddingService` lazily loads one model per process, supports batch and query
embedding, accepts an optional device (`cpu`, `cuda`, or another supported
Torch
device), and raises an explicit `EmbeddingError` for load, generation, or
dimension failures. Document re-indexing generates all vectors before replacing
the existing chunk set.

The migration
`4a8f3c1d2e90_fix_embedding_dimension_and_index` changes the unconstrained
column to `vector(384)`. Existing vectors with the correct dimension are
preserved; invalid-dimension vectors are set to `NULL`. It also creates an
IVFFlat cosine index. Apply it only after confirming the deployed database
contains the expected pgvector extension and model dimension:

```powershell
cd D:\ResearchOS\ResearchOS\backend
alembic upgrade head
```

Configuration:

```env
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
EMBEDDING_DEVICE=
```

No fake vectors are used in production. Tests inject small fake models only to
verify batching and validation behavior.
