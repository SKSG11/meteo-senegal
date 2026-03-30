# Projet P-04 — Tableau de Bord Climatique Multi-Wilayas Pour La Sécurité Alimentaire — ISI Dakar 2025-2026

### Description
Infrastructure cloud AWS serverless qui collecte automatiquement
les données météo des 8 wilayas du Sénégal toutes les 3 heures.

### Architecture AWS
- Lambda Python (Collecte + Traitement + Dashboard)
- DynamoDB (ClimateData + ClimateDaily)
- S3 (Data Lake + Site Web Statique)
- EventBridge (déclenchement automatique 3h)
- CloudFront (distribution mondiale)
- CloudWatch (5 alarmes + métrique custom)
- IAM (principe du moindre privilège)

### Dashboard en direct
https://d2wxglhwu2o8ft.cloudfront.net

### Wilayas surveillées
Dakar, Thiès, Saint-Louis, Ziguinchor,Tambacounda, Kaolack, Louga, Diourbel

### Binôme
- Sokhna KIné Sy Gaye
- SAID HASSANE Amatoul-karim

### Responsable Pédagogique
   M. LAM Sabarane
   
### ISI Dakar — — 2025-2026
