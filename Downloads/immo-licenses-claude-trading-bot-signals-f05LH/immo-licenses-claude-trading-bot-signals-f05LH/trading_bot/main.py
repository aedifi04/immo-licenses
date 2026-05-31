import json
import threading
import time
from datetime import datetime
import pandas as pd
from typing import Any, TypedDict
from flask import Flask, Response, jsonify, render_template_string

from config import STOCKS, CRYPTO, CRYPTO_BINANCE, CHECK_INTERVAL_MINUTES, WEB_PORT
from data_fetcher import fetch_stock, fetch_crypto, fetch_live_price_crypto, fetch_live_price_stock
from signal_engine import analyze, get_chart_signals
from alerts import send_signal, event_queue

# ─── État ─────────────────────────────────────────────────────────────────────
class BotState(TypedDict):
    paused: bool
    last_scan: datetime | None
    signals_today: int
    sent_keys: set[str]
    log: list[str]
    signal_history: list[dict[str, Any]]
    live_prices: dict[str, Any]

state: BotState = {
    "paused": False, "last_scan": None, "signals_today": 0,
    "sent_keys": set(), "log": [], "signal_history": [], "live_prices": {},
}
_scan_lock = threading.Lock()


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    print(entry)
    state["log"].insert(0, entry)
    if len(state["log"]) > 100:
        state["log"].pop()


# ─── Scan principal ───────────────────────────────────────────────────────────

def run_scan(triggered_by: str = "auto") -> int:
    if not _scan_lock.acquire(blocking=False):
        log("Scan ignoré — un scan est déjà en cours.")
        return 0
    try:
        return _do_scan(triggered_by)
    finally:
        _scan_lock.release()


def _do_scan(triggered_by: str) -> int:
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
                state["signal_history"].insert(0, _signal_to_dict(signal, now))
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
                state["signal_history"].insert(0, _signal_to_dict(signal, now))
                found += 1

    log(f"Scan terminé — {found} signal(s).")
    return found


def _signal_to_dict(signal: Any, now: datetime) -> dict[str, Any]:
    return {
        "asset": signal.asset.upper(), "asset_type": signal.asset_type,
        "action": signal.action, "price": round(signal.price, 2),
        "rsi": round(signal.rsi, 1), "momentum": round(signal.momentum, 2),
        "strength": signal.strength, "reasons": signal.reasons,
        "ts": now.strftime("%d/%m %H:%M"),
    }


def scheduler_thread() -> None:
    while True:
        time.sleep(CHECK_INTERVAL_MINUTES * 60)
        if not state["paused"]:
            run_scan("auto")


def price_updater_thread() -> None:
    """Met à jour les prix live toutes les 30 secondes."""
    while True:
        prices: dict[str, Any] = {}
        for coin in CRYPTO:
            result = fetch_live_price_crypto(coin)
            if result:
                prices[coin.upper()] = {"price": result[0], "pct": result[1],
                                         "symbol": CRYPTO_BINANCE[coin]}
        for ticker in STOCKS:
            result = fetch_live_price_stock(ticker)
            if result:
                prices[ticker] = {"price": result[0], "pct": result[1]}
        if prices:
            state["live_prices"] = prices
            event_queue.put_nowait({"type": "prices", "data": prices})
        time.sleep(30)


