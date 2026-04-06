"""add conversation_state_payload and awaiting_human_callback

Revision ID: 002
Revises: 001
Create Date: 2026-04-02 00:00:00.000000

Adds structured memory storage to the conversations table so the state machine
can persist ConversationMemory without depending on fragile text summaries.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Structured conversation memory (ConversationMemory serialised as JSON)
    op.add_column(
        "conversations",
        sa.Column(
            "conversation_state_payload",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )

    # Mirrors ConversationMemory.awaiting_human_callback for fast DB-level queries
    op.add_column(
        "conversations",
        sa.Column(
            "awaiting_human_callback",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )

    # Index for querying conversations that need human attention
    op.create_index(
        "ix_conversations_awaiting_human_callback",
        "conversations",
        ["tenant_id", "awaiting_human_callback"],
    )


def downgrade() -> None:
    op.drop_index("ix_conversations_awaiting_human_callback", table_name="conversations")
    op.drop_column("conversations", "awaiting_human_callback")
    op.drop_column("conversations", "conversation_state_payload")
