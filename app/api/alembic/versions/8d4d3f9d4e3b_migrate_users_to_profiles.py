"""migrate_users_to_profiles

Revision ID: 8d4d3f9d4e3b
Revises: 7f0691f95f9f
Create Date: 2026-05-07 16:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8d4d3f9d4e3b"
down_revision: Union[str, Sequence[str], None] = "7f0691f95f9f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

    op.create_table(
        "profiles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["id"], ["auth.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_profiles_email"), "profiles", ["email"], unique=False)

    op.execute(
        """
        create or replace function public.handle_auth_user_profile()
        returns trigger
        language plpgsql
        security definer
        set search_path = ''
        as $$
        begin
          insert into public.profiles (id, email, full_name)
          values (
            new.id,
            coalesce(new.email, ''),
            coalesce(new.raw_user_meta_data ->> 'full_name', split_part(coalesce(new.email, ''), '@', 1))
          )
          on conflict (id) do update
          set
            email = excluded.email,
            full_name = excluded.full_name,
            updated_at = now();

          return new;
        end;
        $$;
        """
    )
    op.execute("drop trigger if exists on_auth_user_profile_changed on auth.users;")
    op.execute(
        """
        create trigger on_auth_user_profile_changed
        after insert or update on auth.users
        for each row execute procedure public.handle_auth_user_profile();
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("drop trigger if exists on_auth_user_profile_changed on auth.users;")
    op.execute("drop function if exists public.handle_auth_user_profile();")
    op.drop_index(op.f("ix_profiles_email"), table_name="profiles")
    op.drop_table("profiles")

    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=True),
        sa.Column("github_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("github_id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
