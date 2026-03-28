# Datos del Proyecto

Coloca aquí los archivos CSV de precios históricos.

## Formato esperado

Cada archivo debe llamarse `{TICKER}.csv` y tener columnas OHLCV:

```
date,open,high,low,close,volume
2020-01-02,300.35,300.35,295.21,298.58,25000000
2020-01-03,298.10,299.40,294.50,296.32,23000000
...
```

## Archivos necesarios

| Archivo     | Activo            | Tipo    |
|-------------|-------------------|---------|
| GLD.csv     | SPDR Gold Shares  | ETF     |
| QQQ.csv     | Invesco QQQ       | ETF     |
| TLT.csv     | iShares 20Y Bond  | ETF     |
| AAPL.csv    | Apple             | Acción  |
| NVDA.csv    | NVIDIA            | Acción  |
| META.csv    | Meta Platforms    | Acción  |
| AMZN.csv    | Amazon            | Acción  |
| XOM.csv     | ExxonMobil        | Acción  |
| PLTR.csv    | Palantir          | Acción  |
| COIN.csv    | Coinbase          | Acción  |
| BTC.csv     | Bitcoin           | Crypto  |

## Rango de fechas

- **Entrenamiento**: 2020-01-01 → 2024-12-31
- **Test (demo 2025)**: 2025-01-01 → 2025-12-31
