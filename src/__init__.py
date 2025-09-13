"""Pacote da raspagem de notícias.

Mantemos o ``__init__`` leve (sem reexports imediatos) para evitar
importações pesadas desnecessárias quando apenas submódulos específicos
forem usados (ex.: relatórios, sentimento, etc.).
"""

__all__ = [
    # Reexports intencionais podem ser feitos via __getattr__ lazy se necessário.
    "main",
]


def main() -> None:
    """Entrypoint programático para rodar o scraper.

    Importações são feitas dentro da função para evitar custos/depêndencias
    ao importar apenas o pacote.
    """
    from .config import Config  # lazy import
    from .http_client import HttpClient  # lazy import
    from .parser import Parser  # lazy import
    from .scraper import Scraper  # lazy import

    cfg = Config.from_env()
    client = HttpClient(cfg.headers)
    parser = Parser()
    Scraper(cfg, client, parser).run()
