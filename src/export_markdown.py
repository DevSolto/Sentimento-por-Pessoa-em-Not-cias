from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
import re
import unicodedata
from datetime import datetime


@dataclass
class Article:
    url: str
    title: str
    date: str
    body: str
    scraped_at: str


@dataclass
class Comment:
    author: str
    time_text: str
    time_iso: str
    content: str
    scraped_at: str


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _norm(s: str) -> str:
    t = unicodedata.normalize("NFKD", s or "")
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return " ".join(t.lower().split())


PT_MONTHS: Dict[str, int] = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
    # abreviações
    "jan": 1,
    "fev": 2,
    "mar": 3,
    "abr": 4,
    "mai": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "set": 9,
    "out": 10,
    "nov": 11,
    "dez": 12,
}


def _ym_from_article_date(date_text: str) -> Optional[str]:
    if not date_text:
        return None
    s = date_text.strip()
    # 1) ISO YYYY-MM-DD
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12:
            return f"{y:04d}-{mo:02d}"
    # 2) DD/MM/YYYY
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        y, mo = int(m.group(3)), int(m.group(2))
        if 1 <= mo <= 12:
            return f"{y:04d}-{mo:02d}"
    # 3) "D de mês de YYYY"
    ns = _norm(s)
    m = re.search(r"(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})", ns)
    if m:
        y = int(m.group(3))
        mname = m.group(2)
        mo = PT_MONTHS.get(mname)
        if mo:
            return f"{y:04d}-{mo:02d}"
    # 4) "mês D, YYYY"
    m = re.search(r"([a-z]+)\s+(\d{1,2}),?\s+(\d{4})", ns)
    if m:
        y = int(m.group(3))
        mname = m.group(1)
        mo = PT_MONTHS.get(mname)
        if mo:
            return f"{y:04d}-{mo:02d}"
    # 5) ISO YYYY-MM
    m = re.search(r"(\d{4})-(\d{1,2})", s)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12:
            return f"{y:04d}-{mo:02d}"
    return None


def fetch_articles_all(cur: sqlite3.Cursor) -> List[Article]:
    cur.execute(
        """
        SELECT url, COALESCE(title,''), COALESCE(date,''),
               COALESCE(body,''), COALESCE(scraped_at,'')
        FROM artigos
        """
    )
    rows = cur.fetchall()
    return [Article(url=r[0], title=r[1], date=r[2], body=r[3], scraped_at=r[4]) for r in rows]


def fetch_people(cur: sqlite3.Cursor, article_url: str) -> List[str]:
    cur.execute(
        """
        SELECT p.name
        FROM artigos_pessoas ap
        JOIN pessoas p ON p.id = ap.person_id
        WHERE ap.article_url = ?
        ORDER BY p.name ASC
        """,
        (article_url,),
    )
    return [r[0] for r in cur.fetchall() if r and r[0]]


def fetch_comments(cur: sqlite3.Cursor, article_url: str) -> List[Comment]:
    cur.execute(
        """
        SELECT COALESCE(author,''), COALESCE(time_text,''), COALESCE(time_iso,''),
               COALESCE(content,''), COALESCE(scraped_at,'')
        FROM comentarios
        WHERE article_url = ?
        ORDER BY scraped_at ASC
        """,
        (article_url,),
    )
    rows = cur.fetchall()
    return [Comment(author=r[0], time_text=r[1], time_iso=r[2], content=r[3], scraped_at=r[4]) for r in rows]