# ─── Interface web ────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Trading Bot — Dashboard</title>
<script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
<style>
:root{--bg:#0d1117;--card:#161b22;--border:#30363d;--text:#e6edf3;--muted:#8b949e;
     --green:#3fb950;--green-dim:#1a2d1a;--red:#f85149;--red-dim:#2d1a1a;
     --blue:#58a6ff;--yellow:#e3b341;--purple:#bc8cff}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:13px;height:100vh;display:flex;flex-direction:column;overflow:hidden}

/* ── Header ── */
header{background:var(--card);border-bottom:1px solid var(--border);padding:0 16px;height:48px;display:flex;align-items:center;gap:12px;flex-shrink:0}
header h1{font-size:14px;font-weight:600;white-space:nowrap}
.status-dot{width:7px;height:7px;border-radius:50%;background:var(--green);flex-shrink:0}
.status-dot.paused{background:var(--yellow)}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.status-dot:not(.paused){animation:pulse 2s infinite}
.price-ticker{display:flex;gap:6px;overflow-x:auto;flex:1;scrollbar-width:none}
.price-ticker::-webkit-scrollbar{display:none}
.price-chip{background:#1c2128;border:1px solid var(--border);border-radius:6px;padding:4px 10px;white-space:nowrap;cursor:pointer;transition:border-color .15s}
.price-chip:hover,.price-chip.active{border-color:var(--blue)}
.price-chip .sym{font-weight:700;font-size:12px}
.price-chip .val{font-size:12px;margin-left:4px}
.price-chip .chg{font-size:11px;margin-left:3px}
.up{color:var(--green)}.down{color:var(--red)}

/* ── Layout ── */
.layout{display:flex;flex:1;overflow:hidden}
.sidebar{width:270px;flex-shrink:0;border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden}
.main{flex:1;display:flex;flex-direction:column;overflow:hidden}

/* ── Sidebar panels ── */
.panel{border-bottom:1px solid var(--border);padding:12px}
.panel-title{font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px}
.btn{border:none;border-radius:5px;padding:7px 12px;font-size:12px;font-weight:600;cursor:pointer;width:100%;margin-bottom:6px;transition:opacity .15s}
.btn:hover{opacity:.85}
.btn-blue{background:var(--blue);color:#0d1117}
.btn-yellow{background:var(--yellow);color:#0d1117}
.btn-green{background:var(--green);color:#0d1117}

/* ── Signal cards ── */
.sig-card{border-radius:6px;padding:10px;margin-bottom:8px;border-left:3px solid}
.sig-buy{background:var(--green-dim);border-color:var(--green)}
.sig-sell{background:var(--red-dim);border-color:var(--red)}
.sig-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px}
.sig-asset{font-weight:700;font-size:13px}
.badge{padding:1px 7px;border-radius:10px;font-size:10px;font-weight:700}
.badge-buy{background:var(--green-dim);color:var(--green)}
.badge-sell{background:var(--red-dim);color:var(--red)}
.sig-price{font-size:16px;font-weight:700;margin:2px 0}
.sig-meta{font-size:11px;color:var(--muted)}
.sig-reasons{font-size:11px;color:var(--muted);margin-top:5px;padding-top:5px;border-top:1px solid var(--border)}
.strength{display:flex;gap:3px;align-items:center;margin-top:3px}
.sd{width:5px;height:5px;border-radius:50%}

/* ── Log ── */
.log-scroll{overflow-y:auto;flex:1;padding:8px 12px}
.log-line{font-family:monospace;font-size:11px;color:var(--muted);padding:2px 0;border-bottom:1px solid #0d1117}

/* ── Chart area ── */
.chart-area{flex:1;display:flex;flex-direction:column;overflow:hidden;padding:12px;gap:8px}
.chart-header{display:flex;align-items:center;gap:8px;flex-shrink:0}
.asset-tabs{display:flex;gap:4px;overflow-x:auto;scrollbar-width:none;flex:1}
.asset-tabs::-webkit-scrollbar{display:none}
.tab{background:#1c2128;border:1px solid var(--border);border-radius:5px;padding:4px 10px;cursor:pointer;font-size:12px;white-space:nowrap;transition:all .15s}
.tab:hover,.tab.active{background:var(--blue);color:#0d1117;border-color:var(--blue);font-weight:600}
.chart-wrap{background:var(--card);border:1px solid var(--border);border-radius:8px;overflow:hidden;flex:1;min-height:0}
.rsi-wrap{background:var(--card);border:1px solid var(--border);border-radius:8px;overflow:hidden;height:110px;flex-shrink:0}
.chart-label{font-size:10px;color:var(--muted);padding:6px 10px;border-bottom:1px solid var(--border)}

/* ── Empty ── */
.empty{text-align:center;color:var(--muted);padding:30px 12px;font-size:12px}
</style>
</head>
<body>

<header>
  <span class="status-dot" id="sdot"></span>
  <h1>Trading Bot</h1>
  <div class="price-ticker" id="price-ticker">
    <span style="color:var(--muted);font-size:12px">Chargement des prix…</span>
  </div>
</header>

<div class="layout">

  <!-- ── Sidebar ── -->
  <aside class="sidebar">

    <div class="panel">
      <div class="panel-title">Contrôles</div>
      <button class="btn btn-blue" id="scan-btn" onclick="doScan()">🔍 Scanner maintenant</button>
      <button class="btn btn-yellow" id="pause-btn" onclick="togglePause()">⏸ Mettre en pause</button>
    </div>

    <div class="panel" style="flex-shrink:0">
      <div class="panel-title">Signaux <span id="sig-count" style="font-weight:400;color:var(--muted)">(0)</span></div>
      <div id="sig-feed" style="max-height:320px;overflow-y:auto">
        <div class="empty">En attente de signaux…<br>Lance un scan pour commencer.</div>
      </div>
    </div>

    <div class="panel" style="flex:1;display:flex;flex-direction:column;overflow:hidden;min-height:0">
      <div class="panel-title">Journal</div>
      <div class="log-scroll" id="log-feed"></div>
    </div>

  </aside>

  <!-- ── Chart ── -->
  <div class="main">
    <div class="chart-area">

      <div class="chart-header">
        <div class="asset-tabs" id="asset-tabs"></div>
        <div id="chart-info" style="font-size:12px;color:var(--muted);white-space:nowrap"></div>
      </div>

      <div class="chart-wrap">
        <div class="chart-label" id="candle-label">CHANDELIER — 1H</div>
        <div id="candle-chart" style="width:100%;height:calc(100% - 28px)"></div>
      </div>

      <div class="rsi-wrap">
        <div class="chart-label">RSI (14) — zones &lt;38 / &gt;62</div>
        <div id="rsi-chart" style="width:100%;height:calc(100% - 28px)"></div>
      </div>

    </div>
  </div>

</div>

<script>
// ── État ──────────────────────────────────────────────────────────────────────
let paused = false;
let sigCount = 0;
let activeAsset = null;
let candleChart = null, rsiChart = null;
let candleSeries = null, emaShortSeries = null, emaLongSeries = null, rsiSeries = null;

// ── Init graphiques ────────────────────────────────────────────────────────────
function initCharts() {
  const candleEl = document.getElementById('candle-chart');
  const rsiEl    = document.getElementById('rsi-chart');
  const opts = {
    layout: { background: { color: '#161b22' }, textColor: '#8b949e' },
    grid: { vertLines: { color: '#21262d' }, horzLines: { color: '#21262d' } },
    crosshair: { mode: 1 },
    timeScale: { borderColor: '#30363d', timeVisible: true },
    rightPriceScale: { borderColor: '#30363d' },
    handleScroll: true, handleScale: true,
  };

  candleChart = LightweightCharts.createChart(candleEl, { ...opts, height: candleEl.clientHeight || 300 });
  candleSeries  = candleChart.addCandlestickSeries({ upColor:'#3fb950', downColor:'#f85149', borderVisible:false, wickUpColor:'#3fb950', wickDownColor:'#f85149' });
  emaShortSeries = candleChart.addLineSeries({ color:'#58a6ff', lineWidth:1, priceLineVisible:false, lastValueVisible:false });
  emaLongSeries  = candleChart.addLineSeries({ color:'#bc8cff', lineWidth:1, priceLineVisible:false, lastValueVisible:false });

  rsiChart = LightweightCharts.createChart(rsiEl, {
    ...opts, height: rsiEl.clientHeight || 80,
    rightPriceScale: { ...opts.rightPriceScale, autoScale: false, visible: true },
  });
  rsiSeries = rsiChart.addLineSeries({ color:'#e3b341', lineWidth:1.5, priceLineVisible:false, lastValueVisible:true });
  rsiChart.priceScale('right').applyOptions({ autoScale: false, minimum: 0, maximum: 100 });

  // Zones RSI 38/62
  rsiChart.addLineSeries({ color:'#3fb95040', lineWidth:1, priceLineVisible:false, lastValueVisible:false })
          .setData([]);
}

// ── Chargement des données du graphique ───────────────────────────────────────
async function loadChart(asset) {
  activeAsset = asset;
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.asset === asset));
  document.getElementById('candle-label').textContent = `${asset} — CHANDELIER 1H`;

  const r = await fetch(`/api/chart/${encodeURIComponent(asset)}`);
  const d = await r.json();
  if (d.error) { document.getElementById('chart-info').textContent = d.error; return; }

  candleSeries.setData(d.candles);
  emaShortSeries.setData(d.ema_short);
  emaLongSeries.setData(d.ema_long);
  rsiSeries.setData(d.rsi);
  candleSeries.setMarkers(d.markers);

  const p = d.current_price;
  const chg = d.price_change;
  const sign = chg >= 0 ? '+' : '';
  const cls  = chg >= 0 ? 'up' : 'down';
  document.getElementById('chart-info').innerHTML =
    `<b>${p?.toLocaleString('fr-FR',{maximumFractionDigits:4}) ?? '—'}</b> <span class="${cls}">${sign}${chg?.toFixed(2) ?? '—'}%</span>`;

  candleChart.timeScale().fitContent();
  rsiChart.timeScale().fitContent();
}

// ── Tabs ──────────────────────────────────────────────────────────────────────
function buildTabs(stocks, crypto) {
  const container = document.getElementById('asset-tabs');
  container.innerHTML = '';
  const all = [...crypto.map(c => c.toUpperCase()), ...stocks];
  all.forEach((a, i) => {
    const t = document.createElement('div');
    t.className = 'tab';
    t.dataset.asset = a;
    t.textContent = a;
    t.onclick = () => loadChart(a);
    container.appendChild(t);
    if (i === 0) { t.classList.add('active'); loadChart(a); }
  });
}

// ── Ticker prix ───────────────────────────────────────────────────────────────
function updateTicker(prices) {
  const el = document.getElementById('price-ticker');
  el.innerHTML = '';
  Object.entries(prices).forEach(([sym, d]) => {
    const sign = d.pct >= 0 ? '+' : '';
    const cls  = d.pct >= 0 ? 'up' : 'down';
    const chip = document.createElement('div');
    chip.className = 'price-chip' + (sym === activeAsset ? ' active' : '');
    chip.dataset.asset = sym;
    chip.onclick = () => loadChart(sym);
    chip.innerHTML = `<span class="sym">${sym}</span><span class="val">${d.price?.toLocaleString('fr-FR',{maximumFractionDigits:4})}</span><span class="chg ${cls}">${sign}${d.pct?.toFixed(2)}%</span>`;
    el.appendChild(chip);
  });
}

// ── Signal card ───────────────────────────────────────────────────────────────
function renderSignal(s) {
  const feed = document.getElementById('sig-feed');
  const empty = feed.querySelector('.empty');
  if (empty) empty.remove();
  sigCount++;
  document.getElementById('sig-count').textContent = `(${sigCount})`;

  const isBuy = s.action === 'ACHAT';
  const color = isBuy ? 'var(--green)' : 'var(--red)';
  const dots  = [1,2,3,4].map(i => `<span class="sd" style="background:${i<=s.strength?color:'var(--border)'}"></span>`).join('');
  const reasons = (s.reasons||[]).map(r=>`• ${r}`).join('<br>');
  const label = s.asset_type === 'stock' ? '📈' : '🪙';

  const div = document.createElement('div');
  div.className = `sig-card ${isBuy?'sig-buy':'sig-sell'}`;
  div.innerHTML = `
    <div class="sig-head">
      <span class="sig-asset">${isBuy?'🟢':'🔴'} ${label} ${s.asset}</span>
      <span class="badge ${isBuy?'badge-buy':'badge-sell'}">${s.action}</span>
    </div>
    <div class="sig-price">${s.price?.toLocaleString('fr-FR',{maximumFractionDigits:4})} $</div>
    <div class="sig-meta">RSI ${s.rsi} · Momentum ${s.momentum>0?'+':''}${s.momentum}% · ${s.ts}</div>
    <div class="strength">${dots}</div>
    <div class="sig-reasons">${reasons}</div>`;
  feed.prepend(div);

  const title = `${isBuy?'🟢':'🔴'} ${s.action} — ${s.asset}`;
  const body  = `${s.price?.toLocaleString()} $ | RSI ${s.rsi} | ${(s.reasons||[]).join(', ')}`;
  if (Notification.permission === 'granted') new Notification(title, { body });
}

function addLog(text, ts) {
  const feed = document.getElementById('log-feed');
  const div = document.createElement('div');
  div.className = 'log-line';
  div.textContent = `[${ts}] ${text}`;
  feed.prepend(div);
  while (feed.children.length > 50) feed.lastChild.remove();
}

function updateStatus(d) {
  paused = d.paused;
  const dot  = document.getElementById('sdot');
  const btn  = document.getElementById('pause-btn');
  dot.className = 'status-dot' + (paused?' paused':'');
  if (paused) { btn.textContent='▶️ Reprendre'; btn.className='btn btn-green'; }
  else        { btn.textContent='⏸ Mettre en pause'; btn.className='btn btn-yellow'; }
}

// ── SSE ───────────────────────────────────────────────────────────────────────
const sse = new EventSource('/api/stream');
sse.addEventListener('signal',  e => renderSignal(JSON.parse(e.data)));
sse.addEventListener('log',     e => { const d=JSON.parse(e.data); addLog(d.text,d.ts); });
sse.addEventListener('prices',  e => updateTicker(JSON.parse(e.data).data));
sse.addEventListener('status',  e => updateStatus(JSON.parse(e.data)));

// ── Actions ───────────────────────────────────────────────────────────────────
async function doScan() {
  const btn = document.getElementById('scan-btn');
  btn.textContent='⏳ Scan…'; btn.disabled=true;
  await fetch('/api/scan',{method:'POST'});
  setTimeout(()=>{ btn.textContent='🔍 Scanner maintenant'; btn.disabled=false; }, 4000);
  setTimeout(()=>{ if(activeAsset) loadChart(activeAsset); }, 35000);
}
async function togglePause() {
  await fetch(paused?'/api/resume':'/api/pause',{method:'POST'});
}

// ── Init ─────────────────────────────────────────────────────────────────────
if (Notification.permission === 'default') Notification.requestPermission();
initCharts();
buildTabs({{ stocks|tojson }}, {{ crypto|tojson }});
fetch('/api/prices').then(r=>r.json()).then(d=>{ if(d.data) updateTicker(d.data); });

// Sync status
setInterval(async ()=>{ const d=await(await fetch('/api/status')).json(); updateStatus(d); }, 15000);
// Refresh chart toutes les 5 min
setInterval(()=>{ if(activeAsset) loadChart(activeAsset); }, 5*60*1000);

window.addEventListener('resize', ()=>{
  if(candleChart) candleChart.applyOptions({height: document.getElementById('candle-chart').clientHeight});
  if(rsiChart)    rsiChart.applyOptions({height: document.getElementById('rsi-chart').clientHeight});
});
</script>
</body>
</html>
"""

flask_app = Flask(__name__)


def _df_to_chart(df: pd.DataFrame, asset: str, asset_type: str) -> dict[str, Any]:
    from indicators import add_indicators
    df_ind = add_indicators(df)

    candles:  list[dict[str, Any]] = []
    ema_s:    list[dict[str, Any]] = []
    ema_l:    list[dict[str, Any]] = []
    rsi_vals: list[dict[str, Any]] = []

    for ts, row in df_ind.iterrows():
        t = int(pd.Timestamp(ts).timestamp())
        o  = float(row.get("open",  row["close"]))
        h  = float(row.get("high",  row["close"]))
        lo = float(row.get("low",   row["close"]))
        c  = float(row["close"])
        candles.append({"time": t, "open": round(o,4), "high": round(h,4), "low": round(lo,4), "close": round(c,4)})
        ema_s.append({"time": t, "value": round(float(row["ema_short"]), 4)})
        ema_l.append({"time": t, "value": round(float(row["ema_long"]),  4)})
        if not pd.isna(row["rsi"]):
            rsi_vals.append({"time": t, "value": round(float(row["rsi"]), 2)})

    markers: list[dict[str, Any]] = get_chart_signals(df, asset, asset_type)
    last_price = float(df["close"].iloc[-1])
    prev_price = float(df["close"].iloc[-2]) if len(df) > 1 else last_price
    change_pct = (last_price - prev_price) / prev_price * 100 if prev_price else 0

    return {
        "candles": candles, "ema_short": ema_s, "ema_long": ema_l,
        "rsi": rsi_vals, "markers": markers,
        "current_price": round(last_price, 4),
        "price_change": round(change_pct, 2),
    }


# ── API ────────────────────────────────────────────────────────────────────────

@flask_app.route("/")
def index():
    return render_template_string(HTML,
        stocks=STOCKS,
        crypto=[c.upper() for c in CRYPTO])


@flask_app.route("/api/chart/<asset>")
def api_chart(asset: str):
    asset_up = asset.upper()
    coin_id = next((c for c in CRYPTO if CRYPTO_BINANCE[c].replace("USDT","") == asset_up or c.upper() == asset_up), None)
    if coin_id:
        df = fetch_crypto(coin_id)
        if df is None:
            return jsonify({"error": f"Impossible de récupérer les données pour {asset}"})
        return jsonify(_df_to_chart(df, coin_id, "crypto"))
    else:
        ticker = asset_up
        df = fetch_stock(ticker)
        if df is None:
            return jsonify({"error": f"Impossible de récupérer les données pour {asset}"})
        return jsonify(_df_to_chart(df, ticker, "stock"))


@flask_app.route("/api/prices")
def api_prices():
    return jsonify({"data": state["live_prices"]})


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
    return jsonify({"ok": True})


@flask_app.route("/api/resume", methods=["POST"])
def api_resume():
    state["paused"] = False
    log("Scans automatiques repris.")
    return jsonify({"ok": True})


def _sse_stream():
    while True:
        try:
            data = event_queue.get(timeout=25)
            yield f"event: {data['type']}\ndata: {json.dumps(data)}\n\n"
        except Exception:
            yield "event: ping\ndata: {}\n\n"


@flask_app.route("/api/stream")
def api_stream():
    return Response(_sse_stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Démarrage ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import webbrowser
    url = f"http://localhost:{WEB_PORT}"

    threading.Thread(target=run_scan,          args=("démarrage",), daemon=True).start()
    threading.Thread(target=scheduler_thread,  daemon=True).start()
    threading.Thread(target=price_updater_thread, daemon=True).start()

    print(f"\n  Dashboard → {url}\n")
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    flask_app.run(host="0.0.0.0", port=WEB_PORT, debug=False)
