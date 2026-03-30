import json
import boto3
from datetime import datetime, timezone
from decimal import Decimal

REGION        = "us-east-1"
TABLE_SOURCE  = "ClimateData"
TABLE_DEST    = "ClimateDaily"

dynamodb = boto3.resource("dynamodb", region_name=REGION)

WILAYAS = [
    "Dakar", "Thies", "SaintLouis", "Ziguinchor",
    "Tambacounda", "Kaolack", "Louga", "Diourbel"
]

def get_donnees_jour(wilaya, date_str):
    """Récupère toutes les mesures d'une wilaya pour aujourd'hui"""
    table  = dynamodb.Table(TABLE_SOURCE)
    annee  = date_str[:4]
    mois   = date_str[5:7]
    jour   = date_str[8:10]

    response = table.query(
        KeyConditionExpression=(
            boto3.dynamodb.conditions.Key("wilaya_annee")
            .eq(f"{wilaya}#{annee}") &
            boto3.dynamodb.conditions.Key("mois_jour_heure")
            .begins_with(f"{mois}#{jour}")
        )
    )
    return response.get("Items", [])

def calculer_agregats(items):
    """Calcule min/max/moyenne sur les mesures du jour"""
    if not items:
        return None

    temps  = [float(i["temp_celsius"])     for i in items]
    pluies = [float(i["precipitation_mm"]) for i in items]
    vents  = [float(i["vent_kmh"])         for i in items]

    return {
        "temp_min":        round(min(temps),  2),
        "temp_max":        round(max(temps),  2),
        "temp_moyenne":    round(sum(temps)  / len(temps),  2),
        "pluie_totale_mm": round(sum(pluies), 2),
        "vent_moyen_kmh":  round(sum(vents)  / len(vents),  2),
        "nb_mesures":      len(items),
    }

def sauvegarder_daily(wilaya, date_str, agregats):
    """Sauvegarde les agrégats dans ClimateDaily"""
    table = dynamodb.Table(TABLE_DEST)
    annee = date_str[:4]

    table.put_item(Item={
        "wilaya_annee": f"{wilaya}#{annee}",
        "date":         date_str,
        "temp_min":     str(agregats["temp_min"]),
        "temp_max":     str(agregats["temp_max"]),
        "temp_moyenne": str(agregats["temp_moyenne"]),
        "pluie_totale_mm": str(agregats["pluie_totale_mm"]),
        "vent_moyen_kmh":  str(agregats["vent_moyen_kmh"]),
        "nb_mesures":      agregats["nb_mesures"],
    })

def lambda_handler(event, context):
    now      = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    succes   = 0

    for wilaya in WILAYAS:
        items = get_donnees_jour(wilaya, date_str)
        if items:
            agregats = calculer_agregats(items)
            if agregats:
                sauvegarder_daily(wilaya, date_str, agregats)
                succes += 1
                print(
                    f" {wilaya} :"
                    f"min:{agregats['temp_min']}°C "
                    f"max:{agregats['temp_max']}°C "
                    f"moy:{agregats['temp_moyenne']}°C"
                )
        else:
            print(f"{wilaya} : pas de données aujourd'hui")

    print(f"\n{succes}/8 wilayas traitées")
    return {
        "statusCode": 200,
        "body": json.dumps(f"{succes}/8 wilayas traitées"),
    }
