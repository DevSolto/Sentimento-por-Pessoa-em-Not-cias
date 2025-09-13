from __future__ import annotations

import re
from typing import Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .config import ArticleSelectors, CommentSelectors


class Parser:
    @staticmethod
    def extract_text(el) -> str:
        if el is None:
            return ""
        text = " ".join(el.stripped_strings)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def parse_listing(html: str, *, base_url: str, link_selector: str) -> List[str]:
        soup = BeautifulSoup(html, "lxml")
        links: List[str] = []
        for a in soup.select(link_selector):
            href = a.get("href")
            if not href:
                continue
            links.append(urljoin(base_url, href))

        seen = set()
        uniq: List[str] = []
        for u in links:
            if u not in seen:
                seen.add(u)
                uniq.append(u)
        return uniq

    @staticmethod
    def _parse_iso_datetime(text: Optional[str]):
        if not text:
            return None
        from datetime import datetime
        try:
            t = text.strip().replace("Z", "+00:00")
            _ = datetime.fromisoformat(t)
            return t
        except Exception:
            return None

    @staticmethod
    def parse_article(html: str, url: str, sel: ArticleSelectors) -> Dict:
        soup = BeautifulSoup(html, "lxml")
        title_el = soup.select_one(sel.title)
        body_el = soup.select_one(sel.body)
        date_el = soup.select_one(sel.date)
        return {
            "url": url,
            "title": Parser.extract_text(title_el),
            "body": Parser.extract_text(body_el),
            "date": Parser.extract_text(date_el),
            "date_iso": Parser._parse_iso_datetime(date_el.get("datetime") if date_el else None),
        }

    @staticmethod
    def parse_listing_items(
        html: str,
        *,
        base_url: str,
        item_selector: str,
        link_selector: str,
        date_selector: str,
        date_attr: str = "datetime",
    ) -> List[Dict]:
        """Extrai pares {url, date_iso?} da página de listagem.

        Requer que cada item de listagem seja selecionável por `item_selector`.
        Dentro dele, serão buscados `link_selector` e `date_selector`.
        """
        soup = BeautifulSoup(html, "lxml")
        out: List[Dict] = []
        for item in soup.select(item_selector):
            a = item.select_one(link_selector)
            if not a:
                continue
            href = a.get("href")
            if not href:
                continue
            url = urljoin(base_url, href)

            d_el = item.select_one(date_selector)
            d_iso = None
            if d_el is not None:
                # primeiro tenta atributo (ex.: datetime)
                if date_attr:
                    d_iso = Parser._parse_iso_datetime(d_el.get(date_attr))
                if not d_iso:
                    # tenta texto sem formatação (só ISO simples)
                    d_iso = Parser._parse_iso_datetime(d_el.get_text(strip=True))

            out.append({"url": url, "date_iso": d_iso})
        return out

    @staticmethod
    def parse_comments(html: str, url: str, sel: CommentSelectors) -> List[Dict]:
        soup = BeautifulSoup(html, "lxml")
        out: List[Dict] = []
        for c in soup.select(sel.container):
            cid = c.get("id", "")
            author_el = c.select_one(sel.author)
            time_el = c.select_one(sel.time)
            content_el = c.select_one(sel.content)
            permalink_el = c.select_one(sel.permalink)

            href = permalink_el.get("href") if permalink_el else ""
            permalink = urljoin(url, href) if href else ""

            out.append(
                {
                    "article_url": url,
                    "comment_id": cid,
                    "author": Parser.extract_text(author_el),
                    "time_text": Parser.extract_text(time_el),
                    "time_iso": time_el.get("datetime") if time_el else "",
                    "content": Parser.extract_text(content_el),
                    "permalink": permalink,
                }
            )
        return out
