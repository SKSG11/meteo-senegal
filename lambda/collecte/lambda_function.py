import json
import boto3
import urllib.request
import time
from datetime import datetime

# ---- CONFIGURATION ----
API_KEY   = "4d4706012bea109d6ef9d3c0242696f7"        
BUCKET    = "p04-meteo-datalake-2026" 
TABLE     = "ClimateData"


NOM_LAMBDA_TRAITEMENT = "lambda-traitement-climat"
NOM_LAMBDA_DASHBOARD  = "Lambda-Dashboard"

WILAYAS = [
    {"nom": "Dakar",       "lat": 14.6937, "lon": -17.4441},
    {"nom": "Thies",       "lat": 14.7833, "lon": -16.9167},
    {"nom": "SaintLouis",  "lat": 16.0179, "lon": -16.4897},
    {"nom": "Ziguinchor",  "lat": 12.5500, "lon": -16.2667},
    {"nom": "Tambacounda", "lat": 13.7707, "lon": -13.6673},
    {"nom": "Kaolack",     "lat": 14.1490, "lon": -16.0726},
    {"nom": "Louga",       "lat": 15.6144, "lon": -16.2244},
    {"nom": "Diourbel",    "lat": 14.6560, "lon": -16.2310},
]

# Clients AWS
dynamodb       = boto3.resource("dynamodb")
s3             = boto3.client("s3")
lambda_client  = boto3.client("lambda", region_name="us-east-1")
cw             = boto3.client("cloudwatch", region_name="us-east-1")


# FONCTION 1 — Appel API avec RETRY
def get_meteo_avec_retry(wilaya, max_tentatives=3):
    """
    Appelle OpenWeatherMap avec retry automatique.
    Si ça échoue, on réessaie jusqu'à 3 fois.
    Entre chaque tentative on attend 2 secondes.
    """
    url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?lat={wilaya['lat']}&lon={wilaya['lon']}"
        f"&appid={API_KEY}&units=metric&lang=fr"
    )

    for tentative in range(1, max_tentatives + 1):
        try:
            print(f"Tentative : {tentative}/{max_tentatives} pour {wilaya['nom']}")
            reponse = urllib.request.urlopen(url, timeout=10)
            data    = json.loads(reponse.read())

            # Extraction des données météo
            return {
                "temp_celsius":     data["main"]["temp"],
                "humidite_pct":     data["main"]["humidity"],
                "precipitation_mm": data.get("rain", {}).get("1h", 0),
                "vent_kmh":         round(data["wind"]["speed"] * 3.6, 1),
                "pression_hpa":     data["main"]["pressure"],
                "condition_meteo":  data["weather"][0]["description"],
            }

        except Exception as erreur:
            print(f"Échec tentative {tentative} : {erreur}")

            # Si c'est pas la dernière tentative, on attend et on réessaie
            if tentative < max_tentatives:
                print(f" Attente 2s avant retry...")
                time.sleep(2)
            else:
                # Toutes les tentatives ont échoué
                print(f"{wilaya['nom']} : échec après {max_tentatives} tentatives")
                return None


# FONCTION 2 — Sauvegarde DynamoDB

def sauvegarder_dynamodb(wilaya, meteo, now):
    table  = dynamodb.Table(TABLE)
    annee  = str(now.year)
    mois   = str(now.month).zfill(2)
    jour   = str(now.day).zfill(2)
    heure  = str(now.hour).zfill(2)
    ttl    = int(time.time()) + (365 * 24 * 3600)  # expire dans 365 jours

    table.put_item(Item={
        "wilaya_annee":    f"{wilaya['nom']}#{annee}",
        "mois_jour_heure": f"{mois}#{jour}#{heure}",
        "temp_celsius":    str(meteo["temp_celsius"]),
        "humidite_pct":    str(meteo["humidite_pct"]),
        "precipitation_mm":str(meteo["precipitation_mm"]),
        "vent_kmh":        str(meteo["vent_kmh"]),
        "pression_hpa":    str(meteo["pression_hpa"]),
        "condition_meteo": meteo["condition_meteo"],
        "ttl":             ttl,
    })


