# Mega-Sena Laboratório

Laboratório estatístico para estudo dos concursos da Mega-Sena.

## Objetivos

- armazenar todos os concursos históricos;
- calcular estatísticas descritivas;
- separar o **Universo dos Realizáveis (UR)** — combinações historicamente observadas — do **Universo dos Possíveis (UP)** — combinações matematicamente possíveis;
- analisar o UR como base histórica distinta, sem preencher a base com combinações nunca observadas;
- comparar resultados reais com modelos estatísticos quando isso for explicitamente desejado;
- executar simulações de Monte Carlo;
- estudar frequência, atraso, repetição, pares, trincas, consecutivos, soma, paridade e distribuição por faixas;
- separar claramente análise estatística de qualquer alegação de previsão.

## Arquitetura inicial

- **API:** FastAPI + Python
- **Banco:** PostgreSQL
- **Deploy:** Railway
- **Dados:** importação CSV/JSON e camada preparada para ingestão da fonte oficial da CAIXA
- **Análises:** NumPy/Pandas/SciPy

## Modelo estatístico

Uma aposta simples de 6 dezenas é uma combinação entre 60 dezenas:

C(60, 6) = 50.063.860.

O laboratório não assume que padrões históricos alterem a probabilidade matemática de uma combinação específica. O objetivo é medir padrões e comparar os dados observados com o comportamento esperado sob um modelo aleatório.

## Rodando localmente

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API: `http://localhost:8000`

Documentação: `http://localhost:8000/docs`\n\n### Monte Carlo\n\n`GET /stats/monte-carlo?simulations=200&seed=20261002` compara frequência, qui-quadrado, soma, consecutivos e sobreposição histórica com simulações independentes de 6 dezenas em 60. O endpoint aceita de 10 a 1000 simulações e não roda no startup.

## Variáveis de ambiente

- `DATABASE_URL`: URL PostgreSQL.
- `PORT`: porta HTTP, usada pelo Railway.

\n\n### Seis universos ordenados\n\n`GET /stats/ordered-universes` analisa as seis posições após ordenar cada concurso. Para cada posição calcula suporte realizável, distribuição histórica e distribuição teórica exata do k-ésimo valor de uma amostra uniforme de 6 dezenas em 60. A condição conjunta é `x1 < x2 < ... < x6`.\n

### Universo dos Realizáveis (UR)

`GET /stats/realizables` refaz a análise combinatória usando apenas as combinações distintas que efetivamente apareceram no histórico. Repetições da mesma combinação são contabilizadas separadamente como observações históricas, mas não criam um novo elemento do UR.

**Importante:** o UR não é uma nova probabilidade matemática. Ele é o conjunto empírico observado. A análise temporal (independência, calendário etc.) continua sendo feita sobre a sequência dos concursos, porque retirar repetições de combinações destruiria a ordem temporal necessária para esses testes.
