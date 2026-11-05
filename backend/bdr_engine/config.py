"""Engine configuration, read from environment variables. Passwords never come from the command line."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class DbTarget:
    host: str
    port: int
    user: str
    password: str
    dbname: str

    def conninfo(self, dbname: str | None = None, connect_timeout: int = 5) -> dict[str, object]:
        """Keyword arguments for ``psycopg.connect``."""
        return {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "dbname": dbname or self.dbname,
            "connect_timeout": connect_timeout,
        }

    def libpq_env(self) -> dict[str, str]:
        """Environment for pg_dump/pg_restore, so the password never appears in the process list."""
        return {
            "PGHOST": self.host,
            "PGPORT": str(self.port),
            "PGUSER": self.user,
            "PGPASSWORD": self.password,
            "PGCONNECT_TIMEOUT": "5",
        }


@dataclass(frozen=True)
class RetentionPolicy:
    keep_all_hours: int = 24
    keep_daily_days: int = 7


@dataclass(frozen=True)
class Settings:
    source: DbTarget
    verify: DbTarget
    backup_dir: Path
    tables: tuple[str, ...]
    interval_minutes: int = 60
    rpo_minutes: int = 60
    rto_minutes: int = 30
    retention: RetentionPolicy = RetentionPolicy()
    dump_timeout_seconds: int = 900
    restore_timeout_seconds: int = 900
    offsite_bucket: str | None = None
    offsite_prefix: str = "backups/"
    aws_region: str = "ap-southeast-1"
    primary_name: str = "BFC office server"
    primary_location: str = "Naga City office"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env

        def need(key: str) -> str:
            value = env.get(key, "").strip()
            if not value:
                raise ConfigError(f"{key} is not set")
            return value

        def num(key: str, default: int, minimum: int = 1) -> int:
            raw = env.get(key, "").strip()
            try:
                value = int(raw) if raw else default
            except ValueError as e:
                raise ConfigError(f"{key} must be a whole number") from e
            if value < minimum:
                raise ConfigError(f"{key} must be at least {minimum}")
            return value

        def target(prefix: str) -> DbTarget:
            return DbTarget(
                host=need(f"{prefix}_HOST"),
                port=num(f"{prefix}_PORT", 5432),
                user=need(f"{prefix}_USER"),
                password=need(f"{prefix}_PASSWORD"),
                dbname=env.get(f"{prefix}_DB", "").strip() or "postgres",
            )

        tables = tuple(t.strip() for t in env.get("BDR_TABLES", "farmers,inventory_items,transactions").split(",") if t.strip())
        if not tables:
            raise ConfigError("BDR_TABLES must name at least one table")

        return cls(
            source=target("BDR_SOURCE"),
            verify=target("BDR_VERIFY"),
            backup_dir=Path(env.get("BDR_BACKUP_DIR", "/backups")),
            tables=tables,
            interval_minutes=num("BDR_INTERVAL_MINUTES", 60),
            rpo_minutes=num("BDR_RPO_MINUTES", 60),
            rto_minutes=num("BDR_RTO_MINUTES", 30),
            retention=RetentionPolicy(
                keep_all_hours=num("BDR_KEEP_ALL_HOURS", 24),
                keep_daily_days=num("BDR_KEEP_DAILY_DAYS", 7, minimum=0),
            ),
            dump_timeout_seconds=num("BDR_DUMP_TIMEOUT_SECONDS", 900),
            restore_timeout_seconds=num("BDR_RESTORE_TIMEOUT_SECONDS", 900),
            offsite_bucket=env.get("BDR_OFFSITE_BUCKET", "").strip() or None,
            offsite_prefix=env.get("BDR_OFFSITE_PREFIX", "").strip() or "backups/",
            aws_region=env.get("AWS_REGION", "").strip() or "ap-southeast-1",
        )