# FONCTION 3 — Sauvegarde S3

def sauvegarder_s3(wilaya, meteo, now):
    annee = str(now.year)
    mois  = str(now.month).zfill(2)
    jour  = str(now.day).zfill(2)
    heure = str(now.hour).zfill(2)

    fichier = {
        "wilaya":    wilaya["nom"],
        "timestamp": now.isoformat(),
        **meteo
    }
    s3.put_object(
        Bucket = BUCKET,
        Key    = f"raw/{wilaya['nom']}/{annee}-{mois}-{jour}-{heure}.json",
        Body   = json.dumps(fichier),
    )


# FONCTION 4 — Déclencher les autres Lambdas

def declencher_lambda(nom_fonction):
    """
    Déclenche une autre Lambda de façon asynchrone.
    'Event' = on n'attend pas la fin, on continue.
    """
    try:
        lambda_client.invoke(
            FunctionName   = nom_fonction,
            InvocationType = "Event",  # asynchrone = non bloquant
            Payload        = json.dumps({}),
        )
        print(f"{nom_fonction} déclenché automatiquement !")
    except Exception as erreur:
        print(f"Impossible de déclencher {nom_fonction} : {erreur}")


# FONCTION 5 — Envoyer erreur vers DLQ

def signaler_echec_dlq(wilaya_nom, erreur):
    """
    Dead Letter Queue : enregistre les wilayas
    qui ont échoué pour analyse ultérieure.
    """
    try:
        # On publie une métrique d'échec dans CloudWatch
        cw.put_metric_data(
            Namespace  = "P04/Meteo",
            MetricData = [{
                "MetricName": "EchecCollecte",
                "Value":       1,
                "Unit":        "Count",
                "Dimensions": [{"Name": "Wilaya", "Value": wilaya_nom}]
            }]
        )
        print(f"Échec signalé en DLQ pour {wilaya_nom}")
    except Exception as e:
        print(f"Impossible d'écrire en DLQ : {e}")


# HANDLER PRINCIPAL

def lambda_handler(event, context):
    now     = datetime.utcnow()
    succes  = 0
    echecs  = []

    print(f"Début collecte — {now.strftime('%Y-%m-%d %H:%M')} UTC")
    print(f"{'='*50}")

    # Collecte pour chaque wilaya
    for wilaya in WILAYAS:
        print(f"\n{wilaya['nom']} :")

        # Appel API avec retry automatique
        meteo = get_meteo_avec_retry(wilaya, max_tentatives=3)

        if meteo:
            # Sauvegarde DynamoDB + S3
            sauvegarder_dynamodb(wilaya, meteo, now)
            sauvegarder_s3(wilaya, meteo, now)
            succes += 1
            print(f"{wilaya['nom']} : {meteo['temp_celsius']}°C")
        else:
            # Échec même après 3 tentatives → signaler en DLQ
            echecs.append(wilaya["nom"])
            signaler_echec_dlq(wilaya["nom"], "Échec après 3 tentatives")

    print(f"\n{'='*50}")
    print(f"Résultat : {succes}/8 wilayas collectées")

    if echecs:
        print(f"Wilayas en échec : {', '.join(echecs)}")

    # Publier métrique CloudWatch (tâche 35)
    cw.put_metric_data(
        Namespace  = "P04/Meteo",
        MetricData = [{
            "MetricName": "WilayasCollectees",
            "Value":       succes,
            "Unit":        "Count",
        }]
    )
    print(f"Métrique CloudWatch publiée : {succes}/8")

 
    # CHAÎNAGE AUTOMATIQUE 
  
    # Peu importe le résultat, on déclenche les 2 autres Lambdas automatiquement
    print(f"\nDéclenchement automatique des Lambdas suivantes...")
    declencher_lambda(NOM_LAMBDA_TRAITEMENT)
    declencher_lambda(NOM_LAMBDA_DASHBOARD)

    return {
        "statusCode": 200,
        "body": json.dumps({
            "succes": succes,
            "echecs": echecs,
            "message": f"{succes}/8 wilayas collectées"
        })
    }
