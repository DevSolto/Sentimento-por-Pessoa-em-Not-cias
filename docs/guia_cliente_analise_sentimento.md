# Guia do Cliente — Análise de Sentimento e Relatórios (CSV)

Este guia explica, em linguagem simples, como funciona a análise de sentimento aplicada aos comentários das notícias e como interpretar os arquivos CSV gerados. O objetivo é que você entenda o que foi medido, como foi calculado e como usar os resultados.

## O que é analisado

- Para cada notícia do portal, coletamos os comentários dos leitores.
- Para cada pessoa citada na notícia, avaliamos se os comentários são positivos, negativos ou neutros “em relação a” essa pessoa.
- Quando o comentário não cita a pessoa diretamente, usamos pistas do próprio comentário (ex.: “concordo”, “fake news”) e o tom da notícia sobre a pessoa para inferir o sentido final.

## Como a análise funciona (resumo)

- Léxico em PT‑BR: usamos uma lista de palavras positivas/negativas (ex.: “bom”, “ruim”, “corrupto”, “excelente”).
- Regras simples:
  - Negação (ex.: “não bom” → inverte o sentido).
  - Intensificadores/atenuadores (ex.: “muito bom” dá mais peso que “bom”).
  - Menção direta do alvo: se o comentário cita o nome/sobrenome da pessoa, aumentamos a confiança.
- Alinhamento com a notícia: se o comentário faz referência explícita à matéria e indica concordância/discordância (ex.: “concordo”, “é mentira”), combinamos isso com o tom da notícia em relação à pessoa para chegar ao rótulo final.
- Saída: cada par (comentário, pessoa) recebe um rótulo final “positivo”, “negativo” ou “neutro”, acompanhado de uma medida de confiança.

Observação importante: esta é uma abordagem baseada em regras e vocabulário, transparente e ajustável. Não há “caixa‑preta” de IA aqui; se necessário, o vocabulário e as regras podem ser calibrados ao seu contexto.

## Onde encontrar os arquivos

Todos os relatórios ficam em data/reports/ no formato CSV (separados por vírgula, codificação UTF‑8). Abaixo, o que cada arquivo contém e como foi gerado.

### 1) comentarios_por_pessoa_sentimento.csv (detalhado)

Cada linha representa um par (comentário, pessoa citada na notícia).

- id_pessoa: identificador interno da pessoa.
- nome_pessoa: nome da pessoa citada.
- comment_key: identificador único do comentário na fonte.
- artigo_url: endereço da notícia.
- data_comentario: data/hora do comentário (quando disponível).
- comentario_sentimento: sentimento do comentário por si só (positivo/negativo/neutro) considerando a pessoa como alvo.
- comentario_score: intensidade numérica do sentimento do comentário (quanto maior o módulo, mais forte).
- comentario_confianca: confiança no sentimento do comentário (0 a 1).
- comentario_hits: quantidade de termos com polaridade identificados no comentário (base do cálculo).
- alvo_mencionado: 1 se o comentário cita a pessoa (nome ou sobrenome); 0 caso contrário.
- referencia_materia: 1 se o comentário referencia explicitamente a matéria/notícia/reportagem; 0 caso contrário.
- stance_noticia: posição do comentário em relação à notícia: “concorda”, “discorda” ou “indefinido”.
- noticia_sentimento: sentimento da própria notícia (título + corpo) em relação à pessoa.
- noticia_score: intensidade numérica do sentimento da notícia.
- noticia_confianca: confiança no sentimento da notícia em relação à pessoa.
- noticia_hits: quantidade de termos com polaridade identificados no texto da notícia.
- sentimento_final: rótulo final (positivo/negativo/neutro) após aplicar as regras de menção e alinhamento com a notícia.
- confianca_final: confiança do rótulo final (0 a 1).
- origem: explica como chegamos ao rótulo final:
  - comentario_direto: havia menção direta à pessoa no comentário.
  - alinhamento_noticia_stance: derivado por concordância/discordância explícita com a notícia.
  - alinhamento_noticia: derivado combinando o tom do comentário com o tom da notícia.
  - indefinido: não havia sinal suficiente; neutro por segurança.
- metodo: método usado na análise (nesta versão, léxico).
- versao: versão do método/relatório.