def fmt_md_article(a: Article, names: List[str], comments: List[Comment]) -> str:
    lines: List[str] = []
    # Título
    lines.append(f"## {a.title.strip() or '(sem título)'}")
    # Data preferindo a data do site; fallback para scraped_at
    date_text = (a.date or '').strip() or a.scraped_at
    lines.append(f"Data: {date_text}")
    # Lista de citados
    lines.append("Citações:")
    if names:
        for n in names:
            lines.append(f"- {n}")
    else:
        lines.append("- (sem citações registradas)")
    # Corpo
    lines.append("")
    lines.append("Corpo:")
    body = (a.body or '').strip()
    if body:
        lines.append(body)
    else:
        lines.append("(sem corpo)")
    # Comentários
    lines.append("")
    lines.append("Comentários:")
    if comments:
        for c in comments:
            when = c.time_text.strip() or c.time_iso.strip() or c.scraped_at
            author = c.author.strip() or "Anônimo"
            # Uma linha por comentário para facilitar parsing
            content = (c.content or '').strip().replace('\n', ' ')
            lines.append(f"- {author} — {when}: {content}")
    else:
        lines.append("- (sem comentários)")
    lines.append("")
    return "\n".join(lines)


def export_month(cur: sqlite3.Cursor, ym: str, articles: List[Article], out_dir: Path) -> Path:
    out_path = out_dir / f"{ym}.md"
    with out_path.open("w", encoding="utf-8") as f:
        # Cabeçalho do arquivo
        f.write(f"# {ym}\n\n")
        for idx, a in enumerate(articles, start=1):
            names = fetch_people(cur, a.url)
            comments = fetch_comments(cur, a.url)
            block = fmt_md_article(a, names, comments)
            f.write(block)
            if idx != len(articles):
                f.write("\n\n")
    return out_path


def _normalize_ym(value: str) -> str:
    s = value.strip()
    # Accept forms: YYYY-M, YYYY-MM, YYYY/M, YYYY_M, YYYYMM
    m = re.match(r"^(\d{4})[-_/]?(\d{1,2})$", s)
    if not m:
        # Try compact YYYYMM
        m2 = re.match(r"^(\d{4})(\d{2})$", s)
        if not m2:
            return s  # fallback unchanged
        year, month = int(m2.group(1)), int(m2.group(2))
    else:
        year, month = int(m.group(1)), int(m.group(2))
    if not (1 <= month <= 12):
        return s
    return f"{year:04d}-{month:02d}"


def run(db: Path, out: Path, only_months: Optional[Iterable[str]] = None) -> List[Path]:
    ensure_dir(out)
    con = sqlite3.connect(str(db))
    try:
        cur = con.cursor()
        # Agrupa por mês da data da notícia; se não der para parsear, usa scraped_at
        all_articles = fetch_articles_all(cur)
        buckets: Dict[str, List[Article]] = {}
        for a in all_articles:
            ym = _ym_from_article_date(a.date)
            if not ym:
                try:
                    dt = datetime.fromisoformat(a.scraped_at.replace("Z", "+00:00"))
                    ym = f"{dt.year:04d}-{dt.month:02d}"
                except Exception:
                    continue
            buckets.setdefault(ym, []).append(a)

        # Ordena por scraped_at dentro de cada mês
        for arr in buckets.values():
            arr.sort(key=lambda x: x.scraped_at)

        months = sorted(buckets.keys())
        if only_months:
            wanted = {_normalize_ym(m) for m in only_months}
            months = [m for m in months if m in wanted]
        out_files: List[Path] = []
        for ym in months:
            out_files.append(export_month(cur, ym, buckets[ym], out))
        return out_files
    finally:
        con.close()


def main() -> None:
    p = argparse.ArgumentParser(description="Exporta artigos em Markdown por mês (YYYY-MM.md)")
    p.add_argument("--db", type=Path, default=Path("data/rapagem.db"), help="Caminho do DB")
    p.add_argument("--out", type=Path, default=Path("data/md"), help="Pasta de saída")
    p.add_argument(
        "--months",
        type=str,
        nargs="*",
        default=None,
        help="Lista de meses YYYY-MM para exportar (padrão: todos)",
    )
    args = p.parse_args()

    files = run(args.db, args.out, args.months)
    for pth in files:
        print(pth)


if __name__ == "__main__":
    main()
