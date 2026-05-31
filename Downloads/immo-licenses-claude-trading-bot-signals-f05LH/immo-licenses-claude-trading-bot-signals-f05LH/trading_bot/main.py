import json
import threading
import time
from datetime import datetime
import pandas as pd
from typing import Any, TypedDict
from dotenv import load_dotenv
load_dotenv()  # charge .env avant tout autre import
from flask import Flask, Response, jsonify, render_template_string

from config import STOCKS, CRYPTO, CRYPTO_BINANCE, CHECK_INTERVAL_MINUTES, WEB_PORT
from data_fetcher import fetch_stock, fetch_crypto, fetch_live_price_crypto, fetch_live_price_stock
from signal_engine import analyze, get_chart_signals
from alerts import send_signal, event_queue
from sources import get_reddit_sentiment, get_fear_greed, get_news, get_fundamentals
import ai_analyst

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


# ─── Enrichissement multi-sources ─────────────────────────────────────────────

def _enrich(asset: str, asset_type: str, rsi: float, momentum: float) -> dict[str, Any]:
    """Récupère Reddit, Fear&Greed, news, fondamentaux et analyse IA."""
    is_crypto = asset_type == "crypto"
    reddit   = get_reddit_sentiment(asset)
    fg       = get_fear_greed() if is_crypto else None
    news     = get_news(asset, is_crypto=is_crypto)
    fund     = get_fundamentals(asset) if not is_crypto else {}
    ai_res   = ai_analyst.analyze(
        asset, asset_type, rsi, momentum,
        reddit, fg or {"value": 50, "label": "N/A"},
        news, fund,
    )
    return {"reddit": reddit, "fear_greed": fg, "news": news, "ai": ai_res}


def _signal_to_dict(signal: Any, now: datetime, enrichment: dict[str, Any]) -> dict[str, Any]:
    return {
        "asset":      signal.asset.upper(),
        "asset_type": signal.asset_type,
        "action":     signal.action,
        "price":      round(signal.price, 2),
        "rsi":        round(signal.rsi, 1),
        "momentum":   round(signal.momentum, 2),
        "strength":   signal.strength,
        "reasons":    signal.reasons,
        "ts":         now.strftime("%d/%m %H:%M"),
        "reddit":     enrichment.get("reddit"),
        "fear_greed": enrichment.get("fear_greed"),
        "ai":         enrichment.get("ai"),
        "news":       enrichment.get("news", []),
    }


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
                log(f"{ticker}: signal {signal.action} — enrichissement en cours…")
                enrichment = _enrich(ticker, "stock", signal.rsi, signal.momentum)
                entry = _signal_to_dict(signal, now, enrichment)
                send_signal(signal)
                state["sent_keys"].add(key)
                state["signals_today"] += 1
                state["signal_history"].insert(0, entry)
                event_queue.put_nowait({"type": "signal", **entry})
                found += 1

    for coin in CRYPTO:
        df = fetch_crypto(coin)
        if df is None:
            continue
        signal = analyze(coin, df, "crypto")
        if signal:
            key = f"{coin}-{signal.action}-{now.date()}"
            if key not in state["sent_keys"]:
                log(f"{coin}: signal {signal.action} — enrichissement en cours…")
                enrichment = _enrich(coin, "crypto", signal.rsi, signal.momentum)
                entry = _signal_to_dict(signal, now, enrichment)
                send_signal(signal)
                state["sent_keys"].add(key)
                state["signals_today"] += 1
                state["signal_history"].insert(0, entry)
                event_queue.put_nowait({"type": "signal", **entry})
                found += 1

    log(f"Scan terminé — {found} signal(s).")
    return found


def scheduler_thread() -> None:
    while True:
        time.sleep(CHECK_INTERVAL_MINUTES * 60)
        if not state["paused"]:
            run_scan("auto")


def price_updater_thread() -> None:
    while True:
        prices: dict[str, Any] = {}
        for coin in CRYPTO:
            result = fetch_live_price_crypto(coin)
            if result:
                prices[coin.upper()] = {"price": result[0], "pct": result[1]}
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
     --blue:#58a6ff;--yellow:#e3b341;--purple:#bc8cff;--orange:#f0883e}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:13px;height:100vh;display:flex;flex-direction:column;overflow:hidden}
