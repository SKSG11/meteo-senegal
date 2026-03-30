import json
import boto3
from datetime import datetime, timedelta

# ---- CONFIGURATION ----
TABLE     = "ClimateDaily"
BUCKET    = "p04-meteo-dashboard-2026"  # ← ton vrai nom !

dynamodb = boto3.resource("dynamodb")
s3       = boto3.client("s3")

WILAYAS = [
    {"nom":"Dakar",       "region":"Ouest",  "x":30,  "y":120},
    {"nom":"Thies",       "region":"Ouest",  "x":55,  "y":105},
    {"nom":"SaintLouis",  "region":"Nord",   "x":70,  "y":40 },
    {"nom":"Ziguinchor",  "region":"Sud",    "x":60,  "y":195},
    {"nom":"Tambacounda", "region":"Est",    "x":175, "y":145},
    {"nom":"Kaolack",     "region":"Centre", "x":100, "y":130},
    {"nom":"Louga",       "region":"Nord",   "x":95,  "y":70 },
    {"nom":"Diourbel",    "region":"Centre", "x":85,  "y":115},
]

def get_donnees_wilaya(wilaya):
    """Récupère les 7 derniers jours depuis DynamoDB"""
    table = dynamodb.Table(TABLE)
    now   = datetime.utcnow()
    annee = str(now.year)

    historique = []
    for i in range(6, -1, -1):
        d        = now - timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        try:
            rep  = table.get_item(Key={
                "wilaya_annee": f"{wilaya}#{annee}",
                "date":         date_str,
            })
            item = rep.get("Item", {})
            historique.append({
                "date":     d.strftime("%d/%m"),
                "temp_min": float(item.get("temp_min",     0)),
                "temp_max": float(item.get("temp_max",     0)),
                "temp_moy": float(item.get("temp_moyenne", 0)),
                "pluie":    float(item.get("pluie_totale_mm", 0)),
            })
        except:
            historique.append({
                "date": d.strftime("%d/%m"),
                "temp_min": 0, "temp_max": 0,
                "temp_moy": 0, "pluie": 0,
            })
    return historique

def lambda_handler(event, context):
    now      = datetime.utcnow()
    date_maj = now.strftime("%d/%m/%Y à %H:%M UTC")

    # On récupère les données météo actuelles depuis ClimateData
    table_raw = dynamodb.Table("ClimateData")
    annee     = str(now.year)
    mois      = str(now.month).zfill(2)
    jour      = str(now.day).zfill(2)

    # On construit la liste des wilayas avec données réelles
    wilayas_data = []
    for w in WILAYAS:
        # Cherche la dernière mesure du jour
        try:
            rep = table_raw.query(
                KeyConditionExpression=(
                    boto3.dynamodb.conditions.Key("wilaya_annee")
                    .eq(f"{w['nom']}#{annee}") &
                    boto3.dynamodb.conditions.Key("mois_jour_heure")
                    .begins_with(f"{mois}#{jour}")
                ),
                ScanIndexForward=False,  # dernière mesure en premier
                Limit=1
            )
            item = rep["Items"][0] if rep["Items"] else {}
        except:
            item = {}

        # Historique 7 jours
        historique = get_donnees_wilaya(w["nom"])

        wilayas_data.append({
            "nom":       w["nom"],
            "region":    w["region"],
            "x":         w["x"],
            "y":         w["y"],
            "temp":      float(item.get("temp_celsius",     0)),
            "humidite":  float(item.get("humidite_pct",     0)),
            "pluie":     float(item.get("precipitation_mm", 0)),
            "vent":      float(item.get("vent_kmh",         0)),
            "pression":  float(item.get("pression_hpa",     0)),
            "condition": item.get("condition_meteo", "—"),
            "historique": historique,
        })

        print(f"OK : {w['nom']} → {item.get('temp_celsius','?')}°C")

    # On génère le HTML avec les vraies données
    html = generer_html(wilayas_data, date_maj)

    # On uploade vers S3
    s3.put_object(
        Bucket      = BUCKET,
        Key         = "index.html",
        Body        = html.encode("utf-8"),
        ContentType = "text/html",
    )
    # Invalide le cache CloudFront automatiquement
    cf = boto3.client("cloudfront")
    cf.create_invalidation(
    DistributionId = "E3ISD433A3X6Z8",
    InvalidationBatch = {
        "Paths": {"Quantity": 1, "Items": ["/*"]},
        "CallerReference": str(now.timestamp())
    }
    )
    print(" Cache CloudFront invalidé !")

      

    print(" Dashboard uploadé !")
    return {"statusCode": 200, "body": "Dashboard OK"}


