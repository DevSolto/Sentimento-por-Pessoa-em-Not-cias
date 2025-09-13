from __future__ import annotations

import argparse
from pathlib import Path

try:
    # when run as module
    from .config import Config
    from .storage import SQLiteStorage
except Exception:
    # fallback for direct execution
    import os
    import sys
    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if pkg_root not in sys.path:
        sys.path.insert(0, pkg_root)
    from src.config import Config
    from src.storage import SQLiteStorage


def main() -> None:
    ap = argparse.ArgumentParser(description="Migra nomes de tabelas EN -> PT-BR, sem perder dados")
    ap.add_argument("--db", type=Path, default=None, help="Caminho do banco .db (padrão: do .env)")
    args = ap.parse_args()

    cfg = Config.from_env()
    db_path = args.db or cfg.db_path

    # Instanciar storage dispara migração no __post_init__
    st = SQLiteStorage(db_path)
    st.close()
    print(f"Migração concluída em: {db_path}")


if __name__ == "__main__":
    main()

