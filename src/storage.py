from __future__ import annotations

import hashlib
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Dict, List


@dataclass
class SQLiteStorage:
    db_path: Path

    def __post_init__(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.execute("PRAGMA foreign_keys=ON;")
        # Migração: renomear/copiar tabelas para nomes em pt-BR
        self._migrate_table_names()
        # Garante o schema com novos nomes
        self._create_schema()

    def _create_schema(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS artigos (
                url TEXT PRIMARY KEY,
                title TEXT,
                body TEXT,
                date TEXT,
                matched_names TEXT,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS pessoas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                name_norm TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS artigos_pessoas (
                article_url TEXT NOT NULL,
                person_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(article_url, person_id),
                FOREIGN KEY(article_url) REFERENCES artigos(url) ON DELETE CASCADE,
                FOREIGN KEY(person_id) REFERENCES pessoas(id) ON DELETE CASCADE
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS comentarios (
                comment_key TEXT PRIMARY KEY,
                article_url TEXT NOT NULL,
                comment_id TEXT,
                author TEXT,
                time_text TEXT,
                time_iso TEXT,
                content TEXT,
                permalink TEXT,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(article_url) REFERENCES artigos(url) ON DELETE CASCADE
            );
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_comentarios_artigo ON comentarios(article_url);")
        self.conn.commit()

    # ----------------
    # People helpers
    # ----------------
    @staticmethod
    def _norm(text: str) -> str:
        if not text:
            return ""
        t = unicodedata.normalize("NFKD", text)
        t = "".join(ch for ch in t if not unicodedata.combining(ch))
        return " ".join(t.lower().split())

    def upsert_person(self, name: str) -> int:
        name = (name or "").strip()
        if not name:
            return 0
        nn = self._norm(name)
        self.conn.execute(
            """
            INSERT INTO pessoas (name, name_norm)
            VALUES (:name, :name_norm)
            ON CONFLICT(name_norm) DO UPDATE SET
                name=excluded.name,
                updated_at=CURRENT_TIMESTAMP;
            """,
            {"name": name, "name_norm": nn},
        )
        cur = self.conn.execute("SELECT id FROM pessoas WHERE name_norm = ?", (nn,))
        row = cur.fetchone()
        return int(row[0]) if row else 0

    def ensure_people(self, names: Iterable[str]) -> List[int]:
        ids: List[int] = []
        for n in names:
            pid = self.upsert_person(n)
            if pid:
                ids.append(pid)
        return ids

    def link_article_people(self, article_url: str, names: Iterable[str]):
        ids = self.ensure_people(names)
        if not ids:
            return
        payload = [(article_url, pid) for pid in ids]
        self.conn.executemany(
            """
            INSERT OR IGNORE INTO artigos_pessoas (article_url, person_id)
            VALUES (?, ?);
            """,
            payload,
        )
        self.conn.commit()

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass

    # ---------------
    # Upserts
    # ---------------
    def upsert_article(self, item: Dict):
        self.conn.execute(
            """
            INSERT INTO artigos (url, title, body, date, matched_names)
            VALUES (:url, :title, :body, :date, :matched_names)
            ON CONFLICT(url) DO UPDATE SET
                title=excluded.title,
                body=excluded.body,
                date=excluded.date,
                matched_names=excluded.matched_names,
                updated_at=CURRENT_TIMESTAMP;
            """,
            {
                "url": item.get("url"),
                "title": item.get("title"),
                "body": item.get("body"),
                "date": item.get("date"),
                "matched_names": item.get("matched_names"),
            },
        )
        self.conn.commit()

    def _comment_key(self, row: Dict) -> str:
        cid = row.get("comment_id") or ""
        if cid:
            return cid
        pl = row.get("permalink") or ""
        if pl:
            return pl
        # Fallback: hash de article_url + conteúdo
        h = hashlib.sha1()
        h.update(((row.get("article_url") or "") + "\n" + (row.get("content") or "")).encode("utf-8"))
        return h.hexdigest()

    def upsert_comments(self, rows: Iterable[Dict]):
        rows = list(rows)
        if not rows:
            return
        payload = []
        for r in rows:
            payload.append(
                {
                    "comment_key": self._comment_key(r),
                    "article_url": r.get("article_url"),
                    "comment_id": r.get("comment_id"),
                    "author": r.get("author"),
                    "time_text": r.get("time_text"),
                    "time_iso": r.get("time_iso"),
                    "content": r.get("content"),
                    "permalink": r.get("permalink"),
                }
            )

        self.conn.executemany(
            """
            INSERT INTO comentarios (
                comment_key, article_url, comment_id, author, time_text, time_iso, content, permalink
            ) VALUES (
                :comment_key, :article_url, :comment_id, :author, :time_text, :time_iso, :content, :permalink
            )
            ON CONFLICT(comment_key) DO UPDATE SET
                article_url=excluded.article_url,
                comment_id=excluded.comment_id,
                author=excluded.author,
                time_text=excluded.time_text,
                time_iso=excluded.time_iso,
                content=excluded.content,
                permalink=excluded.permalink,
                updated_at=CURRENT_TIMESTAMP;
            """,
            payload,
        )
        self.conn.commit()

    # ---------------
    # Migração de nomes das tabelas (EN -> PT-BR)
    # ---------------
    def _migrate_table_names(self) -> None:
        cur = self.conn.cursor()

        def table_exists(name: str) -> bool:
            r = cur.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
            ).fetchone()
            return r is not None

        old_new = [
            ("people", "pessoas"),
            ("articles", "artigos"),
            ("comments", "comentarios"),
            ("article_people", "artigos_pessoas"),
        ]

        # Garante as novas tabelas antes de copiar (idempotente)
        self._create_schema()

        # Copia dados na ordem para respeitar FKs
        try:
            self.conn.execute("BEGIN")

            if table_exists("people"):
                self.conn.execute(
                    "INSERT OR IGNORE INTO pessoas (id, name, name_norm, created_at, updated_at) "
                    "SELECT id, name, name_norm, created_at, updated_at FROM people"
                )

            if table_exists("articles"):
                self.conn.execute(
                    "INSERT OR IGNORE INTO artigos (url, title, body, date, matched_names, scraped_at, updated_at) "
                    "SELECT url, title, body, date, matched_names, scraped_at, updated_at FROM articles"
                )

            if table_exists("comments"):
                self.conn.execute(
                    "INSERT OR IGNORE INTO comentarios (comment_key, article_url, comment_id, author, time_text, time_iso, content, permalink, scraped_at, updated_at) "
                    "SELECT comment_key, article_url, comment_id, author, time_text, time_iso, content, permalink, scraped_at, updated_at FROM comments"
                )

            if table_exists("article_people"):
                self.conn.execute(
                    "INSERT OR IGNORE INTO artigos_pessoas (article_url, person_id, created_at) "
                    "SELECT article_url, person_id, created_at FROM article_people"
                )

            # Substitui índice
            self.conn.execute("DROP INDEX IF EXISTS idx_comments_article;")
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_comentarios_artigo ON comentarios(article_url);"
            )

            # Remove tabelas antigas em ordem segura
            self.conn.execute("DROP TABLE IF EXISTS article_people;")
            self.conn.execute("DROP TABLE IF EXISTS comments;")
            self.conn.execute("DROP TABLE IF EXISTS articles;")
            self.conn.execute("DROP TABLE IF EXISTS people;")

            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise