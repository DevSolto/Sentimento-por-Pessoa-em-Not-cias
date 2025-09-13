from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple, Dict, Tuple as Tup

from .sentiment import TargetedLexiconAnalyzer, normalize, SentimentResult


@dataclass
class SentimentReportConfig:
    db_path: Path = Path("data/rapagem.db")
    out_dir: Path = Path("data/reports")
    out_file: str = "comentarios_por_pessoa_sentimento.csv"


QUERY = """
SELECT
  p.id          AS id_pessoa,
  p.name        AS nome_pessoa,
  p.name_norm   AS nome_norm,
  a.url         AS artigo_url,
  a.title       AS titulo_artigo,
  COALESCE(c.time_iso, c.time_text) AS data_comentario,
  c.comment_key AS comment_key,
  c.author      AS autor,
  c.content     AS conteudo
FROM artigos a
JOIN artigos_pessoas ap ON ap.article_url = a.url
JOIN pessoas p ON p.id = ap.person_id
JOIN comentarios c ON c.article_url = a.url
-- Opcional: filtros por data ou pessoa podem ser adicionados aqui
ORDER BY p.name, a.scraped_at DESC
"""

ARTICLE_QUERY = """
SELECT
  p.id    AS id_pessoa,
  p.name  AS nome_pessoa,
  a.url   AS artigo_url,
  a.title AS titulo_artigo,
  a.body  AS corpo
FROM artigos a
JOIN artigos_pessoas ap ON ap.article_url = a.url
JOIN pessoas p ON p.id = ap.person_id
ORDER BY a.scraped_at DESC
"""


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _has_article_reference(text: str) -> bool:
    t = normalize(text)
    # Palavras/frases que indicam referência explícita à matéria/notícia/reportagem
    keys = (
        "materia",
        "noticia",
        "reportagem",
        "esta materia",
        "essa materia",
        "esta noticia",
        "essa noticia",
        "esta reportagem",
        "essa reportagem",
        "a materia",
        "a noticia",
        "a reportagem",
        "no farol",
        "do farol",
    )
    return any(k in t for k in keys)


def _detect_news_stance(text: str) -> str:
    """Detecta se o comentário concorda/discorda da notícia.

    Retorna: 'concorda' | 'discorda' | 'indefinido'
    """
    t = normalize(text)
    # Primeiro padrões de discordância (para evitar 'nao concordo' casar com 'concordo')
    disagree = (
        "discordo",
        "nao concordo",
        "mentira",
        "e mentira",
        "isso e mentira",
        "fake news",
        "fake",
        "nao e verdade",
        "falso",
        "nao confere",
        "improcedente",
        "nao procede",
        "errado",
        "nada a ver",
    )
    if any(pat in t for pat in disagree):
        return "discorda"

    agree = (
        "concordo",
        "concorda",
        "verdade",
        "e verdade",
        "isso e verdade",
        "confere",
        "procedente",
        "ta certo",
        "esta certo",
        "correto",
        "isso mesmo",
        "bem dito",
    )
    if any(pat in t for pat in agree):
        return "concorda"

    return "indefinido"


def _compute_article_sentiments(cur: sqlite3.Cursor, analyzer: TargetedLexiconAnalyzer) -> Dict[Tup[str, int], SentimentResult]:
    cur.execute(ARTICLE_QUERY)
    rows = cur.fetchall()
    art_res: Dict[Tup[str, int], SentimentResult] = {}
    for (id_pessoa, nome_pessoa, artigo_url, titulo, corpo) in rows:
        target_variants = [nome_pessoa]
        parts = [p for p in normalize(nome_pessoa).split(" ") if p]
        if parts:
            target_variants.append(parts[-1])
        texto = (titulo or "") + "\n\n" + (corpo or "")
        res = analyzer.analyze(texto, target_names=target_variants)
        art_res[(str(artigo_url), int(id_pessoa))] = res
    return art_res


def _derive_final_label(
    comment_res: SentimentResult,
    article_res: SentimentResult | None,
    mentioned: bool,
    article_ref: bool,
    stance: str,
) -> tuple[str, float, str]:
    if mentioned:
        return comment_res.label, comment_res.confidence, "comentario_direto"

    # Sem menção direta: só alinha se houver referência explícita à matéria
    if not article_ref:
        return "neutro", min(0.5, max(0.25, comment_res.confidence * 0.5)), "indefinido"

    if article_res and article_res.hits > 0 and article_res.label in ("positivo", "negativo"):
        # 1) Se há stance explícito, usa-o
        if stance in ("concorda", "discorda"):
            if stance == "concorda":
                final_label = article_res.label
            else:  # discorda
                final_label = "negativo" if article_res.label == "positivo" else "positivo"
            final_conf = min(1.0, 0.6 + 0.4 * article_res.confidence)
            return final_label, round(final_conf, 3), "alinhamento_noticia_stance"

        # 2) Caso sem stance, cai no alinhamento pelo sentimento do comentário
        if comment_res.hits > 0 and comment_res.label in ("positivo", "negativo"):
            if article_res.label == "positivo":
                final_label = comment_res.label
            else:
                final_label = "positivo" if comment_res.label == "negativo" else "negativo"
            final_conf = min(1.0, 0.5 + (article_res.confidence + comment_res.confidence) / 2)
            return final_label, round(final_conf, 3), "alinhamento_noticia"

    # Caso sem sinal suficiente
    return "neutro", min(0.5, max(0.25, comment_res.confidence * 0.5)), "indefinido"


