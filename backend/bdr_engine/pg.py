"""PostgreSQL helpers: fixed, allowlisted pg_dump/pg_restore invocations (no user-supplied arguments)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import psycopg
from psycopg import sql

from .config import DbTarget


class PgError(RuntimeError):
    pass


def _run(args: list[str], target: DbTarget, timeout: int) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **target.libpq_env()}
    try:
        result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as e:
        raise PgError(f"{args[0]} timed out after {timeout} s") from e
    except FileNotFoundError as e:
        raise PgError(f"{args[0]} is not installed") from e
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip().splitlines()
        raise PgError(f"{args[0]} failed: {message[-1] if message else f'exit code {result.returncode}'}"[:500])
    return result


def tool_version(tool: str) -> str:
    try:
        out = subprocess.run([tool, "--version"], capture_output=True, text=True, timeout=10, check=True).stdout
    except (OSError, subprocess.SubprocessError) as e:
        raise PgError(f"{tool} is not available") from e
    return out.strip().split()[-1]


def dump(target: DbTarget, *, snapshot: str, out_file: Path, timeout: int) -> None:
    _run(
        ["pg_dump", "--format=custom", f"--snapshot={snapshot}", f"--file={out_file}", f"--dbname={target.dbname}"],
        target,
        timeout,
    )


def list_archive(archive: Path, target: DbTarget, timeout: int) -> int:
    """Reads the archive's table of contents. Fails on truncated or non-pg_dump files."""
    result = _run(["pg_restore", "--list", str(archive)], target, timeout)
    return sum(1 for line in result.stdout.splitlines() if line and not line.startswith(";"))


def restore(archive: Path, target: DbTarget, dbname: str, timeout: int) -> None:
    _run(
        [
            "pg_restore",
            "--exit-on-error",
            "--single-transaction",
            "--no-owner",
            "--no-privileges",
            f"--dbname={dbname}",
            str(archive),
        ],
        target,
        timeout,
    )


def snapshot_facts(cur: psycopg.Cursor, tables: tuple[str, ...]) -> tuple[str | None, dict[str, int]]:
    """Schema revision and row counts as seen by the cursor's transaction."""
    cur.execute("SELECT to_regclass('public.alembic_version') IS NOT NULL")
    row = cur.fetchone()
    revision = None
    if row and row[0]:
        cur.execute("SELECT version_num FROM alembic_version")
        found = cur.fetchone()
        revision = found[0] if found else None
    counts: dict[str, int] = {}
    for table in tables:
        cur.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table)))
        counts[table] = cur.fetchone()[0]  # type: ignore[index]
    return revision, counts


def create_database(target: DbTarget, name: str) -> None:
    with psycopg.connect(**target.conninfo(), autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))


def drop_database(target: DbTarget, name: str) -> None:
    with psycopg.connect(**target.conninfo(), autocommit=True) as conn:
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))
