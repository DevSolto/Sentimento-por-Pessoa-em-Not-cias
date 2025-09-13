from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple, List

from dotenv import load_dotenv


@dataclass
class ArticleSelectors:
    link: str = "a.article-link"
    title: str = "h1.title"
    body: str = "div.article-body"
    date: str = "time"


@dataclass
class CommentSelectors:
    container: str = "article.comment"
    author: str = ".comment-author"
    time: str = "time.comment-time"
    content: str = ".comment-content"
    permalink: str = "a.comment-permalink"


@dataclass
class Config:
    output_dir: Path
    raw_dir: Path
    processed_dir: Path
    db_path: Path
    base_url: str
    listing_tpl: str
    max_pages: int
    delay_range: Tuple[float, float]
    months_back: int
    headers: Dict[str, str]
    article_sel: ArticleSelectors
    comment_sel: CommentSelectors
    names: List[str]
    # Filtros de data opcionais (ISO: YYYY-MM-DD ou YYYY-MM-DDTHH:MM:SSZ)
    date_after: str
    date_before: str
    # Seletores opcionais para filtrar por data já na listagem
    listing_item_selector: str
    listing_link_selector: str
    listing_date_selector: str
    listing_date_attr: str
    listing_start_page: int
    listing_end_page: int

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()

        output_dir = Path(os.getenv("OUTPUT_DIR", "data"))
        raw_dir = output_dir / "raw"
        processed_dir = output_dir / "processed"
        raw_dir.mkdir(parents=True, exist_ok=True)
        processed_dir.mkdir(parents=True, exist_ok=True)
        # Caminho do banco SQLite (padrão: <OUTPUT_DIR>/rapagem.db)
        db_env = os.getenv("DB_PATH")
        db_path = Path(db_env) if db_env else (output_dir / "rapagem.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)

        base_url = os.getenv("BASE_URL", "https://EXEMPLO.com")
        listing_tpl = os.getenv(
            "LISTING_PAGE_URL_TEMPLATE",
            "https://EXEMPLO.com/noticias?page={page}",
        )
        max_pages = int(os.getenv("MAX_PAGES", "2"))
        months_back = int(os.getenv("MONTHS_BACK", "0"))  # 0 = desativado
        date_after = os.getenv("DATE_AFTER", "").strip()
        date_before = os.getenv("DATE_BEFORE", "").strip()

        dmin, dmax = (os.getenv("REQUEST_DELAY_RANGE", "1,2").split(",") + ["2"])[:2]
        delay_range = (float(dmin), float(dmax))

        article_sel = ArticleSelectors(
            link=os.getenv("ARTICLE_LINK_SELECTOR", ArticleSelectors.link),
            title=os.getenv("ARTICLE_TITLE_SELECTOR", ArticleSelectors.title),
            body=os.getenv("ARTICLE_BODY_SELECTOR", ArticleSelectors.body),
            date=os.getenv("ARTICLE_DATE_SELECTOR", ArticleSelectors.date),
        )

        comment_sel = CommentSelectors(
            container=os.getenv("COMMENT_CONTAINER_SELECTOR", CommentSelectors.container),
            author=os.getenv("COMMENT_AUTHOR_SELECTOR", CommentSelectors.author),
            time=os.getenv("COMMENT_TIME_SELECTOR", CommentSelectors.time),
            content=os.getenv("COMMENT_CONTENT_SELECTOR", CommentSelectors.content),
            permalink=os.getenv("COMMENT_PERMALINK_SELECTOR", CommentSelectors.permalink),
        )

        # Seletores opcionais para data diretamente na listagem
        listing_item_selector = os.getenv("LISTING_ITEM_SELECTOR", "").strip()
        listing_link_selector = os.getenv(
            "LISTING_LINK_SELECTOR", article_sel.link
        ).strip()
        listing_date_selector = os.getenv("LISTING_DATE_SELECTOR", "time").strip()
        listing_date_attr = os.getenv("LISTING_DATE_ATTR", "datetime").strip()

        # Intervalo de páginas da listagem (inclusivo)
        def _to_int(v: str, default: int) -> int:
            try:
                return int(v)
            except Exception:
                return default

        listing_start_page = _to_int(os.getenv("LISTING_START_PAGE", "1"), 1)
        if listing_start_page < 1:
            listing_start_page = 1
        listing_end_page = _to_int(os.getenv("LISTING_END_PAGE", str(max_pages)), max_pages)
        if listing_end_page < listing_start_page:
            listing_end_page = listing_start_page

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0 Safari/537.36"
            ),
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        # Lista de nomes (filtro). Use vírgula, ponto-e-vírgula ou quebra de linha.
        raw_names = os.getenv("NAMES_FILTER", "").strip()
        names: List[str] = []
        if raw_names:
            import re as _re
            parts = [_p.strip() for _p in _re.split(r"[,;\n]+", raw_names) if _p.strip()]
            names = parts

        return cls(
            output_dir=output_dir,
            raw_dir=raw_dir,
            processed_dir=processed_dir,
            db_path=db_path,
            base_url=base_url,
            listing_tpl=listing_tpl,
            max_pages=max_pages,
            delay_range=delay_range,
            months_back=months_back,
            headers=headers,
            article_sel=article_sel,
            comment_sel=comment_sel,
            names=names,
            date_after=date_after,
            date_before=date_before,
            listing_item_selector=listing_item_selector,
            listing_link_selector=listing_link_selector,
            listing_date_selector=listing_date_selector,
            listing_date_attr=listing_date_attr,
            listing_start_page=listing_start_page,
            listing_end_page=listing_end_page,
        )
