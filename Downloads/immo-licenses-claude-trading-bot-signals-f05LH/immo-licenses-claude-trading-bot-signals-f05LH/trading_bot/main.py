import json
import threading
import time
import socket
from datetime import datetime
from typing import Any, TypedDict
from flask import Flask, Response, jsonify, render_template_string

from config import STOCKS, CRYPTO, CHECK_INTERVAL_MINUTES, WEB_PORT, MODE
from data_fetcher import fetch_stock, fetch_crypto
from signal_engine import analyze
from alerts import send_signal, event_queue

# ─── État global ──────────────────────────────────────────────────────────────
class BotState(TypedDict):
    paused: bool
    last_scan: datetime | None
    signals_today: int
    sent_keys: set[str]
    log: list[str]
    signal_history: list[dict[str, Any]]

state: BotState = {
    "paused": False,
    "last_scan": None,
    "signals_today": 0,
    "sent_keys": set(),
    "log": [],
    "signal_history": [],
}


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    print(entry)
    state["log"].insert(0, entry)
    if len(state["log"]) > 100:
        state["log"].pop()


# ─── Scan principal ───────────────────────────────────────────────────────────

def run_scan(triggered_by: str = "auto") -> int:
    now = datetime.now()
    state["last_scan"] = now
    found = 0
    log(f"Scan ({triggered_by}) démarré…")

    for ticker in STOCKS:
        df = fetch_stock(ticker)
        if df is None:
            continue
        signal = analyze(ticker, df, "stock")
        if signal:
            key = f"{ticker}-{signal.action}-{now.date()}"
            if key not in state["sent_keys"]:
                send_signal(signal)
                state["sent_keys"].add(key)
                state["signals_today"] += 1
                state["signal_history"].insert(0, {
                    "asset": signal.asset.upper(),
                    "asset_type": signal.asset_type,
                    "action": signal.action,
                    "price": round(signal.price, 2),
                    "rsi": round(signal.rsi, 1),
                    "strength": signal.strength,
                    "reasons": signal.reasons,
                    "ts": now.strftime("%d/%m %H:%M"),
                })
                found += 1

    for coin in CRYPTO:
        df = fetch_crypto(coin)
        if df is None:
            continue
        signal = analyze(coin, df, "crypto")
        if signal:
            key = f"{coin}-{signal.action}-{now.date()}"
            if key not in state["sent_keys"]:
                send_signal(signal)
                state["sent_keys"].add(key)
                state["signals_today"] += 1
                state["signal_history"].insert(0, {
                    "asset": signal.asset.upper(),
                    "asset_type": signal.asset_type,
                    "action": signal.action,
                    "price": round(signal.price, 2),
                    "rsi": round(signal.rsi, 1),
                    "strength": signal.strength,
                    "reasons": signal.reasons,
                    "ts": now.strftime("%d/%m %H:%M"),
                })
                found += 1

    log(f"Scan terminé — {found} signal(s).")
    return found


def scheduler_thread() -> None:
    while True:
        time.sleep(CHECK_INTERVAL_MINUTES * 60)
        if not state["paused"]:
            run_scan("auto")


