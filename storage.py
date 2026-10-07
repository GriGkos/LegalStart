"""Persistent questionnaire state; SQLite locally, PostgreSQL in the cloud."""
from __future__ import annotations

import asyncio
import json
import ssl
import uuid
from pathlib import Path

from sqlalchemy import (BigInteger, Boolean, Column, Integer, MetaData, String,
                        Table, Text, delete, insert, select, text, update)
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

metadata = MetaData()


def postgres_ssl_context(host: str | None) -> ssl.SSLContext:
    context = ssl.create_default_context()
    hostname = (host or "").lower().rstrip(".")
    if (hostname.endswith(".pooler.supabase.com") or
            (hostname.startswith("db.") and hostname.endswith(".supabase.co"))):
        # Supabase's PostgreSQL endpoints use a private CA, absent from system
        # trust stores. Add the published root while keeping hostname checks.
        certificate = Path(__file__).resolve().parent / "certs" / "supabase-prod-ca-2021.crt"
        context.load_verify_locations(cafile=str(certificate))
    return context


drafts = Table(
    "legalstart_drafts", metadata,
    Column("platform", String(80), primary_key=True),
    Column("user_id", BigInteger, primary_key=True),
    Column("session_id", String(32), nullable=False),
    Column("step", Integer, nullable=False),
    Column("editing", Boolean, nullable=False),
    Column("answers", Text, nullable=False),
    Column("username", String(128), nullable=False),
    Column("full_name", String(256), nullable=False),
)
applications = Table(
    "legalstart_applications", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("platform", String(80), nullable=False),
    Column("user_id", BigInteger, nullable=False),
    Column("session_id", String(32), nullable=False, unique=True),
    Column("username", String(128), nullable=False),
    Column("full_name", String(256), nullable=False),
    Column("answers", Text, nullable=False),
    Column("status", String(16), nullable=False),
    Column("admin_notified", Boolean, nullable=False),
)
events = Table(
    "legalstart_events", metadata,
    Column("event_key", String(120), primary_key=True),
    Column("result", Text, nullable=False),
)


