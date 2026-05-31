import threading
import socket
from datetime import datetime
from typing import TypedDict
from flask import Flask, jsonify, render_template_string

from config import STOCKS, CRYPTO, CHECK_INTERVAL_MINUTES, WEB_PORT
from data_fetcher import fetch_stock, fetch_crypto
from signal_engine import analyze
from alerts import send_signal, send_message

# ─── État global ──────────────────────────────────────────────────────────────
class BotState(TypedDict):
    paused: bool
    last_scan: datetime | None
    signals_today: int
    sent_keys: set[str]
    log: list[str]

state: BotState = {
    "paused": False,
    "last_scan": None,
    "signals_today": 0,
    "sent_keys": set(),
    "log": [],
}


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    print(entry)
    state["log"].insert(0, entry)
    if len(state["log"]) > 50:
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
                found += 1

    log(f"Scan terminé — {found} signal(s).")
    return found


# ─── Boucle automatique (thread séparé) ──────────────────────────────────────

def scheduler_thread():
    import time
    while True:
        time.sleep(CHECK_INTERVAL_MINUTES * 60)
        if not state["paused"]:
            run_scan("auto")


# ─── Interface web ────────────────────────────────────────────────────────────

HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Trading Bot</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:-apple-system,sans-serif;background:#0f172a;color:#e2e8f0;padding:20px}
    h1{font-size:1.4rem;margin-bottom:4px}
    .sub{color:#94a3b8;font-size:.85rem;margin-bottom:24px}
    .card{background:#1e293b;border-radius:12px;padding:16px;margin-bottom:16px}
    .badge{display:inline-block;padding:4px 10px;border-radius:20px;font-size:.8rem;font-weight:600}
    .green{background:#166534;color:#86efac}.red{background:#7f1d1d;color:#fca5a5}
    .stat{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #334155}
    .stat:last-child{border:none}
    .label{color:#94a3b8;font-size:.9rem}.value{font-weight:600}
    .btn{display:block;width:100%;padding:14px;border:none;border-radius:10px;font-size:1rem;font-weight:600;cursor:pointer;margin-bottom:10px}
    .btn-blue{background:#2563eb;color:#fff}.btn-yellow{background:#d97706;color:#fff}.btn-green{background:#16a34a;color:#fff}
    .log-entry{font-size:.8rem;color:#94a3b8;padding:4px 0;border-bottom:1px solid #0f172a;font-family:monospace}
  </style>
</head>
<body>
  <h1>📈 Trading Bot</h1>
  <p class="sub">Revolut Signal Alerts — WhatsApp</p>

  <div class="card">
    <div class="stat">
      <span class="label">Statut</span>
      <span id="status-badge" class="badge green">Actif</span>
    </div>
    <div class="stat">
      <span class="label">Dernier scan</span>
      <span class="value" id="last-scan">—</span>
    </div>
    <div class="stat">
      <span class="label">Signaux aujourd'hui</span>
      <span class="value" id="signals-today">0</span>
    </div>
    <div class="stat">
      <span class="label">Intervalle auto</span>
      <span class="value">{{ interval }} min</span>
    </div>
  </div>

  <div class="card">
    <button class="btn btn-blue" onclick="doAction('/api/scan','Scan lancé !')">🔍 Scanner maintenant</button>
    <button class="btn btn-yellow" id="pause-btn" onclick="togglePause()">⏸ Mettre en pause</button>
  </div>

  <div class="card">
    <div class="label" style="margin-bottom:10px">Actifs surveillés</div>
    <div style="font-size:.85rem;color:#cbd5e1">
      <b>Actions :</b> {{ stocks }}<br><br>
      <b>Crypto :</b> {{ crypto }}
    </div>
  </div>

  <div class="card">
    <div class="label" style="margin-bottom:10px">Journal</div>
    <div id="log-container"></div>
  </div>

  <script>
    let paused = false;
    async function doAction(url) {
      const r = await fetch(url, {method:'POST'});
      const d = await r.json();
      alert(d.message);
      refreshStatus();
    }
    async function togglePause() {
      await doAction(paused ? '/api/resume' : '/api/pause');
    }
    async function refreshStatus() {
      const d = await (await fetch('/api/status')).json();
      paused = d.paused;
      document.getElementById('last-scan').textContent = d.last_scan || '—';
      document.getElementById('signals-today').textContent = d.signals_today;
      const badge = document.getElementById('status-badge');
      const btn   = document.getElementById('pause-btn');
      if (paused) {
        badge.textContent='En pause'; badge.className='badge red';
        btn.textContent='▶️ Reprendre'; btn.className='btn btn-green';
      } else {
        badge.textContent='Actif'; badge.className='badge green';
        btn.textContent='⏸ Mettre en pause'; btn.className='btn btn-yellow';
      }
      document.getElementById('log-container').innerHTML =
        d.log.map(e=>`<div class="log-entry">${e}</div>`).join('');
    }
    setInterval(refreshStatus, 10000);
    refreshStatus();
  </script>
</body>
</html>
"""

flask_app = Flask(__name__)


@flask_app.route("/")
def index():
    return render_template_string(
        HTML,
        interval=CHECK_INTERVAL_MINUTES,
        stocks=", ".join(STOCKS),
        crypto=", ".join(c.capitalize() for c in CRYPTO),
    )


@flask_app.route("/api/status")
def api_status():
    last = state["last_scan"].strftime("%H:%M:%S") if state["last_scan"] else None
    return jsonify({"paused": state["paused"], "last_scan": last,
                    "signals_today": state["signals_today"], "log": state["log"][:20]})


@flask_app.route("/api/scan", methods=["POST"])
def api_scan():
    threading.Thread(target=run_scan, args=("manuel",), daemon=True).start()
    return jsonify({"message": "Scan lancé !"})


@flask_app.route("/api/pause", methods=["POST"])
def api_pause():
    state["paused"] = True
    log("Scans automatiques mis en pause.")
    return jsonify({"message": "Bot mis en pause."})


@flask_app.route("/api/resume", methods=["POST"])
def api_resume():
    state["paused"] = False
    log("Scans automatiques repris.")
    return jsonify({"message": "Bot repris."})


# ─── Point d'entrée ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    ip = socket.gethostbyname(socket.gethostname())

    send_message(
        f"✅ Bot démarré\n"
        f"Surveillance toutes les {CHECK_INTERVAL_MINUTES} min.\n"
        f"Interface : http://{ip}:{WEB_PORT}"
    )

    threading.Thread(target=run_scan, args=("démarrage",), daemon=True).start()
    threading.Thread(target=scheduler_thread, daemon=True).start()

    print(f"\n  Interface web → http://{ip}:{WEB_PORT}\n")
    flask_app.run(host="0.0.0.0", port=WEB_PORT, debug=False)