Como foi gerado: combinamos a tabela de pessoas citadas em cada notícia com os comentários daquela notícia (no banco data/rapagem.db) e aplicamos a análise acima para cada par (comentário, pessoa).

Como usar: filtre por "alvo_mencionado = 1" para leituras mais “estritas” (comentários que citam diretamente a pessoa). Use o campo "sentimento_final" para quadros e gráficos; "confianca_final" ajuda a ponderar.

### 2) sentimento_agregado_por_pessoa.csv (resumo por pessoa)

Consolida o arquivo detalhado por pessoa.

- id_pessoa, nome_pessoa: identificação.
- qtd_total: total de pares (comentário, pessoa) contabilizados.
- qtd_pos, qtd_neg, qtd_neu: contagens por sentimento final.
- pct_pos, pct_neg, pct_neu: percentuais sobre o total da pessoa.
- pct_mencao_direta: fração de pares com menção direta (alvo_mencionado = 1).

Como foi gerado: soma dos rótulos finais do arquivo “comentarios_por_pessoa_sentimento.csv”.

Como usar: ranking e evolução do sentimento por pessoa; comparação de perfis (ex.: % positivo vs. % negativo).

### 3) artigos.csv

Lista de notícias com estatísticas básicas.

- url: endereço da notícia.
- data: data de publicação (quando disponível).
- titulo: título da notícia.
- citacoes: nomes detectados no texto da notícia.
- tamanho_corpo: tamanho (em caracteres) do corpo da notícia.
- qtd_comentarios: total de comentários na notícia.
- raspado_em: quando a notícia foi coletada.

### 4) pessoa_artigos.csv

Relaciona cada pessoa às notícias em que foi citada.

- id_pessoa, nome_pessoa: identificação.
- url, data, titulo: notícia onde a pessoa aparece.
- raspado_em: quando a notícia foi coletada.

### 5) ranking_pessoas.csv

Ranking de pessoas por quantidade de notícias em que aparecem.

- id_pessoa, nome_pessoa: identificação.
- qtd_artigos: total de notícias em que a pessoa é citada.

### 6) co_citacoes.csv

Pares de pessoas citadas em uma mesma notícia.

- pessoa_a, pessoa_b: nomes.
- qtd_artigos_juntos: em quantas notícias apareceram juntas.

### 7) resumo_comentarios.csv

Resumo por notícia.

- url, titulo, data: identificação da notícia.
- qtd_comentarios: total de comentários na notícia.

### 8) top_comentadores.csv

Autores mais ativos nos comentários.

- autor: nome informado na plataforma.
- qtd_comentarios: número de comentários publicados.

### 9) linha_tempo_pessoa_mes.csv

Evolução mensal de citações por pessoa (com base na data de coleta).

- mes: ano-mês (AAAA-MM).
- nome_pessoa: pessoa citada.
- qtd_artigos: quantidade de notícias onde foi citada no mês.

### 10) comentarios_por_pessoa.csv

Volume de comentários por pessoa (sem sentimento).

- id_pessoa, nome_pessoa: identificação.
- qtd_comentarios: total de comentários nas notícias em que a pessoa foi citada.

## Boas práticas de leitura

- Use filtros básicos: por período, por pessoa e por "alvo_mencionado".
- Priorize "sentimento_final" e "confianca_final" nas análises; campos "comentario_*" mostram o tom “puro” do comentário, enquanto "noticia_*" mostram o tom da notícia sobre a pessoa.
- Trate valores com baixa confiança como “indefinidos” quando necessário.

## Limitações e cuidados

- Ironia/sarcasmo e expressões locais podem não ser reconhecidas pelo vocabulário inicial.
- Comentários podem discutir outra pessoa do mesmo artigo; o campo "alvo_mencionado" ajuda a filtrar os casos mais claros.
- Os percentuais são sensíveis ao volume; para bases pequenas, variações podem ser grandes.

## Dúvidas e ajustes

Podemos adaptar vocabulário, regras e cortes (limiares) ao seu contexto editorial. Se desejar, também é possível calibrar com uma amostra rotulada ou evoluir para um modelo estatístico supervisionado mantendo esta base como referência.

***

Versão do guia: 1.0
