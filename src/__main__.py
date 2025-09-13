from __future__ import annotations

# Suporte a execução como módulo (python -m src)
# e como arquivo direto (python src/__main__.py)
try:  # quando executado como módulo
    from . import Config, HttpClient, Parser, Scraper
except Exception:  # fallback para execução direta
    import os
    import sys
    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if pkg_root not in sys.path:
        sys.path.insert(0, pkg_root)
    from src import Config, HttpClient, Parser, Scraper


def main() -> None:
    cfg = Config.from_env()
    client = HttpClient(cfg.headers)
    parser = Parser()
    Scraper(cfg, client, parser).run()


if __name__ == "__main__":
    main()
