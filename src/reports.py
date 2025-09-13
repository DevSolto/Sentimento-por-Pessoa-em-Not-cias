from __future__ import annotations

import argparse
import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence, Tuple


@dataclass
class Report:
    name: str
    query: str
    params: Tuple = ()
    filename: str | None = None


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _write_csv(cur: sqlite3.Cursor, query: str, out_path: Path, params: Sequence | None = None) -> None:
    params = params or []
    cur.execute(query, params)
    rows = cur.fetchall()
    headers = [d[0] for d in cur.description or []]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if headers:
            w.writerow(headers)
        w.writerows(rows)


def build_reports() -> list[Report]:
    r: list[Report] = []

    # 1) Lista de artigos com contagens
    r.append(
        Report(
            name="articles",
            filename="artigos.csv",
            query=(
                """
                SELECT
                  a.url AS url,
                  a.date AS data,
                  a.title AS titulo,
                  a.matched_names AS citacoes,
                  LENGTH(COALESCE(a.body,'')) AS tamanho_corpo,
                  (SELECT COUNT(1) FROM comentarios c WHERE c.article_url = a.url) AS qtd_comentarios,
                  a.scraped_at AS raspado_em
                FROM artigos a
                ORDER BY a.scraped_at DESC
                """
            ),
        )
    )

    # 2) Artigos por pessoa (detalhado)
    r.append(
        Report(
            name="person_articles",
            filename="pessoa_artigos.csv",
            query=(
                """
                SELECT
                  p.id AS id_pessoa,
                  p.name AS nome_pessoa,
                  a.url AS url,
                  a.date AS data,
                  a.title AS titulo,
                  a.scraped_at AS raspado_em
                FROM artigos_pessoas ap
                JOIN pessoas p ON p.id = ap.person_id
                JOIN artigos a ON a.url = ap.article_url
                ORDER BY p.name, a.scraped_at DESC
                """
            ),
        )
    )

    # 3) Ranking de pessoas por número de artigos
    r.append(
        Report(
            name="people_rank",
            filename="ranking_pessoas.csv",
            query=(
                """
                SELECT
                  p.id AS id_pessoa,
                  p.name AS nome_pessoa,
                  COUNT(ap.article_url) AS qtd_artigos
                FROM pessoas p
                LEFT JOIN artigos_pessoas ap ON ap.person_id = p.id
                GROUP BY p.id, p.name
                ORDER BY qtd_artigos DESC, nome_pessoa
                """
            ),
        )
    )

    # 4) Coocorrências: pares de pessoas citadas no mesmo artigo
    r.append(
        Report(
            name="co_mentions",
            filename="co_citacoes.csv",
            query=(
                """
                SELECT
                  p1.name AS pessoa_a,
                  p2.name AS pessoa_b,
                  COUNT(*) AS qtd_artigos_juntos
                FROM artigos_pessoas ap1
                JOIN artigos_pessoas ap2
                  ON ap1.article_url = ap2.article_url
                 AND ap1.person_id < ap2.person_id
                JOIN pessoas p1 ON p1.id = ap1.person_id
                JOIN pessoas p2 ON p2.id = ap2.person_id
                GROUP BY p1.name, p2.name
                HAVING qtd_artigos_juntos > 0
                ORDER BY qtd_artigos_juntos DESC, pessoa_a, pessoa_b
                """
            ),
        )
    )

    # 5) Resumo de comentários por artigo
    r.append(
        Report(
            name="comments_summary",
            filename="resumo_comentarios.csv",
            query=(
                """
                SELECT
                  a.url AS url,
                  a.title AS titulo,
                  a.date AS data,
                  COUNT(c.comment_key) AS qtd_comentarios
                FROM artigos a
                LEFT JOIN comentarios c ON c.article_url = a.url
                GROUP BY a.url, a.title, a.date
                ORDER BY qtd_comentarios DESC, a.title
                """
            ),
        )
    )

    # 6) Top autores de comentários
    r.append(
        Report(
            name="top_commenters",
            filename="top_comentadores.csv",
            query=(
                """
                SELECT
                  TRIM(COALESCE(author, '')) AS autor,
                  COUNT(*) AS qtd_comentarios
                FROM comentarios
                GROUP BY TRIM(COALESCE(author, ''))
                HAVING autor <> ''
                ORDER BY qtd_comentarios DESC, autor
                """
            ),
        )
    )

    # 7) Timeline mensal por pessoa (com base em scraped_at)
    r.append(
        Report(
            name="timeline_person_month",
            filename="linha_tempo_pessoa_mes.csv",
            query=(
                """
                SELECT
                  strftime('%Y-%m', a.scraped_at) AS mes,
                  p.name AS nome_pessoa,
                  COUNT(*) AS qtd_artigos
                FROM artigos a
                JOIN artigos_pessoas ap ON ap.article_url = a.url
                JOIN pessoas p ON p.id = ap.person_id
                GROUP BY mes, nome_pessoa
                ORDER BY mes, nome_pessoa
                """
            ),
        )
    )

    # 8) Total de comentários em notícias onde cada pessoa é citada
    r.append(
        Report(
            name="comments_per_person",
            filename="comentarios_por_pessoa.csv",
            query=(
                """
                SELECT
                  p.id AS id_pessoa,
                  p.name AS nome_pessoa,
                  COUNT(c.comment_key) AS qtd_comentarios
                FROM pessoas p
                LEFT JOIN artigos_pessoas ap ON ap.person_id = p.id
                LEFT JOIN comentarios c ON c.article_url = ap.article_url
                GROUP BY p.id, p.name
                ORDER BY qtd_comentarios DESC, nome_pessoa
                """
            ),
        )
    )

    return r


def generate_reports(db_path: Path, out_dir: Path, only: Iterable[str] | None = None) -> list[Path]:
    out_files: list[Path] = []
    _ensure_dir(out_dir)

    con = sqlite3.connect(str(db_path))
    try:
        cur = con.cursor()
        for rep in build_reports():
            if only and rep.name not in set(only):
                continue
            filename = rep.filename or f"{rep.name}.csv"
            out_path = out_dir / filename
            _write_csv(cur, rep.query, out_path, rep.params)
            out_files.append(out_path)
    finally:
        con.close()

    return out_files


def main() -> None:
    p = argparse.ArgumentParser(description="Gera relatórios CSV a partir do banco SQLite")
    p.add_argument("--db", type=Path, default=Path("data/rapagem.db"), help="Caminho do SQLite .db")
    p.add_argument("--out", type=Path, default=Path("data/reports"), help="Pasta de saída para CSVs")
    p.add_argument(
        "--only",
        type=str,
        nargs="*",
        default=None,
        help=(
            "Gera apenas relatórios por nome (ex.: articles people_rank). "
            "Disponíveis: " + ", ".join(r.name for r in build_reports())
        ),
    )
    args = p.parse_args()

    out_files = generate_reports(args.db, args.out, args.only)
    for f in out_files:
        print(f)


if __name__ == "__main__":
    main()
