"""SQLite belongs only to IAM. No access to R2 or Slice Manager tables."""
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager, closing

from fastapi import HTTPException

SCHEMA = """
CREATE TABLE users (
 id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, display_name TEXT NOT NULL,
 password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','professor','student')),
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
);
CREATE TABLE sessions (
 jti TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), expires INTEGER NOT NULL
);
CREATE TABLE courses (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, professor_can_modify INTEGER NOT NULL
);
CREATE TABLE memberships (
 course_id TEXT NOT NULL REFERENCES courses(id), user_id TEXT NOT NULL REFERENCES users(id),
 quotas TEXT NOT NULL, PRIMARY KEY(course_id,user_id)
);
CREATE TABLE resources (
 id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('slice','vm')),
 course_id TEXT NOT NULL REFERENCES courses(id), professor_id TEXT NOT NULL REFERENCES users(id),
 parent_slice_id TEXT REFERENCES resources(id)
);
CREATE TABLE assignments (
 resource_id TEXT NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
 user_id TEXT NOT NULL REFERENCES users(id), PRIMARY KEY(resource_id,user_id)
);
CREATE TABLE login_attempts (subject TEXT NOT NULL, at INTEGER NOT NULL);
CREATE INDEX login_attempts_subject ON login_attempts(subject,at);
CREATE TABLE audit (
 id INTEGER PRIMARY KEY AUTOINCREMENT, at INTEGER NOT NULL,
 actor_id TEXT, action TEXT NOT NULL, resource_id TEXT, outcome TEXT NOT NULL
);
PRAGMA user_version=1;
"""


def audit(db, actor, action, resource, outcome):
    db.execute("INSERT INTO audit(at,actor_id,action,resource_id,outcome) VALUES(?,?,?,?,?)",
               (int(time.time()), actor, action, resource, outcome))


def require_row(db, table, identity):
    # Table names are exclusively hardcoded by the application, never request input.
    row = db.execute(f"SELECT * FROM {table} WHERE id=?", (identity,)).fetchone()
    if row is None:
        raise HTTPException(404, "not_found")
    return row


def public_user(row):
    return {**{k: row[k] for k in ("id", "username", "display_name", "role")},
            "active": bool(row["active"])}


class Store:
    def __init__(self, path):
        self.path = path

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=10, check_same_thread=False)) as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version == 0:
                db.executescript("BEGIN IMMEDIATE;\n" + SCHEMA + "\nCOMMIT;")
            elif version != 1:
                raise RuntimeError("Unsupported IAM database schema")

    def check_schema(self):
        if not self.path.is_file():
            raise RuntimeError("Initialize IAM with python -m g5_iam.cli init")
        with self.transaction() as db:
            if db.execute("PRAGMA user_version").fetchone()[0] != 1:
                raise RuntimeError("Unsupported IAM database schema")

    def bootstrap(self, user, password_hash):
        with self.transaction() as db:
            if db.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
                raise ValueError("IAM already initialized: bootstrap does not reset existing accounts")
            identity = str(uuid.uuid4())
            db.execute("INSERT INTO users(id,username,display_name,password_hash,role) VALUES(?,?,?,?,?)",
                       (identity, user.username, user.display_name, password_hash, "admin"))
            audit(db, identity, "bootstrap", identity, "allowed")

    def record(self, actor, action, resource, outcome):
        with self.transaction() as db:
            audit(db, actor, action, resource, outcome)