def generate_sentiment_report(cfg: SentimentReportConfig, analyzer: TargetedLexiconAnalyzer | None = None) -> Path:
    analyzer = analyzer or TargetedLexiconAnalyzer()
    ensure_dir(cfg.out_dir)
    out_path = cfg.out_dir / cfg.out_file

    # Abre em modo somente leitura para evitar criar WAL/journal no sandbox
    abs_path = cfg.db_path.resolve()
    db_uri = f"file:{abs_path}?mode=ro"
    con = sqlite3.connect(db_uri, uri=True)
    try:
        cur = con.cursor()
        article_map = _compute_article_sentiments(cur, analyzer)
        cur.execute(QUERY)
        rows = cur.fetchall()
        headers = [d[0] for d in cur.description or []]

        with out_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            # Cabeçalho de saída
            w.writerow([
                "id_pessoa",
                "nome_pessoa",
                "comment_key",
                "artigo_url",
                "data_comentario",
                # análise do comentário (direta)
                "comentario_sentimento",
                "comentario_score",
                "comentario_confianca",
                "comentario_hits",
                "alvo_mencionado",
                "referencia_materia",
                "stance_noticia",
                # análise da notícia em relação à pessoa
                "noticia_sentimento",
                "noticia_score",
                "noticia_confianca",
                "noticia_hits",
                # rótulo final derivado
                "sentimento_final",
                "confianca_final",
                "origem",
                # metadados
                "metodo",
                "versao",
            ])

            for row in rows:
                (
                    id_pessoa,
                    nome_pessoa,
                    nome_norm,
                    artigo_url,
                    titulo_artigo,
                    data_comentario,
                    comment_key,
                    autor,
                    conteudo,
                ) = row

                # Nomes-alvo: nome completo e última palavra (sobrenome)
                target_variants = [nome_pessoa]
                parts = [p for p in normalize(nome_pessoa).split(" ") if p]
                if parts:
                    target_variants.append(parts[-1])

                res = analyzer.analyze(conteudo or "", target_names=target_variants)
                art_res = article_map.get((str(artigo_url), int(id_pessoa)))
                ref = _has_article_reference(conteudo or "")
                stance = _detect_news_stance(conteudo or "")
                final_label, final_conf, origin = _derive_final_label(res, art_res, res.mentioned, ref, stance)

                w.writerow([
                    id_pessoa,
                    nome_pessoa,
                    comment_key,
                    artigo_url,
                    data_comentario,
                    # comentário base
                    res.label,
                    f"{res.score:.4f}",
                    f"{res.confidence:.3f}",
                    res.hits,
                    1 if res.mentioned else 0,
                    1 if ref else 0,
                    stance,
                    # notícia
                    (art_res.label if art_res else "neutro"),
                    f"{(art_res.score if art_res else 0.0):.4f}",
                    f"{(art_res.confidence if art_res else 0.3):.3f}",
                    (art_res.hits if art_res else 0),
                    # final derivado
                    final_label,
                    f"{final_conf:.3f}",
                    origin,
                    # meta
                    "lexico_v1",
                    "0.1.0",
                ])

    finally:
        con.close()

    return out_path


def aggregate_by_person(source_csv: Path, out_dir: Path) -> Path:
    out_path = out_dir / "sentimento_agregado_por_pessoa.csv"
    counts: dict[tuple[str, str], dict[str, float]] = {}
    with source_csv.open("r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            pid = row["id_pessoa"]
            pname = row["nome_pessoa"]
            key = (pid, pname)
            d = counts.setdefault(key, {"pos": 0, "neg": 0, "neu": 0, "total": 0, "mention": 0})
            # Usa o rótulo final se disponível; caso contrário, usa o antigo campo 'sentimento'
            lab = row.get("sentimento_final") or row.get("sentimento") or "neutro"
            if lab == "positivo":
                d["pos"] += 1
            elif lab == "negativo":
                d["neg"] += 1
            else:
                d["neu"] += 1
            d["total"] += 1
            if row.get("alvo_mencionado") in ("1", 1):
                d["mention"] += 1

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "id_pessoa",
            "nome_pessoa",
            "qtd_total",
            "qtd_pos",
            "qtd_neg",
            "qtd_neu",
            "pct_pos",
            "pct_neg",
            "pct_neu",
            "pct_mencao_direta",
        ])
        for (pid, pname), d in sorted(counts.items(), key=lambda kv: (-kv[1]["total"], kv[0][1])):
            tot = max(1.0, float(d["total"]))
            w.writerow([
                pid,
                pname,
                int(d["total"]),
                int(d["pos"]),
                int(d["neg"]),
                int(d["neu"]),
                f"{(d['pos']/tot):.3f}",
                f"{(d['neg']/tot):.3f}",
                f"{(d['neu']/tot):.3f}",
                f"{(d['mention']/tot):.3f}",
            ])

    return out_path


def main() -> None:
    cfg = SentimentReportConfig()
    detailed = generate_sentiment_report(cfg)
    agg = aggregate_by_person(detailed, cfg.out_dir)
    print(detailed)
    print(agg)


if __name__ == "__main__":
    main()