def generer_html(wilayas_data, date_maj):
    """Injecte les vraies données dans le HTML du dashboard"""

    # On convertit les données en JSON pour JavaScript
    data_json = json.dumps(wilayas_data, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Observatoire Climatique — Sénégal</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  *, *::before, *::after {{ margin:0; padding:0; box-sizing:border-box; }}
  :root {{
    --cream:#FAF8F4; --white:#FFFFFF; --ink:#1A1A2E;
    --ink-soft:#4A4A6A; --ink-muted:#8888AA;
    --green:#2D6A4F; --green-light:#E8F5EE;
    --amber:#E07B39; --amber-light:#FDF0E8;
    --blue:#1B4FBF; --blue-light:#EAF0FD;
    --red:#C0392B; --red-light:#FDECEA;
    --border:#E8E4DC;
    --shadow-sm:0 1px 4px rgba(26,26,46,0.06);
    --shadow-md:0 4px 20px rgba(26,26,46,0.08);
    --shadow-lg:0 12px 40px rgba(26,26,46,0.12);
    --radius:16px; --radius-sm:10px;
  }}
  body {{ font-family:'DM Sans',sans-serif; background:var(--cream); color:var(--ink); }}
  header {{
    background:var(--white); border-bottom:1px solid var(--border);
    padding:0 40px; position:sticky; top:0; z-index:100;
    display:flex; align-items:center; justify-content:space-between; height:72px;
  }}
  .logo {{ display:flex; align-items:center; gap:14px; }}
  .logo-icon {{ width:42px; height:42px; border-radius:12px; background:var(--green);
    display:flex; align-items:center; justify-content:center; font-size:20px; }}
  .logo-title {{ font-family:'DM Serif Display',serif; font-size:16px; }}
  .logo-sub {{ font-size:11px; color:var(--ink-muted); }}
  .status-pill {{ display:flex; align-items:center; gap:6px; background:var(--green-light);
    border-radius:99px; padding:6px 14px; font-size:12px; color:var(--green); font-weight:500; }}
  .pulse {{ width:7px; height:7px; border-radius:50%; background:var(--green);
    animation:pulse 2s infinite; }}
  @keyframes pulse {{ 0%,100%{{opacity:1;transform:scale(1)}} 50%{{opacity:0.6;transform:scale(1.3)}} }}
  .btn {{ padding:9px 20px; border-radius:99px; border:none; font-family:'DM Sans',sans-serif;
    font-size:13px; font-weight:500; cursor:pointer; transition:all 0.2s; }}
  .btn-primary {{ background:var(--green); color:white; }}
  .btn-primary:hover {{ background:#235c42; transform:translateY(-1px); }}
  .hero {{ padding:48px 40px 32px; animation:fadeUp 0.6s ease both; }}
  @keyframes fadeUp {{ from{{opacity:0;transform:translateY(20px)}} to{{opacity:1;transform:none}} }}
  .hero h1 {{ font-family:'DM Serif Display',serif; font-size:clamp(28px,4vw,42px); line-height:1.15; margin-bottom:12px; }}
  .hero h1 em {{ color:var(--green); font-style:italic; }}
  .hero p {{ font-size:15px; color:var(--ink-soft); max-width:500px; line-height:1.6; }}
  .stat-strip {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; padding:0 40px 40px; }}
  .stat-card {{ background:var(--white); border-radius:var(--radius); padding:22px 24px;
    border:1px solid var(--border); box-shadow:var(--shadow-sm);
    transition:transform 0.2s,box-shadow 0.2s; }}
  .stat-card:hover {{ transform:translateY(-3px); box-shadow:var(--shadow-md); }}
  .stat-label {{ font-size:11px; color:var(--ink-muted); text-transform:uppercase; letter-spacing:1px; margin-bottom:8px; }}
  .stat-value {{ font-family:'DM Serif Display',serif; font-size:32px; line-height:1; }}
  .stat-unit {{ font-size:13px; color:var(--ink-muted); margin-top:4px; }}
  .stat-badge {{ display:inline-block; padding:3px 10px; border-radius:99px; font-size:11px; font-weight:500; margin-top:8px; }}
  .badge-green {{ background:var(--green-light); color:var(--green); }}
  .badge-amber {{ background:var(--amber-light); color:var(--amber); }}
  .badge-red   {{ background:var(--red-light);   color:var(--red); }}
  .badge-blue  {{ background:var(--blue-light);  color:var(--blue); }}
  .alerts-section {{ padding:0 40px 32px; }}
  .section-label {{ font-size:11px; color:var(--ink-muted); text-transform:uppercase; letter-spacing:1.5px; font-weight:600; margin-bottom:16px; }}
  .alerts-row {{ display:flex; gap:12px; flex-wrap:wrap; }}
  .alert-chip {{ display:flex; align-items:center; gap:8px; padding:10px 16px;
    border-radius:99px; font-size:13px; font-weight:500; border:1px solid; }}
  .alert-chip.ok   {{ background:var(--green-light); color:var(--green); border-color:#b7dfc9; }}
  .alert-chip.warn {{ background:var(--amber-light); color:var(--amber); border-color:#f5c9a0; }}
  .alert-chip.crit {{ background:var(--red-light);   color:var(--red);   border-color:#f0b8b3; }}
  .main-grid {{ display:grid; grid-template-columns:1fr 340px; gap:24px; padding:0 40px 40px; }}
  .wilayas-grid {{ display:grid; grid-template-columns:repeat(2,1fr); gap:16px; }}
  .wilaya-card {{ background:var(--white); border-radius:var(--radius); border:1px solid var(--border);
    box-shadow:var(--shadow-sm); padding:22px; cursor:pointer; transition:all 0.25s; position:relative; overflow:hidden; }}
  .wilaya-card::before {{ content:''; position:absolute; top:0; left:0; width:4px; height:100%;
    background:var(--green); border-radius:4px 0 0 4px; transition:width 0.3s; }}
  .wilaya-card:hover {{ transform:translateY(-4px); box-shadow:var(--shadow-lg); }}
  .wilaya-card.active {{ border-color:var(--green); box-shadow:0 0 0 3px rgba(45,106,79,0.1),var(--shadow-md); }}
  .card-top {{ display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:16px; }}
  .card-name {{ font-size:15px; font-weight:600; }}
  .card-region {{ font-size:11px; color:var(--ink-muted); margin-top:2px; }}
  .card-temp {{ font-family:'DM Serif Display',serif; font-size:36px; line-height:1; }}
  .card-temp span {{ font-size:18px; color:var(--ink-muted); }}
  .card-metrics {{ display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-top:12px; }}
  .metric {{ text-align:center; }}
  .metric-val {{ font-size:13px; font-weight:600; }}
  .metric-lbl {{ font-size:10px; color:var(--ink-muted); }}
  .card-condition {{ margin-top:14px; padding-top:14px; border-top:1px solid var(--border);
    font-size:12px; color:var(--ink-soft); display:flex; align-items:center; justify-content:space-between; }}
  .side-panel {{ display:flex; flex-direction:column; gap:16px; }}
  .panel-card {{ background:var(--white); border-radius:var(--radius); border:1px solid var(--border);
    box-shadow:var(--shadow-sm); padding:24px; overflow:hidden; }}
  .panel-title {{ font-family:'DM Serif Display',serif; font-size:18px; margin-bottom:4px; }}
  .panel-sub {{ font-size:12px; color:var(--ink-muted); margin-bottom:20px; }}
  .senegal-map {{ position:relative; background:var(--cream); border-radius:var(--radius-sm); padding:16px; }}
  .map-tooltip {{ position:absolute; background:var(--ink); color:white; padding:6px 12px;
    border-radius:8px; font-size:12px; pointer-events:none; opacity:0; transition:opacity 0.2s;
    white-space:nowrap; z-index:10; }}
  .chart-tabs {{ display:flex; gap:4px; margin-bottom:16px; }}
  .tab {{ padding:6px 14px; border-radius:99px; font-size:12px; font-weight:500; cursor:pointer;
    border:1px solid var(--border); background:transparent; color:var(--ink-muted);
    transition:all 0.2s; font-family:'DM Sans',sans-serif; }}
  .tab.active {{ background:var(--ink); color:white; border-color:var(--ink); }}
  footer {{ text-align:center; padding:32px 40px; border-top:1px solid var(--border);
    font-size:12px; color:var(--ink-muted); }}
  .modal-overlay {{ position:fixed; inset:0; background:rgba(26,26,46,0.4);
    backdrop-filter:blur(4px); z-index:200; display:none; align-items:center; justify-content:center; }}
  .modal-overlay.open {{ display:flex; }}
  .modal {{ background:var(--white); border-radius:24px; padding:32px; width:min(600px,90vw);
    box-shadow:var(--shadow-lg); max-height:80vh; overflow-y:auto; }}
  .modal-header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:24px; }}
  .modal-close {{ background:none; border:none; font-size:20px; cursor:pointer; color:var(--ink-muted); }}
  @media(max-width:900px){{
    header,.hero,.stat-strip,.alerts-section,.main-grid{{padding-left:20px;padding-right:20px}}
    .stat-strip{{grid-template-columns:repeat(2,1fr)}}
    .main-grid{{grid-template-columns:1fr}}
    .wilayas-grid{{grid-template-columns:1fr}}
  }}
</style>
</head>
<body>

<header>
  <div class="logo">
    <div class="logo-icon">🌍</div>
    <div>
      <div class="logo-title">CLIMATE</div>
      <div class="logo-sub">Observatoire climatique pour la sécurité alimentaire</div>
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:16px">
    <div class="status-pill"><div class="pulse"></div>Système actif</div>
    <span style="font-size:12px;color:var(--ink-muted)">{date_maj}</span>
    <button class="btn btn-primary" onclick="exportCSV()">↓ Exporter CSV</button>
  </div>
</header>

<section class="hero">
  <h1>Surveillance météo<br><em>multi-wilayas</em> en temps réel</h1>
  <p>Données collectées automatiquement toutes les 3h. <br>8 wilayas surveillées pour anticiper les risques alimentaires.</p>
</section>

<section class="stat-strip" id="stat-strip"></section>

<section class="alerts-section">
  <div class="section-label">Alertes en cours</div>
  <div class="alerts-row" id="alerts-row"></div>
</section>

<div class="main-grid">
  <div>
    <div class="section-label" style="margin-bottom:16px">Données par wilaya — Région</div>
    <div class="wilayas-grid" id="wilayas-grid"></div>
  </div>
  <div class="side-panel">
    <div class="panel-card">
      <div class="panel-title">Carte du Sénégal</div>
      <div class="panel-sub">Cliquer sur une wilaya</div>
      <div class="senegal-map" id="map-container">
        <svg style="width:100%;height:auto" viewBox="0 0 280 260">
          <path d="M40,30 L60,20 L100,15 L140,18 L180,22 L220,30 L250,50 L260,80 L255,110 L240,140 L220,160 L200,175 L180,185 L160,195 L140,210 L120,220 L100,215 L80,205 L60,190 L45,175 L30,155 L20,130 L15,100 L20,70 L30,45 Z"
            fill="#E8F5EE" stroke="#2D6A4F" stroke-width="1.5"/>
          <g id="map-dots"></g>
        </svg>
        <div class="map-tooltip" id="map-tooltip"></div>
      </div>
    </div>
    <div class="panel-card">
      <div class="panel-title" id="chart-title">Sélectionner une wilaya</div>
      <div class="panel-sub">7 derniers jours</div>
      <div class="chart-tabs">
        <button class="tab active" onclick="switchChart('temp',this)">Température</button>
        <button class="tab" onclick="switchChart('pluie',this)">Pluie</button>
      </div>
      <canvas id="main-chart" height="180"></canvas>
    </div>
  </div>
</div>

<div class="modal-overlay" id="modal">
  <div class="modal">
    <div class="modal-header">
      <div>
        <div class="panel-title" id="modal-title"></div>
        <div style="font-size:12px;color:var(--ink-muted)" id="modal-sub"></div>
      </div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div id="modal-content"></div>
    <canvas id="modal-chart" height="160" style="margin-top:20px"></canvas>
  </div>
</div>

<footer>
  <strong>Projet P-04 — ISI Dakar</strong> · 2025–2026 · OpenWeatherMap API
</footer>

<script>
// ══ DONNÉES RÉELLES depuis DynamoDB ══
const DATA = {data_json};

let selected = null;
let chartMode = 'temp';
let mainChart = null;
let modalChart = null;

function tempColor(t) {{
  if(t<25) return '#1B4FBF';
  if(t<32) return '#2D6A4F';
  if(t<38) return '#E07B39';
  return '#C0392B';
}}

function init() {{
  updateStats();
  updateAlerts();
  renderCards();
  renderMap();
  if(DATA.length>0) selectWilaya(DATA[0]);
}}

function updateStats() {{
  const temps = DATA.map(w=>w.temp).filter(t=>t>0);
  const moy   = temps.length ? (temps.reduce((a,b)=>a+b,0)/temps.length).toFixed(1) : '—';
  const max   = temps.length ? Math.max(...temps) : 0;
  const maxW  = DATA.find(w=>w.temp===max) || DATA[0];
  const pluies= DATA.map(w=>w.pluie);
  const maxP  = Math.max(...pluies);
  const maxPW = DATA.find(w=>w.pluie===maxP) || DATA[0];

  document.getElementById('stat-strip').innerHTML = `
    <div class="stat-card">
      <div class="stat-label">Wilayas actives</div>
      <div class="stat-value">8</div>
      <div class="stat-unit">sur 8 surveillées</div>
      <span class="stat-badge badge-green">✓ Opérationnel</span>
    </div>
    <div class="stat-card">
      <div class="stat-label">Température moyenne</div>
      <div class="stat-value">${{moy}}</div>
      <div class="stat-unit">°C · aujourd'hui</div>
      <span class="stat-badge badge-amber">${{parseFloat(moy)>35?'⚠ Chaleur':'✓ Normale'}}</span>
    </div>
    <div class="stat-card">
      <div class="stat-label">Wilaya la plus chaude</div>
      <div class="stat-value" style="color:${{tempColor(max)}}">${{max}}°</div>
      <div class="stat-unit">${{maxW.nom}}</div>
      <span class="stat-badge badge-red">⚠ Surveiller</span>
    </div>
    <div class="stat-card">
      <div class="stat-label">Précipitations max</div>
      <div class="stat-value">${{maxP}}</div>
      <div class="stat-unit">mm · ${{maxPW.nom}}</div>
      <span class="stat-badge badge-blue">💧 Hydrique</span>
    </div>`;
}}

function updateAlerts() {{
  const row = document.getElementById('alerts-row');
  const chips = [];
  DATA.forEach(w => {{
    if(w.temp>40) chips.push(`<div class="alert-chip crit">🌡️ ${{w.nom}} > 40°C</div>`);
    if(w.pluie>10) chips.push(`<div class="alert-chip warn">💧 Fortes pluies · ${{w.nom}}</div>`);
  }});
  if(!chips.length) chips.push('<div class="alert-chip ok">✓ Toutes les wilayas dans les normes</div>');
  chips.push('<div class="alert-chip ok">✓ Collecte 8/8 réussie</div>');
  row.innerHTML = chips.join('');
}}

function renderCards() {{
  document.getElementById('wilayas-grid').innerHTML = DATA.map((w,i) => `
    <div class="wilaya-card" id="card-${{w.nom}}" onclick="selectWilaya(DATA[${{i}}])"
         ondblclick="openModal(DATA[${{i}}])"
         style="animation:fadeUp 0.5s ease ${{i*0.06}}s both">
      <div class="card-top">
        <div>
          <div class="card-name">${{w.nom}}</div>
          <div class="card-region">${{w.region}} · ${{w.condition}}</div>
        </div>
        <div class="card-temp" style="color:${{tempColor(w.temp)}}">${{w.temp}}<span>°C</span></div>
      </div>
      <div class="card-metrics">
        <div class="metric"><div>💧</div><div class="metric-val">${{w.humidite}}%</div><div class="metric-lbl">Humidité</div></div>
        <div class="metric"><div>🌧️</div><div class="metric-val">${{w.pluie}}mm</div><div class="metric-lbl">Pluie</div></div>
        <div class="metric"><div>💨</div><div class="metric-val">${{w.vent}}km/h</div><div class="metric-lbl">Vent</div></div>
      </div>
      <div class="card-condition">
        <span>Pression : ${{w.pression}} hPa</span>
        ${{w.temp>38?'<span style="color:var(--red);font-weight:600">⚠ Chaleur critique</span>':
          w.pluie>8?'<span style="color:var(--blue);font-weight:600">⚠ Fortes pluies</span>':
          '<span style="color:var(--green)">✓ Normal</span>'}}
      </div>
    </div>`).join('');
}}

function renderMap() {{
  document.getElementById('map-dots').innerHTML = DATA.map((w,i) => `
    <g style="cursor:pointer" onclick="selectWilaya(DATA[${{i}}])"
       onmouseenter="showTip(event,'${{w.nom}}',w.temp)"
       onmouseleave="hideTip()">
      <circle cx="${{w.x}}" cy="${{w.y}}" r="6" fill="${{tempColor(w.temp)}}" opacity="0.85" id="dot-${{w.nom}}"/>
      <text x="${{w.x}}" y="${{w.y-10}}" text-anchor="middle"
            font-family="DM Sans,sans-serif" font-size="8" fill="#1A1A2E" font-weight="500">
        ${{w.nom}}
      </text>
    </g>`).join('');
}}

function showTip(e,nom,temp){{
  const t=document.getElementById('map-tooltip');
  t.textContent=nom+' · '+temp+'°C';
  t.style.opacity='1';
  t.style.left=(e.offsetX+10)+'px';
  t.style.top=(e.offsetY-30)+'px';
}}
function hideTip(){{ document.getElementById('map-tooltip').style.opacity='0'; }}

function selectWilaya(w) {{
  selected=w;
  document.querySelectorAll('.wilaya-card').forEach(c=>c.classList.remove('active'));
  const card=document.getElementById('card-'+w.nom);
  if(card){{ card.classList.add('active'); card.scrollIntoView({{behavior:'smooth',block:'nearest'}}); }}
  document.getElementById('chart-title').textContent=w.nom;
  renderChart(w);
}}

function switchChart(mode,el) {{
  chartMode=mode;
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  if(selected) renderChart(selected);
}}

function renderChart(w) {{
  const ctx=document.getElementById('main-chart').getContext('2d');
  if(mainChart) mainChart.destroy();
  const labels=w.historique.map(h=>h.date);
  const datasets=chartMode==='temp'?[
    {{label:'Max °C',data:w.historique.map(h=>h.temp_max),borderColor:'#C0392B',tension:0.4,fill:false,pointRadius:4}},
    {{label:'Moy °C',data:w.historique.map(h=>h.temp_moy),borderColor:'#E07B39',tension:0.4,fill:false,pointRadius:4}},
    {{label:'Min °C',data:w.historique.map(h=>h.temp_min),borderColor:'#1B4FBF',tension:0.4,fill:false,pointRadius:4}},
  ]:[
    {{label:'Pluie mm',data:w.historique.map(h=>h.pluie),backgroundColor:'rgba(27,79,191,0.5)',borderColor:'#1B4FBF',borderRadius:6,type:'bar'}},
  ];
  mainChart=new Chart(ctx,{{
    type:'line',data:{{labels,datasets}},
    options:{{responsive:true,
      plugins:{{legend:{{labels:{{font:{{family:'DM Sans',size:11}},boxWidth:12}}}}}},
      scales:{{x:{{grid:{{color:'rgba(0,0,0,0.04)'}},ticks:{{font:{{family:'DM Sans',size:10}}}}}},
               y:{{grid:{{color:'rgba(0,0,0,0.04)'}},ticks:{{font:{{family:'DM Sans',size:10}}}}}}}}}}
  }});
}}

function openModal(w) {{
  document.getElementById('modal-title').textContent=w.nom;
  document.getElementById('modal-sub').textContent='Région '+w.region+' · '+w.condition;
  document.getElementById('modal-content').innerHTML=`
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px">
      ${{[['🌡️','Température',w.temp+'°C'],['💧','Humidité',w.humidite+'%'],
          ['🌧️','Précipitations',w.pluie+' mm'],['💨','Vent',w.vent+' km/h'],
          ['🔵','Pression',w.pression+' hPa'],['☁️','Condition',w.condition]]
        .map(([icon,lbl,val])=>`
          <div style="background:var(--cream);border-radius:12px;padding:14px;text-align:center">
            <div style="font-size:20px;margin-bottom:4px">${{icon}}</div>
            <div style="font-size:18px;font-weight:600">${{val}}</div>
            <div style="font-size:11px;color:var(--ink-muted)">${{lbl}}</div>
          </div>`).join('')}}
    </div>`;
  const ctx=document.getElementById('modal-chart').getContext('2d');
  if(modalChart) modalChart.destroy();
  modalChart=new Chart(ctx,{{
    type:'line',
    data:{{labels:w.historique.map(h=>h.date),datasets:[
      {{label:'Max',data:w.historique.map(h=>h.temp_max),borderColor:'#C0392B',tension:0.4,fill:false}},
      {{label:'Moy',data:w.historique.map(h=>h.temp_moy),borderColor:'#E07B39',tension:0.4,fill:false}},
      {{label:'Min',data:w.historique.map(h=>h.temp_min),borderColor:'#1B4FBF',tension:0.4,fill:false}},
    ]}},
    options:{{responsive:true,plugins:{{legend:{{labels:{{font:{{family:'DM Sans',size:11}},boxWidth:12}}}}}},
      scales:{{x:{{ticks:{{font:{{family:'DM Sans',size:10}}}}}},y:{{ticks:{{font:{{family:'DM Sans',size:10}}}}}}}}}}
  }});
  document.getElementById('modal').classList.add('open');
}}

function closeModal() {{ document.getElementById('modal').classList.remove('open'); }}
document.getElementById('modal').addEventListener('click',e=>{{ if(e.target===document.getElementById('modal')) closeModal(); }});

function exportCSV() {{
  let csv='Wilaya,Région,Temp(°C),Humidité(%),Pluie(mm),Vent(km/h),Pression(hPa),Condition\\n';
  DATA.forEach(w=>{{ csv+=`${{w.nom}},${{w.region}},${{w.temp}},${{w.humidite}},${{w.pluie}},${{w.vent}},${{w.pression}},"${{w.condition}}"\\n`; }});
  const a=document.createElement('a');
  a.href='data:text/csv;charset=utf-8,'+encodeURIComponent(csv);
  a.download='meteo_senegal_'+new Date().toISOString().slice(0,10)+'.csv';
  a.click();
}}

init();
</script>
</body>
</html>"""
