"""Initial schema — exoplanets table.

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exoplanets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("pl_name", sa.String(), nullable=False),
        sa.Column("hostname", sa.String(), nullable=False),
        sa.Column("discovery_method", sa.String(), nullable=False),
        sa.Column("disc_year", sa.Integer(), nullable=True),
        sa.Column("orbital_period", sa.Float(), nullable=True),
        sa.Column("pl_rade", sa.Float(), nullable=True),
        sa.Column("pl_bmasse", sa.Float(), nullable=True),
        sa.Column("pl_eqt", sa.Float(), nullable=True),
        sa.Column("st_teff", sa.Float(), nullable=True),
        sa.Column("st_rad", sa.Float(), nullable=True),
        sa.Column("sy_dist", sa.Float(), nullable=True),
        sa.Column("ra", sa.Float(), nullable=True),
        sa.Column("dec", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pl_name"),
    )
    op.create_index("ix_exoplanets_pl_name", "exoplanets", ["pl_name"])
    op.create_index("ix_exoplanets_hostname", "exoplanets", ["hostname"])
    op.create_index("ix_exoplanets_discovery_method", "exoplanets", ["discovery_method"])
    op.create_index("ix_exoplanets_disc_year", "exoplanets", ["disc_year"])
    op.create_index(
        "ix_disc_method_year", "exoplanets", ["discovery_method", "disc_year"]
    )


def downgrade() -> None:
    op.drop_index("ix_disc_method_year", table_name="exoplanets")
    op.drop_index("ix_exoplanets_disc_year", table_name="exoplanets")
    op.drop_index("ix_exoplanets_discovery_method", table_name="exoplanets")
    op.drop_index("ix_exoplanets_hostname", table_name="exoplanets")
    op.drop_index("ix_exoplanets_pl_name", table_name="exoplanets")
    op.drop_table("exoplanets")
