# Alarmes CloudWatch — Projet P-04

## 5 Alarmes configurées

| # | Nom | Condition | Action |
|---|-----|-----------|--------|
| 1 | p04-alerte-temperature-42 | Température > 42°C | Email SNS |
| 2 | p04-alerte-precipitation-100mm | Pluie > 100mm/24h | Email SNS |
| 3 | p04-alerte-echec-lambda | Errors Lambda >= 1 | Email SNS |
| 4 | p04-alerte-latence-5s | Duration > 5000ms | Email SNS |
| 5 | p04-alerte-erreurs-dynamodb | SystemErrors >= 1 | Email SNS |

## Métrique personnalisée
- Namespace : P04/Meteo
- Métrique  : WilayasCollectees
- Objectif  : 8/8 par cycle
- Unité     : Count