# ─── Interface web ────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Trading Bot — Dashboard</title>
<style>
  :root{--bg:#0d1117;--card:#161b22;--border:#30363d;--text:#e6edf3;--muted:#8b949e;
        --green:#3fb950;--green-bg:#1a2d1a;--red:#f85149;--red-bg:#2d1a1a;
        --blue:#58a6ff;--yellow:#d29922;--purple:#bc8cff}
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:14px}
  header{background:var(--card);border-bottom:1px solid var(--border);padding:14px 24px;
         display:flex;align-items:center;gap:12px;position:sticky;top:0;z-index:10}
  header h1{font-size:1.1rem;font-weight:600}
  .dot{width:8px;height:8px;border-radius:50%;background:var(--green);animation:pulse 2s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
  .dot.paused{background:var(--yellow);animation:none}
  .badge{padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;text-transform:uppercase}
  .badge-green{background:var(--green-bg);color:var(--green)}
  .badge-red{background:var(--red-bg);color:var(--red)}
  .badge-yellow{background:#2d2100;color:var(--yellow)}
  main{max-width:1200px;margin:0 auto;padding:20px 16px;display:grid;
       grid-template-columns:320px 1fr;gap:16px}
  @media(max-width:800px){main{grid-template-columns:1fr}}
  .card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:16px}
  .card-title{font-size:12px;font-weight:600;color:var(--muted);text-transform:uppercase;
              letter-spacing:.05em;margin-bottom:12px}
  .stat-row{display:flex;justify-content:space-between;align-items:center;
            padding:8px 0;border-bottom:1px solid var(--border)}
  .stat-row:last-child{border:none}
  .stat-label{color:var(--muted)}
  .stat-value{font-weight:600}
  .btn{border:none;border-radius:6px;padding:9px 16px;font-size:13px;font-weight:600;
       cursor:pointer;transition:opacity .15s}
  .btn:hover{opacity:.85}
  .btn-primary{background:var(--blue);color:#0d1117}
  .btn-warning{background:var(--yellow);color:#0d1117}
  .btn-success{background:var(--green);color:#0d1117}
  .btn-full{display:block;width:100%;margin-bottom:8px}
  .signal-card{border-radius:8px;padding:14px;margin-bottom:10px;
               border-left:3px solid;animation:slidein .3s ease}
  @keyframes slidein{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:none}}
  .signal-buy{background:var(--green-bg);border-color:var(--green)}
  .signal-sell{background:var(--red-bg);border-color:var(--red)}
  .signal-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
  .signal-asset{font-weight:700;font-size:1rem}
  .signal-meta{font-size:12px;color:var(--muted);margin-top:4px}
  .signal-reasons{font-size:12px;color:var(--muted);margin-top:6px;padding-top:6px;
                  border-top:1px solid var(--border)}
  .strength-dots{display:flex;gap:4px;align-items:center}
  .dot-s{width:6px;height:6px;border-radius:50%}
  .log-entry{font-family:monospace;font-size:12px;color:var(--muted);padding:3px 0;
             border-bottom:1px solid var(--border)}
  .log-entry:last-child{border:none}
  .empty-state{text-align:center;color:var(--muted);padding:40px 0;font-size:13px}
  #notif-bar{display:none;background:#1c2128;border:1px solid var(--border);border-radius:6px;
             padding:10px 14px;margin-bottom:16px;font-size:13px;align-items:center;gap:10px}
  #notif-bar button{margin-left:auto}
  .watchlist-item{display:flex;justify-content:space-between;padding:6px 0;
                  border-bottom:1px solid var(--border);font-size:13px}
  .watchlist-item:last-child{border:none}
  .section-title{font-size:11px;color:var(--muted);font-weight:600;
                 text-transform:uppercase;margin:10px 0 4px}
</style>
</head>
<body>

<header>
  <span class="dot" id="status-dot"></span>
  <h1>Trading Bot</h1>
  <span style="color:var(--muted);font-size:12px">Revolut Signal Alerts</span>
  <span id="header-badge" class="badge badge-green" style="margin-left:auto">Actif</span>
</header>

<main>
  <!-- Colonne gauche -->
  <aside>
    <!-- Statut -->
    <div class="card" style="margin-bottom:16px">
      <div class="card-title">Statut</div>
      <div class="stat-row">
        <span class="stat-label">Dernier scan</span>
        <span class="stat-value" id="last-scan">—</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">Signaux aujourd'hui</span>
        <span class="stat-value" id="signals-today">0</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">Intervalle</span>
        <span class="stat-value">{{ interval }} min</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">Mode</span>
        <span class="stat-value">{{ mode }}</span>
      </div>
    </div>

    <!-- Actions -->
    <div class="card" style="margin-bottom:16px">
      <div class="card-title">Contrôles</div>
      <button class="btn btn-primary btn-full" id="scan-btn" onclick="doScan()">
        🔍 Scanner maintenant
      </button>
      <button class="btn btn-warning btn-full" id="pause-btn" onclick="togglePause()">
        ⏸ Mettre en pause
      </button>
    </div>

    <!-- Watchlist -->
    <div class="card" style="margin-bottom:16px">
      <div class="card-title">Actifs surveillés</div>
      <div class="section-title">Actions</div>
      {% for s in stocks %}
      <div class="watchlist-item"><span>{{ s }}</span></div>
      {% endfor %}
      <div class="section-title" style="margin-top:8px">Crypto</div>
      {% for c in crypto %}
      <div class="watchlist-item"><span>{{ c }}</span></div>
      {% endfor %}
    </div>

    <!-- Journal -->
    <div class="card">
      <div class="card-title">Journal</div>
      <div id="log-container">
        <div class="empty-state">En attente du premier scan…</div>
      </div>
    </div>
  </aside>

  <!-- Colonne droite -->
  <section>
    <div id="notif-bar">
      <span>🔔 Active les notifications desktop pour ne rien manquer</span>
      <button class="btn btn-primary" onclick="requestNotif()">Activer</button>
    </div>

    <div class="card">
      <div class="card-title" style="display:flex;justify-content:space-between">
        <span>Signaux</span>
        <span id="signal-count" style="color:var(--muted);font-weight:400">0 signal(s)</span>
      </div>
      <div id="signals-container">
        <div class="empty-state">
          Aucun signal pour le moment.<br>
          Lance un scan ou attends le prochain cycle automatique.
        </div>
      </div>
    </div>
  </section>
</main>

<script>
let paused = false;
let signalCount = 0;
const signals = [];

// ── Notifications desktop ──────────────────────────────────────────────────
function requestNotif() {
  Notification.requestPermission().then(p => {
    if (p === 'granted') document.getElementById('notif-bar').style.display = 'none';
  });
}

function notify(title, body) {
  if (Notification.permission === 'granted') {
    new Notification(title, { body, icon: '' });
  }
}

// Affiche la barre si les notifs ne sont pas encore accordées
if (Notification.permission === 'default') {
  document.getElementById('notif-bar').style.display = 'flex';
}

// ── SSE — réception des événements en temps réel ────────────────────────────
const sse = new EventSource('/api/stream');

sse.addEventListener('signal', e => {
  const s = JSON.parse(e.data);
  signals.unshift(s);
  signalCount++;
  renderSignal(s);
  document.getElementById('signal-count').textContent = `${signalCount} signal(s)`;
  const label = s.action === 'ACHAT' ? '🟢 ACHAT' : '🔴 VENTE';
  notify(`${label} — ${s.asset}`, `Prix: ${s.price.toLocaleString('fr')} € | RSI: ${s.rsi} | ${s.strength_label}`);
});

sse.addEventListener('log', e => {
  const d = JSON.parse(e.data);
  addLog(d.text, d.ts);
});

sse.addEventListener('status', e => {
  const d = JSON.parse(e.data);
  updateStatus(d);
});

// ── Rendu des signaux ─────────────────────────────────────────────────────
function renderSignal(s) {
  const container = document.getElementById('signals-container');
  const empty = container.querySelector('.empty-state');
  if (empty) empty.remove();

  const isBuy = s.action === 'ACHAT';
  const cls = isBuy ? 'signal-buy' : 'signal-sell';
  const emoji = isBuy ? '🟢' : '🔴';
  const color = isBuy ? 'var(--green)' : 'var(--red)';
  const dots = [1,2,3].map(i =>
    `<span class="dot-s" style="background:${i<=s.strength?color:'var(--border)'}"></span>`
  ).join('');
  const reasons = s.reasons.map(r => `• ${r}`).join('<br>');

  const div = document.createElement('div');
  div.className = `signal-card ${cls}`;
  div.innerHTML = `
    <div class="signal-header">
      <span class="signal-asset">${emoji} ${s.asset}</span>
      <span class="badge ${isBuy?'badge-green':'badge-red'}">${s.action}</span>
    </div>
    <div style="display:flex;justify-content:space-between;align-items:center">
      <span style="font-size:1.1rem;font-weight:700">${s.price.toLocaleString('fr-FR',{minimumFractionDigits:2})} €</span>
      <div class="strength-dots" title="Force: ${s.strength_label}">${dots}</div>
    </div>
    <div class="signal-meta">
      ${s.asset_type === 'stock' ? '📈 Action' : '🪙 Crypto'} &nbsp;·&nbsp;
      RSI ${s.rsi} &nbsp;·&nbsp; ${s.ts}
    </div>
    <div class="signal-reasons">${reasons}</div>
  `;
  container.prepend(div);
}

function addLog(text, ts) {
  const container = document.getElementById('log-container');
  const empty = container.querySelector('.empty-state');
  if (empty) empty.remove();
  const div = document.createElement('div');
  div.className = 'log-entry';
  div.textContent = `[${ts}] ${text}`;
  container.prepend(div);
  // Garde max 30 entrées
  while (container.children.length > 30) container.lastChild.remove();
}

function updateStatus(d) {
  paused = d.paused;
  document.getElementById('last-scan').textContent = d.last_scan || '—';
  document.getElementById('signals-today').textContent = d.signals_today;
  const dot = document.getElementById('status-dot');
  const badge = document.getElementById('header-badge');
  const btn = document.getElementById('pause-btn');
  if (paused) {
    dot.className = 'dot paused';
    badge.textContent = 'En pause'; badge.className = 'badge badge-yellow';
    btn.textContent = '▶️ Reprendre'; btn.className = 'btn btn-success btn-full';
  } else {
    dot.className = 'dot';
    badge.textContent = 'Actif'; badge.className = 'badge badge-green';
    btn.textContent = '⏸ Mettre en pause'; btn.className = 'btn btn-warning btn-full';
  }
}

// ── Actions ────────────────────────────────────────────────────────────────
async function doScan() {
  const btn = document.getElementById('scan-btn');
  btn.textContent = '⏳ Scan en cours…'; btn.disabled = true;
  await fetch('/api/scan', {method:'POST'});
  setTimeout(() => { btn.textContent = '🔍 Scanner maintenant'; btn.disabled = false; }, 3000);
}

async function togglePause() {
  await fetch(paused ? '/api/resume' : '/api/pause', {method:'POST'});
}

// Sync status toutes les 10s (fallback si SSE rate quelque chose)
setInterval(async () => {
  const d = await (await fetch('/api/status')).json();
  updateStatus(d);
}, 10000);
</script>
</body>
</html>
"""

flask_app = Flask(__name__)


# ── SSE — stream d'événements vers le navigateur ───────────────────────────────

def event_stream():
    while True:
        try:
            data = event_queue.get(timeout=25)
            yield f"event: {data['type']}\ndata: {json.dumps(data)}\n\n"
        except Exception:
            yield "event: ping\ndata: {}\n\n"  # keepalive


@flask_app.route("/api/stream")
def api_stream():
    return Response(event_stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── API REST ───────────────────────────────────────────────────────────────────

@flask_app.route("/")
def index():
    return render_template_string(
        HTML,
        interval=CHECK_INTERVAL_MINUTES,
        mode="PC (interface)" if MODE == "pc" else "PC + WhatsApp",
        stocks=STOCKS,
        crypto=[c.capitalize() for c in CRYPTO],
    )


@flask_app.route("/api/status")
def api_status():
    last = state["last_scan"].strftime("%H:%M:%S") if state["last_scan"] else None
    return jsonify({"paused": state["paused"], "last_scan": last,
                    "signals_today": state["signals_today"]})


@flask_app.route("/api/scan", methods=["POST"])
def api_scan():
    threading.Thread(target=run_scan, args=("manuel",), daemon=True).start()
    return jsonify({"ok": True})


@flask_app.route("/api/pause", methods=["POST"])
def api_pause():
    state["paused"] = True
    log("Scans automatiques mis en pause.")
    event_queue.put_nowait({"type": "status", "paused": True,
                            "last_scan": None, "signals_today": state["signals_today"]})
    return jsonify({"ok": True})


@flask_app.route("/api/resume", methods=["POST"])
def api_resume():
    state["paused"] = False
    log("Scans automatiques repris.")
    event_queue.put_nowait({"type": "status", "paused": False,
                            "last_scan": None, "signals_today": state["signals_today"]})
    return jsonify({"ok": True})


# ── Point d'entrée ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import webbrowser
    ip = socket.gethostbyname(socket.gethostname())
    url = f"http://localhost:{WEB_PORT}"

    threading.Thread(target=run_scan, args=("démarrage",), daemon=True).start()
    threading.Thread(target=scheduler_thread, daemon=True).start()

    print(f"\n  Dashboard → {url}\n")
    # Ouvre le navigateur automatiquement
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    flask_app.run(host="0.0.0.0", port=WEB_PORT, debug=False)
