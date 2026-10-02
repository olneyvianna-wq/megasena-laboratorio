# Mega-Sena Laboratório

Laboratório estatístico para estudo dos concursos da Mega-Sena.

## Objetivos

- armazenar todos os concursos históricos;
- calcular estatísticas descritivas;
- comparar resultados reais com um modelo aleatório teórico;
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

