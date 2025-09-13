# Análise de Sentimento Direcionado (Comentários → Pessoas Citadas)

## Visão Geral

- Objetivo: classificar o sentimento de comentários “em relação a” cada pessoa citada na notícia (sentimento direcionado por entidade).
- Abordagem: baseline léxico em PT‑BR com regras (negação, intensificadores/atenuadores) e detecção de menção direta ao alvo (nome/sobrenome).
- Entradas: banco SQLite `data/rapagem.db` com as tabelas `artigos`, `pessoas`, `artigos_pessoas`, `comentarios`.
- Saídas (CSV em `data/reports/`):
  - `comentarios_por_pessoa_sentimento.csv`: detalhado por (comentário, pessoa) com rótulo final derivado.
  - `sentimento_agregado_por_pessoa.csv`: agregados por pessoa (quantidades e percentuais com base no rótulo final).

## Arquitetura e Arquivos

- Código principal:
  - `src/sentiment.py`: analisador léxico direcionado (negação, intensificadores, menção do alvo).
  - `src/sentiment_report.py`: consulta o SQLite e gera os dois relatórios CSV.
  - `src/__init__.py`: importações tornadas lazy para evitar dependências pesadas quando rodar apenas relatórios.
- Dependências: os relatórios utilizam apenas a biblioteca padrão do Python (sqlite3, csv, etc.). O projeto possui outras dependências para scraping em `requirements.txt` (requests, beautifulsoup4, lxml, pandas, tqdm, python-dotenv), mas não são obrigatórias para executar esta etapa de relatórios.

## Como Funciona a Classificação

1. Direcionamento ao alvo: para cada comentário de um artigo, geramos pares com todas as pessoas citadas naquele artigo (`artigos` ↔ `artigos_pessoas` ↔ `pessoas`).
2. Menção direta: verificamos se o nome completo normalizado (sem acentos) aparece no texto ou se o sobrenome está presente. Se sim, `alvo_mencionado = 1` e a confiança aumenta.
3. Sentimento da notícia → pessoa: calculamos o sentimento do título + corpo da notícia em relação à pessoa (mesmo analisador léxico, usando nome/sobrenome como alvo). Isso dá o rótulo `noticia_sentimento` por pessoa.
4. Referência explícita à matéria no comentário: só aplicamos alinhamento quando o comentário referencia a matéria/notícia/reportagem (ex.: “matéria”, “reportagem”, “essa notícia”).
5. Derivação para comentários sem menção direta (com referência):
   - Se a notícia tem sentimento não neutro para a pessoa e o comentário expressa concordância explícita (ex.: “concordo”, “é verdade”, “tá certo”): o rótulo final segue o da notícia para a pessoa.
   - Se expressa discordância explícita (ex.: “não concordo”, “é mentira”, “fake news”): o rótulo final inverte o da notícia para a pessoa.
   - Se não há sinal explícito de concordância/discordância, usa-se o sentimento do comentário como proxy: propaga se a notícia é positiva; inverte se a notícia é negativa.
   - Se faltar sinal suficiente, o final é `neutro` com baixa confiança.
6. Léxico e regras:
   - Polaridade por termo (positivo/negativo) a partir de um léxico PT‑BR pequeno e ajustável.
   - Negação: inverte a polaridade se houver negador até 3 tokens antes ("não", "nunca", "jamais", "sem").
   - Intensificadores/atenuadores: multiplicam o peso (ex.: "muito bom" > "bom"; "pouco ruim" < "ruim").
   - Score: média dos termos polarizados do comentário; thresholds: `> 0.2` → positivo; `< -0.2` → negativo; caso contrário, neutro.
   - Confiança: cresce com |score| e recebe bônus quando `alvo_mencionado = 1`.

> Observação: por padrão, todos os pares (comentário, pessoa) são classificados, mesmo sem menção direta; você pode filtrar depois por `alvo_mencionado = 1` para uma leitura mais estrita.

## Como Executar

Pré‑requisitos:
- Python 3 instalado.
- Banco `data/rapagem.db` preenchido pelo pipeline de scraping.

Comando:
- `python3 -m src.sentiment_report`

Saídas geradas:
- `data/reports/comentarios_por_pessoa_sentimento.csv`
- `data/reports/sentimento_agregado_por_pessoa.csv`

## Esquema dos Relatórios

`data/reports/comentarios_por_pessoa_sentimento.csv`
- `id_pessoa`, `nome_pessoa`, `comment_key`, `artigo_url`, `data_comentario`.
- `comentario_sentimento`, `comentario_score`, `comentario_confianca`, `comentario_hits`.
- `alvo_mencionado`: 1 se nome/sobrenome aparece no comentário.
- `referencia_materia`: 1 se o comentário referencia explicitamente a matéria/notícia/reportagem.
- `stance_noticia`: `concorda` | `discorda` | `indefinido` (posição do comentário frente à notícia).
- `noticia_sentimento`, `noticia_score`, `noticia_confianca`, `noticia_hits` (sentimento da notícia em relação à pessoa).
- `sentimento_final`, `confianca_final`, `origem`:
  - `origem = comentario_direto` quando há menção direta.
  - `origem = alinhamento_noticia_stance` quando derivado por concordância/discordância explícita com a notícia.
  - `origem = alinhamento_noticia` quando derivado pelo sentimento do comentário (sem stance explícita).
  - `origem = indefinido` quando não há sinal suficiente (final neutro).
- `metodo`, `versao`.

`data/reports/sentimento_agregado_por_pessoa.csv`
- `qtd_total`, `qtd_pos`, `qtd_neg`, `qtd_neu`: contagens por pessoa.
- `pct_pos`, `pct_neg`, `pct_neu`: participações por pessoa.
- `pct_mencao_direta`: fração com `alvo_mencionado = 1`.

## Onde Ajustar/Calibrar

- Léxico: editar/adicionar termos em `src/sentiment.py` (classe `Lexicon.small_pt`).
  - Sugestões do domínio: “gestão”, “investigado”, “denúncia”, “rachadinha”, “golpista”, “competência”, “aprovação”, “rejeição”…
- Regras/thresholds: ajustar em `src/sentiment.py` (classe `TargetedLexiconAnalyzer.analyze`).
  - Janela de negação, multiplicadores de intensificadores, limites para neutro, fórmula de confiança.
- Menção direta: se desejar, trabalhe apenas com pares onde `alvo_mencionado = 1` (pós‑processamento do CSV ou ajuste do gerador).

## Limitações Conhecidas

- Ironia/sarcasmo e duplo sentido: difíceis para léxicos; podem exigir modelo supervisionado.
- Discurso reportado (“Fulano disse que Beltrano é corrupto”): atribuição do sentimento ao alvo depende de regra editorial.
- Múltiplas entidades: sem parsing sintático, a proximidade pode induzir ruído quando o comentário discute outra pessoa do mesmo artigo.
- Vocabulário local/coloquial: o léxico precisa de expansão com termos característicos do corpus.

## Evolução Recomendada

- Rotular uma amostra (100–300 pares) para calibrar thresholds e expandir o léxico.
- Usar “entity markers” e treinar um modelo PT‑BR (ex.: BERTimbau) para sentimento direcionado; manter o léxico como fallback quando a confiança do modelo for baixa.
- Agregar por janelas temporais (semanal/mensal) e cruzar com a linha do tempo de artigos para tendências por pessoa.

---

### Referências de Código

- `src/sentiment.py`
- `src/sentiment_report.py`
- `requirements.txt` (dependências do scraper)
