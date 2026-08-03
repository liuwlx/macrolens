# Database migrations

The executable migration lives in `backend/alembic/versions/0001_initial.py` and creates the PostgreSQL schemas from SQLAlchemy metadata, plus PostgreSQL extensions, the latest-observation view, and the pgvector HNSW index.

`reference_schema_v1.sql` is the earlier reviewed logical schema and remains as a design reference. The Alembic migration is the source of truth for deployment.