class Store:
    def __init__(self, database_url: str = "", db_path: str = "data/applications.db",
                 namespace: str = "telegram"):
        self.namespace = namespace
        self.lock = asyncio.Lock()
        connect_args = {}
        if not database_url:
            path = Path(db_path).resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            database_url = "sqlite+aiosqlite:///" + path.as_posix()
        database_url = database_url.replace("postgres://", "postgresql://", 1)
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        url = make_url(database_url)
        if url.drivername == "postgresql+asyncpg":
            # Use Supabase's session pooler (5432), not its transaction pooler.
            sslmode = url.query.get("sslmode", "require")
            url = url.difference_update_query(["sslmode"])
            if sslmode != "disable":
                connect_args["ssl"] = postgres_ssl_context(url.host)
        elif url.drivername != "sqlite+aiosqlite":
            raise ValueError("DATABASE_URL должен быть PostgreSQL или SQLite+aiosqlite")
        self.engine = create_async_engine(url, pool_pre_ping=True, hide_parameters=True,
                                          connect_args=connect_args)

    async def initialize(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
            if self.engine.dialect.name == "postgresql":
                # Supabase's public REST API must not expose questionnaire data.
                # The server connects with the database owner, which bypasses RLS.
                for table in (drafts, applications, events):
                    await conn.execute(text(f"ALTER TABLE {table.name} ENABLE ROW LEVEL SECURITY"))

    async def close(self):
        await self.engine.dispose()

    def _user(self, user_id):
        return (drafts.c.platform == self.namespace) & (drafts.c.user_id == user_id)

    @staticmethod
    def _draft(row):
        return {"session_id": row["session_id"], "step": row["step"],
                "editing": row["editing"], "answers": json.loads(row["answers"])}

    async def get_draft(self, user_id):
        async with self.engine.connect() as conn:
            row = (await conn.execute(select(drafts).where(self._user(user_id)))).mappings().first()
            return self._draft(row) if row else None

    async def _mutate(self, event_key, user_id, operation):
        # One running process per bot. Mutations and event receipts commit together:
        # retries cannot advance two questions or submit the same form twice.
        async with self.lock, self.engine.begin() as conn:
            cached = (await conn.execute(select(events.c.result).where(
                events.c.event_key == event_key))).scalar_one_or_none()
            if cached is not None:
                result = json.loads(cached)
                if result["state"] == "draft":
                    row = (await conn.execute(select(drafts).where(self._user(user_id)))).mappings().first()
                    if row and row["session_id"] == result["session_id"]:
                        return {"state": "draft", "draft": self._draft(row)}
                    return {"state": "stale"}
                return result
            result = await operation(conn)
            # Receipts contain no answers or names, including after cancellation.
            receipt = ({"state": "draft", "session_id": result["draft"]["session_id"]}
                       if result["state"] == "draft" else result)
            await conn.execute(insert(events).values(
                event_key=event_key, result=json.dumps(receipt, ensure_ascii=False)))
            return result

    async def begin(self, user_id, username, full_name, event_key):
        async def operation(conn):
            row = (await conn.execute(select(drafts).where(self._user(user_id)))).mappings().first()
            if row:
                return {"state": "draft", "draft": self._draft(row)}
            values = dict(platform=self.namespace, user_id=user_id,
                          session_id=uuid.uuid4().hex, step=0, editing=False,
                          answers=json.dumps(["", "", "", ""]),
                          username=username or "", full_name=full_name)
            await conn.execute(insert(drafts).values(**values))
            return {"state": "draft", "draft": self._draft(values)}
        return await self._mutate(event_key, user_id, operation)

    async def answer(self, user_id, text, event_key):
        async def operation(conn):
            row = (await conn.execute(select(drafts).where(self._user(user_id)))).mappings().first()
            if not row:
                return {"state": "missing"}
            data = self._draft(row)
            if data["step"] < 4:
                data["answers"][data["step"]] = text
                data["step"] = 4 if data["editing"] else data["step"] + 1
                data["editing"] = False
                await conn.execute(update(drafts).where(self._user(user_id)).values(
                    step=data["step"], editing=False,
                    answers=json.dumps(data["answers"], ensure_ascii=False)))
            return {"state": "draft", "draft": data}
        return await self._mutate(event_key, user_id, operation)

    async def action(self, user_id, session_id, action, event_key, field=None):
        async def operation(conn):
            row = (await conn.execute(select(drafts).where(self._user(user_id)))).mappings().first()
            if not row or (session_id is not None and row["session_id"] != session_id):
                return {"state": "stale"}
            data = self._draft(row)
            if action == "cancel":
                await conn.execute(delete(drafts).where(self._user(user_id)))
                return {"state": "canceled"}
            if action == "edit" and data["step"] == 4 and field in range(4):
                data.update(step=field, editing=True)
                await conn.execute(update(drafts).where(self._user(user_id)).values(
                    step=field, editing=True))
                return {"state": "draft", "draft": data}
            if action == "confirm" and data["step"] == 4:
                result = await conn.execute(insert(applications).values(
                    platform=self.namespace, user_id=user_id, session_id=session_id,
                    username=row["username"], full_name=row["full_name"],
                    answers=row["answers"], status="new", admin_notified=False))
                application_id = result.inserted_primary_key[0]
                await conn.execute(delete(drafts).where(self._user(user_id)))
                return {"state": "submitted", "id": application_id}
            return {"state": "draft", "draft": data}
        return await self._mutate(event_key, user_id, operation)

    async def pending_notifications(self):
        async with self.engine.connect() as conn:
            rows = (await conn.execute(select(applications).where(
                (applications.c.platform == self.namespace) &
                (applications.c.admin_notified.is_(False))).order_by(applications.c.id).limit(20))).mappings()
            return [dict(row, answers=json.loads(row["answers"])) for row in rows]

    async def mark_notified(self, application_id):
        async with self.engine.begin() as conn:
            await conn.execute(update(applications).where(
                (applications.c.id == application_id) &
                (applications.c.platform == self.namespace)).values(admin_notified=True))
