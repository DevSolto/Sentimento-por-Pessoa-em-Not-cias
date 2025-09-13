# Sentimento por Pessoa em Notícias

Projeto para raspagem de notícias e análise de sentimento direcionado a pessoas citadas, gerando CSVs e relatórios explicativos para uso editorial e acompanhamento.

## Passo a passo

1. Crie e ative um ambiente virtual (recomendado):
   - Linux/macOS:
     - `python -m venv .venv`
     - `source .venv/bin/activate`
   - Windows (PowerShell):
     - `python -m venv .venv`
     - `.venv\\Scripts\\Activate.ps1`

2. Instale as dependências:
   - `pip install -r requirements.txt`

3. Configure variáveis de ambiente:
   - Copie `.env.example` para `.env` e ajuste os valores (URL base, template de paginação e seletores CSS).
   - Ex.: `cp .env.example .env`

4. Abra o notebook:
   - `jupyter notebook` ou `jupyter lab`
   - Abra `notebooks/raspagem_noticias.ipynb`

5. Preencha os seletores no notebook (ou via `.env`) e rode as células.

## Boas práticas e ética
- Verifique o `robots.txt` do site e os termos de uso.
- Respeite limites: use delays entre requisições e número de páginas razoável.
- Identifique sua intenção de pesquisa/estudo quando possível e não sobrecarregue servidores.

## Estrutura
- `notebooks/raspagem_noticias.ipynb`: notebook principal com template de raspagem.
- `requirements.txt`: dependências mínimas (requests, bs4, pandas...).
- `.env.example`: modelo de configuração.
- `data/`: pasta para saídas (`raw/` e `processed/`).

## Dicas de seleção
- Use o inspetor do navegador para descobrir os seletores CSS dos links de notícia na listagem, e dos campos dentro de cada notícia (título, corpo, data).
- Ajuste `LISTING_PAGE_URL_TEMPLATE` para refletir a paginação do site (ex.: `?page={page}` ou `/pagina/{page}`).

## Possíveis extensões
- Detecção automática de próxima página por seletor (botão "Próxima").
- Persistência em SQLite.
- Uso de `httpx`/`asyncio` com limitação de concorrência.
- Selenium/Playwright para páginas altamente dinâmicas (JavaScript pesado).

## Problemas comuns
- Codificação/acentos: o `requests` e `BeautifulSoup` com `lxml` geralmente lidam bem, mas pode ser necessário forçar `response.encoding`.
- Bloqueios/403: reduza a taxa, varie o `User-Agent`, e assegure-se de estar em conformidade com as políticas do site.

## Dados locais (privacidade)
- Os dados gerados localmente (SQLite e CSVs em `data/`) não são versionados por padrão (`.gitignore`).
- A pasta `data/` é mantida apenas com um marcador (`data/.gitkeep`) para preservar a estrutura.

## Documentação
- Guia do Cliente — Análise de Sentimento e CSVs: docs/guia_cliente_analise_sentimento.md
- Detalhes técnicos da análise de sentimento: docs/analise_sentimento_direcionado.md

## Resumo dos CSVs principais
- `comentarios_por_pessoa_sentimento.csv`: detalhado por (comentário, pessoa). Campos‑chave: `id_pessoa`, `nome_pessoa`, `comment_key`, `artigo_url`, `comentario_sentimento`, `alvo_mencionado`, `noticia_sentimento`, `sentimento_final`, `confianca_final`, `origem`.
- `sentimento_agregado_por_pessoa.csv`: resumo por pessoa a partir do rótulo final. Campos‑chave: `id_pessoa`, `nome_pessoa`, `qtd_total`, `qtd_pos`, `qtd_neg`, `qtd_neu`, `pct_pos`, `pct_neg`, `pct_neu`, `pct_mencao_direta`.
