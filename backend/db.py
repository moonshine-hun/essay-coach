import os
import aiosqlite

DB_PATH = os.path.join(os.path.dirname(__file__), "essay.db")

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS essay_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_title TEXT NOT NULL,
    news_summary TEXT NOT NULL DEFAULT '',
    news_source TEXT NOT NULL DEFAULT '',
    news_url TEXT NOT NULL DEFAULT '',
    question TEXT NOT NULL DEFAULT '',
    char_limit INTEGER NOT NULL DEFAULT 800,
    time_limit_min INTEGER NOT NULL DEFAULT 40,
    user_answer TEXT NOT NULL DEFAULT '',
    feedback TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    submitted_at TEXT
);
CREATE TABLE IF NOT EXISTS ai_call_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    called_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
"""


async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(_CREATE_SQL)
        await db.commit()