header{background:var(--card);border-bottom:1px solid var(--border);padding:0 16px;height:48px;display:flex;align-items:center;gap:12px;flex-shrink:0}
header h1{font-size:14px;font-weight:600;white-space:nowrap}
.sdot{width:7px;height:7px;border-radius:50%;background:var(--green);flex-shrink:0}
.sdot.paused{background:var(--yellow)}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.sdot:not(.paused){animation:pulse 2s infinite}
.ticker{display:flex;gap:6px;overflow-x:auto;flex:1;scrollbar-width:none;align-items:center}
.ticker::-webkit-scrollbar{display:none}
.chip{background:#1c2128;border:1px solid var(--border);border-radius:6px;padding:4px 10px;white-space:nowrap;cursor:pointer;transition:border-color .15s;display:flex;align-items:center;gap:4px}
.chip:hover,.chip.active{border-color:var(--blue)}
.chip .sym{font-weight:700;font-size:11px}
.chip .val{font-size:12px}
.chip .chg{font-size:11px}
.up{color:var(--green)}.dn{color:var(--red)}
/* Fear&Greed chip in header */
.fg-chip{background:#1c2128;border:1px solid var(--border);border-radius:6px;padding:4px 10px;font-size:11px;white-space:nowrap;display:flex;align-items:center;gap:5px}
.fg-num{font-weight:700;font-size:13px}
/* Layout */
.layout{display:flex;flex:1;overflow:hidden}
.sidebar{width:275px;flex-shrink:0;border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden}
.main{flex:1;display:flex;flex-direction:column;overflow:hidden}
.panel{border-bottom:1px solid var(--border);padding:10px 12px}
.ptitle{font-size:10px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px}
.btn{border:none;border-radius:5px;padding:7px 12px;font-size:12px;font-weight:600;cursor:pointer;width:100%;margin-bottom:6px;transition:opacity .15s}
.btn:hover{opacity:.85}
.btn-blue{background:var(--blue);color:#0d1117}.btn-yellow{background:var(--yellow);color:#0d1117}.btn-green{background:var(--green);color:#0d1117}
/* Signal cards */
.sc{border-radius:6px;padding:10px;margin-bottom:8px;border-left:3px solid;animation:fadein .3s}
@keyframes fadein{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:none}}
.sc-buy{background:var(--green-dim);border-color:var(--green)}
.sc-sell{background:var(--red-dim);border-color:var(--red)}
.sc-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:3px}
.sc-asset{font-weight:700;font-size:13px}
.badge{padding:1px 7px;border-radius:10px;font-size:10px;font-weight:700}
.bb{background:var(--green-dim);color:var(--green)}.bs{background:var(--red-dim);color:var(--red)}
.bn{background:#21262d;color:var(--muted)}
.sc-price{font-size:15px;font-weight:700;margin:2px 0}
.sc-meta{font-size:11px;color:var(--muted);margin-bottom:6px}
/* Multi-source bars */
.sources{margin:6px 0;border-top:1px solid var(--border);padding-top:6px}
.src-row{display:flex;align-items:center;gap:6px;margin-bottom:4px}
.src-lbl{font-size:10px;color:var(--muted);width:80px;flex-shrink:0}
.src-bar{flex:1;height:4px;background:var(--border);border-radius:2px;overflow:hidden}
.src-fill{height:100%;border-radius:2px;transition:width .5s}
.src-val{font-size:10px;color:var(--text);width:60px;text-align:right;flex-shrink:0}
.sc-reasons{font-size:11px;color:var(--muted);margin-top:5px;padding-top:5px;border-top:1px solid var(--border)}
/* Log */
.log-scroll{overflow-y:auto;flex:1;padding:6px 12px}
.ll{font-family:monospace;font-size:11px;color:var(--muted);padding:2px 0;border-bottom:1px solid #0d1117}
/* Chart area */
.chart-area{flex:1;display:flex;flex-direction:column;overflow:hidden;padding:10px;gap:8px}
.tabs-row{display:flex;align-items:center;gap:8px;flex-shrink:0}
.tabs{display:flex;gap:4px;overflow-x:auto;scrollbar-width:none;flex:1}
.tabs::-webkit-scrollbar{display:none}
.tab{background:#1c2128;border:1px solid var(--border);border-radius:5px;padding:4px 10px;cursor:pointer;font-size:12px;white-space:nowrap;transition:all .15s}
.tab:hover,.tab.active{background:var(--blue);color:#0d1117;border-color:var(--blue);font-weight:600}
.cbox{background:var(--card);border:1px solid var(--border);border-radius:8px;overflow:hidden}
.cbox-label{font-size:10px;color:var(--muted);padding:5px 10px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between}
#candle-wrap{flex:1;min-height:0}
#rsi-wrap{height:100px;flex-shrink:0}
#news-wrap{height:110px;flex-shrink:0}
.news-item{font-size:11px;color:var(--muted);padding:4px 0;border-bottom:1px solid var(--border);line-height:1.4}
.news-item:last-child{border:none}
.news-scroll{overflow-y:auto;height:calc(100% - 28px);padding:4px 10px}
.empty{text-align:center;color:var(--muted);padding:20px 12px;font-size:12px}
</style>
</head>
<body>

<header>
  <span class="sdot" id="sdot"></span>
  <h1>Trading Bot</h1>
  <div class="ticker" id="ticker"><span style="color:var(--muted);font-size:12px">Chargement…</span></div>
  <div class="fg-chip" id="fg-chip" style="display:none">
    😨 <span class="fg-num" id="fg-val">—</span> <span id="fg-lbl" style="color:var(--muted)">Fear&Greed</span>
  </div>
</header>

<div class="layout">

  <aside class="sidebar">
    <div class="panel">
      <div class="ptitle">Contrôles</div>
      <button class="btn btn-blue" id="scan-btn" onclick="doScan()">🔍 Scanner maintenant</button>
      <button class="btn btn-yellow" id="pause-btn" onclick="togglePause()">⏸ Mettre en pause</button>
    </div>
    <div class="panel" style="flex-shrink:0">
      <div class="ptitle">Signaux <span id="sig-count" style="font-weight:400;color:var(--muted)">(0)</span></div>
      <div id="sig-feed" style="max-height:340px;overflow-y:auto">
        <div class="empty">En attente de signaux…</div>
      </div>
    </div>
    <div class="panel" style="flex:1;display:flex;flex-direction:column;overflow:hidden;min-height:0">
      <div class="ptitle">Journal</div>
      <div class="log-scroll" id="log-feed"></div>
    </div>
  </aside>

  <div class="main">
    <div class="chart-area">

      <div class="tabs-row">
        <div class="tabs" id="asset-tabs"></div>
        <div id="chart-info" style="font-size:12px;color:var(--muted);white-space:nowrap"></div>
      </div>

      <div class="cbox" id="candle-wrap">
        <div class="cbox-label">
          <span id="candle-label">CHANDELIER — 1H</span>
          <span style="color:var(--muted)">— EMA9 &nbsp;— EMA21</span>
        </div>
        <div id="candle-chart" style="width:100%;height:calc(100% - 26px)"></div>
      </div>

      <div class="cbox" id="rsi-wrap">
        <div class="cbox-label"><span>RSI (14)</span><span style="color:var(--green)">38</span><span style="color:var(--red)">62</span></div>
        <div id="rsi-chart" style="width:100%;height:calc(100% - 26px)"></div>
      </div>

      <div class="cbox" id="news-wrap">
        <div class="cbox-label"><span id="news-label">📰 Actualités</span><span id="reddit-badge" style="color:var(--muted)"></span></div>
        <div class="news-scroll" id="news-feed"><div class="empty">Sélectionne un actif</div></div>
      </div>

    </div>
  </div>

</div>

<script>
let paused = false, sigCount = 0, activeAsset = null;
let candleChart, rsiChart, candleSeries, emaShortS, emaLongS, rsiSeries;

function initCharts() {
  const opts = {
    layout:{background:{color:'#161b22'},textColor:'#8b949e'},
    grid:{vertLines:{color:'#21262d'},horzLines:{color:'#21262d'}},
    crosshair:{mode:1},timeScale:{borderColor:'#30363d',timeVisible:true},
    rightPriceScale:{borderColor:'#30363d'},handleScroll:true,handleScale:true,
  };
  const ce = document.getElementById('candle-chart');
  const re = document.getElementById('rsi-chart');
  candleChart = LightweightCharts.createChart(ce,{...opts,height:ce.clientHeight||280});
  candleSeries = candleChart.addCandlestickSeries({upColor:'#3fb950',downColor:'#f85149',borderVisible:false,wickUpColor:'#3fb950',wickDownColor:'#f85149'});
  emaShortS = candleChart.addLineSeries({color:'#58a6ff',lineWidth:1,priceLineVisible:false,lastValueVisible:false});
  emaLongS  = candleChart.addLineSeries({color:'#bc8cff',lineWidth:1,priceLineVisible:false,lastValueVisible:false});
  rsiChart  = LightweightCharts.createChart(re,{...opts,height:re.clientHeight||74,rightPriceScale:{...opts.rightPriceScale,autoScale:false}});
  rsiSeries = rsiChart.addLineSeries({color:'#e3b341',lineWidth:1.5,priceLineVisible:false,lastValueVisible:true});
  rsiChart.priceScale('right').applyOptions({autoScale:false,minimum:0,maximum:100});
}

async function loadChart(asset) {
  activeAsset = asset;
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t.dataset.asset===asset));
  document.getElementById('candle-label').textContent = `${asset} — CHANDELIER 1H`;
  const d = await (await fetch(`/api/chart/${encodeURIComponent(asset)}`)).json();
  if (d.error){document.getElementById('chart-info').textContent=d.error;return;}
  candleSeries.setData(d.candles);
  emaShortS.setData(d.ema_short);
  emaLongS.setData(d.ema_long);
  rsiSeries.setData(d.rsi);
  candleSeries.setMarkers(d.markers);
  const cls = d.price_change>=0?'up':'dn', sign=d.price_change>=0?'+':'';
  document.getElementById('chart-info').innerHTML =
    `<b>${d.current_price?.toLocaleString('fr-FR',{maximumFractionDigits:4})??'—'}</b> <span class="${cls}">${sign}${d.price_change?.toFixed(2)??'—'}%</span>`;
  candleChart.timeScale().fitContent();
  rsiChart.timeScale().fitContent();
  loadSentimentAndNews(asset);
}

async function loadSentimentAndNews(asset) {
  // News
  const news = await (await fetch(`/api/news/${encodeURIComponent(asset)}`)).json();
  const nf = document.getElementById('news-feed');
  nf.innerHTML = news.length
    ? news.map(h=>`<div class="news-item">• ${h}</div>`).join('')
    : '<div class="empty">Aucune actualité disponible</div>';
  document.getElementById('news-label').textContent = `📰 Actualités — ${asset}`;
  // Sentiment
  const s = await (await fetch(`/api/sentiment/${encodeURIComponent(asset)}`)).json();
  const pct = Math.round((s.reddit?.ratio||0.5)*100);
  const rColor = pct>60?'var(--green)':pct<40?'var(--red)':'var(--muted)';
  document.getElementById('reddit-badge').innerHTML =
    `<span style="color:${rColor}">💬 Reddit ${pct}% positif</span>`;
  if (s.fear_greed) {
    document.getElementById('fg-chip').style.display='flex';
    document.getElementById('fg-val').textContent = s.fear_greed.value;
    document.getElementById('fg-lbl').textContent = s.fear_greed.label;
    document.getElementById('fg-val').style.color = s.fear_greed.color||'var(--yellow)';
  }
}

function buildTabs(stocks, crypto) {
  const c = document.getElementById('asset-tabs');
  c.innerHTML='';
  [...crypto.map(x=>x.toUpperCase()),...stocks].forEach((a,i)=>{
    const t=document.createElement('div');
    t.className='tab'; t.dataset.asset=a; t.textContent=a;
    t.onclick=()=>loadChart(a); c.appendChild(t);
    if(i===0){t.classList.add('active');loadChart(a);}
  });
}

function updateTicker(prices) {
  const el=document.getElementById('ticker'); el.innerHTML='';
  Object.entries(prices).forEach(([sym,d])=>{
    const sign=d.pct>=0?'+':'',cls=d.pct>=0?'up':'dn';
    const chip=document.createElement('div');
    chip.className='chip'+(sym===activeAsset?' active':'');
    chip.dataset.asset=sym; chip.onclick=()=>loadChart(sym);
    chip.innerHTML=`<span class="sym">${sym}</span><span class="val">${d.price?.toLocaleString('fr-FR',{maximumFractionDigits:4})}</span><span class="chg ${cls}">${sign}${d.pct?.toFixed(2)}%</span>`;
    el.appendChild(chip);
  });
}

function renderSignal(s) {
  const feed=document.getElementById('sig-feed');
  const empty=feed.querySelector('.empty'); if(empty)empty.remove();
  sigCount++; document.getElementById('sig-count').textContent=`(${sigCount})`;
  const isBuy=s.action==='ACHAT', color=isBuy?'var(--green)':'var(--red)';
  const label=s.asset_type==='stock'?'📈':'🪙';
  const reasons=(s.reasons||[]).map(r=>`• ${r}`).join('<br>');

  // Barres multi-sources
  const techPct = Math.round((s.strength/4)*100);
  const redditPct = s.reddit ? Math.round(s.reddit.ratio*100) : 50;
  const redditColor = redditPct>60?'var(--green)':redditPct<40?'var(--red)':'var(--yellow)';
  let sourcesHtml = `
    <div class="sources">
      <div class="src-row">
        <span class="src-lbl">📊 Technique</span>
        <div class="src-bar"><div class="src-fill" style="width:${techPct}%;background:${color}"></div></div>
        <span class="src-val">${s.strength}/4</span>
      </div>`;
  if (s.reddit && s.reddit.total > 0) {
    sourcesHtml+=`<div class="src-row">
      <span class="src-lbl">💬 Reddit</span>
      <div class="src-bar"><div class="src-fill" style="width:${redditPct}%;background:${redditColor}"></div></div>
      <span class="src-val">${redditPct}% (${s.reddit.total})</span>
    </div>`;
  }
  if (s.fear_greed) {
    const fgPct=s.fear_greed.value, fgColor=s.fear_greed.color||'var(--yellow)';
    sourcesHtml+=`<div class="src-row">
      <span class="src-lbl">😨 Fear&Greed</span>
      <div class="src-bar"><div class="src-fill" style="width:${fgPct}%;background:${fgColor}"></div></div>
      <span class="src-val">${fgPct}/100</span>
    </div>`;
  }
  if (s.ai) {
    const aiAction=s.ai.action, aiConf=s.ai.confiance||0;
    const aiBadge=aiAction==='ACHAT'?'bb':aiAction==='VENTE'?'bs':'bn';
    sourcesHtml+=`<div class="src-row">
      <span class="src-lbl">🤖 Claude IA</span>
      <span class="badge ${aiBadge}">${aiAction} ${aiConf}%</span>
      <span class="src-val" style="font-size:9px;color:var(--muted);overflow:hidden">${(s.ai.resume||'').slice(0,30)}</span>
    </div>`;
  }
  sourcesHtml+='</div>';

  const div=document.createElement('div');
  div.className=`sc ${isBuy?'sc-buy':'sc-sell'}`;
  div.innerHTML=`
    <div class="sc-head">
      <span class="sc-asset">${isBuy?'🟢':'🔴'} ${label} ${s.asset}</span>
      <span class="badge ${isBuy?'bb':'bs'}">${s.action}</span>
    </div>
    <div class="sc-price">${s.price?.toLocaleString('fr-FR',{maximumFractionDigits:4})} $</div>
    <div class="sc-meta">RSI ${s.rsi} · Momentum ${s.momentum>0?'+':''}${s.momentum}% · ${s.ts}</div>
    ${sourcesHtml}
    <div class="sc-reasons">${reasons}</div>`;
  feed.prepend(div);

  if(Notification.permission==='granted')
    new Notification(`${isBuy?'🟢':'🔴'} ${s.action} — ${s.asset}`,
      {body:`${s.price?.toLocaleString()} $ | ${(s.reasons||[]).join(' | ')}`});
}

function addLog(text,ts) {
  const f=document.getElementById('log-feed');
  const d=document.createElement('div'); d.className='ll';
  d.textContent=`[${ts}] ${text}`; f.prepend(d);
  while(f.children.length>50) f.lastChild.remove();
}

function updateStatus(d) {
  paused=d.paused;
  const dot=document.getElementById('sdot'), btn=document.getElementById('pause-btn');
  dot.className='sdot'+(paused?' paused':'');
  if(paused){btn.textContent='▶️ Reprendre';btn.className='btn btn-green';}
  else{btn.textContent='⏸ Mettre en pause';btn.className='btn btn-yellow';}
}

const sse=new EventSource('/api/stream');
sse.addEventListener('signal', e=>renderSignal(JSON.parse(e.data)));
sse.addEventListener('log',    e=>{const d=JSON.parse(e.data);addLog(d.text,d.ts);});
sse.addEventListener('prices', e=>updateTicker(JSON.parse(e.data).data));
sse.addEventListener('status', e=>updateStatus(JSON.parse(e.data)));

async function doScan() {
  const btn=document.getElementById('scan-btn');
  btn.textContent='⏳ Scan…'; btn.disabled=true;
  await fetch('/api/scan',{method:'POST'});
  setTimeout(()=>{btn.textContent='🔍 Scanner maintenant';btn.disabled=false;},5000);
  setTimeout(()=>{if(activeAsset)loadChart(activeAsset);},35000);
}
async function togglePause(){await fetch(paused?'/api/resume':'/api/pause',{method:'POST'});}

if(Notification.permission==='default') Notification.requestPermission();
initCharts();
buildTabs({{ stocks|tojson }}, {{ crypto|tojson }});
fetch('/api/prices').then(r=>r.json()).then(d=>{if(d.data)updateTicker(d.data);});
setInterval(async()=>{const d=await(await fetch('/api/status')).json();updateStatus(d);},15000);
setInterval(()=>{if(activeAsset)loadChart(activeAsset);},5*60*1000);
window.addEventListener('resize',()=>{
  if(candleChart)candleChart.applyOptions({height:document.getElementById('candle-chart').clientHeight});
  if(rsiChart)rsiChart.applyOptions({height:document.getElementById('rsi-chart').clientHeight});
});
</script>
</body>
</html>
"""

flask_app = Flask(__name__)


def _resolve_asset(asset: str) -> tuple[str, bool]:
    """Retourne (identifiant, is_crypto)."""
    asset_up = asset.upper()
    coin_id = next(
        (c for c in CRYPTO if CRYPTO_BINANCE[c].replace("USDT","") == asset_up or c.upper() == asset_up),
        None,
    )
    return (coin_id or asset_up, coin_id is not None)


def _df_to_chart(df: pd.DataFrame, asset: str, asset_type: str) -> dict[str, Any]:
    from indicators import add_indicators
    df_ind = add_indicators(df)
    candles:  list[dict[str, Any]] = []
    ema_s:    list[dict[str, Any]] = []
    ema_l:    list[dict[str, Any]] = []
    rsi_vals: list[dict[str, Any]] = []
    for ts, row in df_ind.iterrows():
        t  = int(pd.Timestamp(str(ts)).timestamp())
        o  = float(row.get("open",  row["close"]))
        h  = float(row.get("high",  row["close"]))
        lo = float(row.get("low",   row["close"]))
        c  = float(row["close"])
        candles.append({"time":t,"open":round(o,4),"high":round(h,4),"low":round(lo,4),"close":round(c,4)})
        ema_s.append({"time":t,"value":round(float(row["ema_short"]),4)})
        ema_l.append({"time":t,"value":round(float(row["ema_long"]),4)})
        if not pd.isna(row["rsi"]):
            rsi_vals.append({"time":t,"value":round(float(row["rsi"]),2)})
    markers: list[dict[str, Any]] = get_chart_signals(df, asset, asset_type)
    last = float(df["close"].iloc[-1])
    prev = float(df["close"].iloc[-2]) if len(df) > 1 else last
    chg  = (last - prev) / prev * 100 if prev else 0
    return {"candles":candles,"ema_short":ema_s,"ema_long":ema_l,"rsi":rsi_vals,
            "markers":markers,"current_price":round(last,4),"price_change":round(chg,2)}


# ── API ────────────────────────────────────────────────────────────────────────

@flask_app.route("/")
def index():
    return render_template_string(HTML, stocks=STOCKS, crypto=[c.upper() for c in CRYPTO])


@flask_app.route("/api/chart/<asset>")
def api_chart(asset: str):
    ident, is_crypto = _resolve_asset(asset)
    df = fetch_crypto(ident) if is_crypto else fetch_stock(ident)
    if df is None:
        return jsonify({"error": f"Données indisponibles pour {asset}"})
    return jsonify(_df_to_chart(df, ident, "crypto" if is_crypto else "stock"))


@flask_app.route("/api/news/<asset>")
def api_news(asset: str):
    ident, is_crypto = _resolve_asset(asset)
    return jsonify(get_news(ident, is_crypto=is_crypto))


@flask_app.route("/api/sentiment/<asset>")
def api_sentiment(asset: str):
    ident, is_crypto = _resolve_asset(asset)
    reddit = get_reddit_sentiment(ident)
    fg = get_fear_greed() if is_crypto else None
    return jsonify({"reddit": reddit, "fear_greed": fg})


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
    threading.Thread(target=run_scan,             args=("démarrage",), daemon=True).start()
    threading.Thread(target=scheduler_thread,     daemon=True).start()
    threading.Thread(target=price_updater_thread, daemon=True).start()
    print(f"\n  Dashboard → {url}\n")
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    flask_app.run(host="0.0.0.0", port=WEB_PORT, debug=False)
