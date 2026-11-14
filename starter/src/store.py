"""Persistent vector storage and cosine search using PostgreSQL + pgvector."""
import json
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from .models import Chunk


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        if not database_url:
            raise ValueError("DATABASE_URL is required")
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self.database_url = database_url
        self.dimensions = dimensions

    def create_schema(self) -> None:
        with psycopg.connect(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS day6_chunks (
                        strategy text NOT NULL,
                        chunk_id text NOT NULL,
                        document_id text NOT NULL,
                        source text NOT NULL,
                        page integer NOT NULL,
                        chunk_text text NOT NULL,
                        metadata jsonb NOT NULL,
                        embedding vector NOT NULL,
                        PRIMARY KEY (strategy, chunk_id)
                    )
                    """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS day6_chunks_strategy_idx "
                    "ON day6_chunks (strategy)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS day6_chunks_metadata_idx "
                    "ON day6_chunks USING gin (metadata)"
                )

    def version_info(self) -> dict[str, str]:
        with psycopg.connect(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT current_setting('server_version'),
                           (SELECT extversion FROM pg_extension WHERE extname = 'vector')
                    """
                )
                row = cursor.fetchone()
        if not row or not row[1]:
            raise RuntimeError("PostgreSQL is connected but pgvector is not installed")
        return {"postgresql": row[0], "pgvector": row[1]}

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have equal lengths")
        if any(len(vector) != self.dimensions for vector in vectors):
            raise ValueError("embedding dimension does not match configured model")
        if not strategy:
            raise ValueError("strategy must not be empty")

        with psycopg.connect(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM day6_chunks WHERE strategy = %s", (strategy,))
                cursor.executemany(
                    """
                    INSERT INTO day6_chunks
                        (strategy, chunk_id, document_id, source, page, chunk_text, metadata, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)
                    """,
                    [
                        (
                            strategy,
                            chunk.chunk_id,
                            chunk.document_id,
                            chunk.source,
                            chunk.page,
                            chunk.text,
                            Jsonb(chunk.metadata),
                            self._vector_literal(vector),
                        )
                        for chunk, vector in zip(chunks, vectors)
                    ],
                )

    def search(
        self,
        strategy: str,
        query_vector: list[float],
        top_k: int = 3,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if len(query_vector) != self.dimensions:
            raise ValueError("query vector dimension does not match configured model")
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        if filters and set(filters) - {"section"}:
            raise ValueError(f"Unsupported metadata filter fields: {sorted(set(filters) - {'section'})}")

        where_filter = ""
        parameters: list[Any] = [strategy, self._vector_literal(query_vector)]
        if filters:
            where_filter = "AND metadata @> %s::jsonb"
            parameters.append(json.dumps(filters, ensure_ascii=False))
        parameters.append(top_k)

        query = f"""
            SELECT chunk_id, chunk_text, source, document_id, page, metadata,
                   1 - (embedding <=> %s::vector) AS score
            FROM day6_chunks
            WHERE strategy = %s {where_filter}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        # The query vector occurs in both the score and ordering expressions.
        ordered_parameters = [parameters[1], parameters[0]]
        if filters:
            ordered_parameters.append(parameters[2])
        ordered_parameters.extend([parameters[1], parameters[-1]])

        with psycopg.connect(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, ordered_parameters)
                rows = cursor.fetchall()
        return [
            {
                "chunk_id": row[0],
                "text": row[1],
                "source": row[2],
                "document_id": row[3],
                "page": row[4],
                "metadata": row[5],
                "score": float(row[6]),
            }
            for row in rows
        ]

    @staticmethod
    def _vector_literal(vector: list[float]) -> str:
        return "[" + ",".join(format(float(value), ".9g") for value in vector) + "]"
