from __future__ import annotations

import calendar
from datetime import datetime, timezone
import random
import time
from typing import Dict, List, Tuple

import pandas as pd
from tqdm import tqdm

from .config import Config
from .http_client import HttpClient
from .parser import Parser
from .filtering import NameFilter
from .storage import SQLiteStorage


class Scraper:
    def __init__(self, cfg: Config, client: HttpClient, parser: Parser):
        self.cfg = cfg
        self.client = client
        self.parser = parser
        self.name_filter = NameFilter(cfg.names)
        self.storage = SQLiteStorage(cfg.db_path)
        # Filtros de data
        self.cutoff_utc = None  # meses recentes (min)
        self.start_utc = None   # DATE_AFTER (min inclusivo)
        self.end_utc = None     # DATE_BEFORE (max exclusivo)
        if self.cfg.months_back and self.cfg.months_back > 0:
            now_utc = datetime.now(timezone.utc)
            self.cutoff_utc = self._months_ago(now_utc, self.cfg.months_back)
        # DATE_AFTER / DATE_BEFORE (prioridade sobre months_back na filtragem)
        if self.cfg.date_after:
            da = self._parse_iso_to_utc(self.cfg.date_after)
            if da:
                self.start_utc = da
        if self.cfg.date_before:
            db = self._parse_iso_to_utc(self.cfg.date_before)
            if db:
                self.end_utc = db

    @staticmethod
    def _months_ago(dt: datetime, months: int) -> datetime:
        y, m = dt.year, dt.month - months
        while m <= 0:
            m += 12
            y -= 1
        # Ajusta o dia para o último dia do mês, se necessário
        last_day = calendar.monthrange(y, m)[1]
        day = min(dt.day, last_day)
        return dt.replace(year=y, month=m, day=day)

    @staticmethod
    def _parse_iso_to_utc(iso_text: str):
        try:
            t = iso_text.replace("Z", "+00:00")
            dt = datetime.fromisoformat(t)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt
        except Exception:
            return None

    def _within_date_filters(self, dt) -> bool:
        """Retorna True se a data dt passa pelos filtros configurados.
        Regras:
          - Se date_after (start_utc) definido: dt >= start
          - Se date_before (end_utc) definido: dt < end
          - Se nenhum date_* definido mas months_back (cutoff_utc) definido: dt >= cutoff
          - Se nenhum filtro de data definido ou dt inválido: True (sem filtro)
        """
        if dt is None:
            # Se existem filtros explícitos de data e não conseguimos avaliar, reprovamos o item
            if self.start_utc or self.end_utc or self.cutoff_utc:
                return False
            return True
        if self.start_utc and dt < self.start_utc:
            return False
        if self.end_utc and dt >= self.end_utc:
            return False
        if (not self.start_utc and not self.end_utc) and self.cutoff_utc and dt < self.cutoff_utc:
            return False
        return True

    def _sleep(self):
        time.sleep(random.uniform(*self.cfg.delay_range))

    def collect_links(self) -> List[str]:
        all_links: List[str] = []
        start_page = max(1, int(self.cfg.listing_start_page))
        end_page = min(int(self.cfg.max_pages), int(self.cfg.listing_end_page or self.cfg.max_pages))
        if end_page < start_page:
            end_page = start_page
        for page in tqdm(range(start_page, end_page + 1), desc="Listagem"):
            url = self.cfg.listing_tpl.format(page=page)
            resp = self.client.fetch(url)
            if resp.status_code != 200:
                print("Falha na página", page, resp.status_code)
                break

            # Se tivermos seletores de item+data, filtra já na listagem conforme filtros de data
            if self.cfg.listing_item_selector:
                items = self.parser.parse_listing_items(
                    resp.text,
                    base_url=self.cfg.base_url,
                    item_selector=self.cfg.listing_item_selector,
                    link_selector=self.cfg.listing_link_selector,
                    date_selector=self.cfg.listing_date_selector,
                    date_attr=self.cfg.listing_date_attr,
                )
                kept = 0
                page_dts = []
                for it in items:
                    diso = it.get("date_iso")
                    dt = self._parse_iso_to_utc(diso) if diso else None
                    if dt is not None:
                        page_dts.append(dt)
                    if not self._within_date_filters(dt):
                        continue
                    all_links.append(it["url"])
                    kept += 1
                # Early-stop heurístico quando listagem é do mais novo → mais antigo
                # - months_back apenas: se nada passou, paramos (como já estava)
                # - date_after definido: se o item mais novo da página já é < start, paramos
                if kept == 0 and (self.cutoff_utc and not (self.start_utc or self.end_utc)):
                    break
                if kept == 0 and self.start_utc and page_dts:
                    try:
                        if max(page_dts) < self.start_utc:
                            break
                    except Exception:
                        pass
            else:
                links = self.parser.parse_listing(
                    resp.text,
                    base_url=self.cfg.base_url,
                    link_selector=self.cfg.article_sel.link,
                )
                all_links.extend(links)
            self._sleep()

        seen = set()
        unique_links: List[str] = []
        for u in all_links:
            if u not in seen:
                seen.add(u)
                unique_links.append(u)
        return unique_links

    def scrape_articles(self, links: List[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
        rows: List[Dict] = []
        comment_rows: List[Dict] = []
        for i, url in tqdm(list(enumerate(links, start=1)), total=len(links), desc="Artigos"):
            try:
                resp = self.client.fetch(url)
                if resp.status_code != 200:
                    print("Falha artigo", url, resp.status_code)
                    continue
                item = self.parser.parse_article(resp.text, url, self.cfg.article_sel)

                # Filtro por data (DATE_AFTER/DATE_BEFORE têm prioridade; depois months_back)
                adt = None
                if item.get("date_iso"):
                    adt = self._parse_iso_to_utc(item["date_iso"])  # type: ignore[arg-type]
                if not self._within_date_filters(adt):
                    continue

                # Verificação do filtro de nomes (título + corpo)
                combined_text = f"{item.get('title','')}\n{item.get('body','')}"
                matched, matched_names = self.name_filter.match(combined_text)
                if not matched:
                    # Ignora artigos que não batem o filtro
                    continue

                if matched_names:
                    item["matched_names"] = "; ".join(matched_names)
                rows.append(item)
                # Persistência incremental no SQLite
                self.storage.upsert_article(item)
                # Ligação N:N artigo ↔ pessoas
                if matched_names:
                    self.storage.link_article_people(item["url"], matched_names)

                # Comentários apenas das notícias selecionadas
                parsed_comments = self.parser.parse_comments(resp.text, url, self.cfg.comment_sel)
                comment_rows.extend(parsed_comments)
                self.storage.upsert_comments(parsed_comments)
            except Exception as e:
                print("Erro em", url, e)
            finally:
                self._sleep()

        df_articles = pd.DataFrame(rows)
        df_comments = pd.DataFrame(comment_rows) if comment_rows else pd.DataFrame()
        return df_articles, df_comments

    def run(self):
        print("Config:")
        print(f"  BASE_URL = {self.cfg.base_url}")
        print(f"  LISTING_TPL = {self.cfg.listing_tpl}")
        print(f"  MAX_PAGES = {self.cfg.max_pages}")
        print(f"  PAGES = {self.cfg.listing_start_page}..{self.cfg.listing_end_page}")
        print(f"  OUTPUT_DIR = {self.cfg.output_dir}")
        print(f"  DB_PATH = {self.cfg.db_path}")
        if self.name_filter.enabled():
            print(f"  NAMES_FILTER = {self.name_filter.original}")
        else:
            print("  NAMES_FILTER = (desativado)")
        if self.start_utc or self.end_utc:
            print(
                "  DATA = "+
                (f">= {self.start_utc.isoformat()}" if self.start_utc else "")+
                (" e " if self.start_utc and self.end_utc else "")+
                (f"< {self.end_utc.isoformat()}" if self.end_utc else "")
            )
        elif self.cutoff_utc:
            print(f"  MONTHS_BACK = {self.cfg.months_back} (cutoff >= {self.cutoff_utc.isoformat()})")
        else:
            print("  DATA = (sem filtro)")

        links = self.collect_links()
        print(f"Links coletados (únicos): {len(links)}")

        df_articles, df_comments = self.scrape_articles(links)

        articles_csv = self.cfg.processed_dir / "noticias.csv"
        articles_json = self.cfg.processed_dir / "noticias.json"
        df_articles.to_csv(articles_csv, index=False)
        df_articles.to_json(articles_json, orient="records", force_ascii=False)

        print("Salvo:")
        print("  ", articles_csv)
        print("  ", articles_json)

        if not df_comments.empty:
            comments_csv = self.cfg.processed_dir / "comentarios.csv"
            comments_json = self.cfg.processed_dir / "comentarios.json"
            df_comments.to_csv(comments_csv, index=False)
            df_comments.to_json(comments_json, orient="records", force_ascii=False)
            print("  ", comments_csv)
            print("  ", comments_json)
