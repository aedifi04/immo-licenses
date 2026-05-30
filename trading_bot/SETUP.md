# Trading Signal Bot — Guide de démarrage

## 1. Crée ton bot Telegram (5 minutes)

1. Ouvre Telegram → cherche **@BotFather**
2. Tape `/newbot` → donne un nom → copie le **token** (ex: `7123456789:AAF...`)
3. Cherche **@userinfobot** → tape `/start` → copie ton **chat_id** (ex: `123456789`)

## 2. Configure le bot

Ouvre `config.py` et remplace :
```python
TELEGRAM_TOKEN   = "7123456789:AAFxxx..."   # ton token BotFather
TELEGRAM_CHAT_ID = "123456789"              # ton chat_id
```

Tu peux aussi modifier les listes `STOCKS` et `CRYPTO`.

## 3. Lance le bot

### Option A — Sur ton PC/Mac (simple)
```bash
cd trading_bot
pip install -r requirements.txt
python main.py
```
> Le bot s'arrête si tu fermes le terminal.

### Option B — Docker (recommandé, tourne en arrière-plan)
```bash
cd trading_bot
docker build -t trading-bot .
docker run -d --name trading-bot --restart unless-stopped trading-bot
```
> Tourne en continu, redémarre automatiquement si ton PC reboot.

### Option C — Cloud gratuit (tourne 24/7 sans PC allumé)
Déploie sur **Railway.app** (gratuit) :
1. Crée un compte sur railway.app
2. "New Project" → "Deploy from GitHub repo"
3. Sélectionne ce repo → Railway détecte le Dockerfile automatiquement
4. Ajoute les variables d'environnement `TELEGRAM_TOKEN` et `TELEGRAM_CHAT_ID`

---

## Commandes depuis ton téléphone

Une fois le bot lancé, ouvre Telegram et tape dans la conversation avec ton bot :

| Commande | Action |
|---|---|
| `/start` | Affiche l'aide |
| `/scan` | Force un scan immédiat |
| `/status` | État du bot, dernier scan, nb de signaux |
| `/pause` | Met en pause les scans automatiques |
| `/resume` | Reprend les scans automatiques |
| `/watchlist` | Liste des actifs surveillés |

---

## Comprendre les alertes

Une alerte est envoyée quand **au moins 2 conditions sur 3** sont réunies :

| Condition | ACHAT | VENTE |
|---|---|---|
| RSI | < 30 (survendu) | > 70 (suracheté) |
| MACD | Croise à la hausse | Croise à la baisse |
| EMA 9/21 | Croise à la hausse | Croise à la baisse |

**Force du signal :**
- 2/3 conditions = signal moyen
- 3/3 conditions = signal fort (plus fiable)

---

## ⚠️ Avertissement

Ce bot génère des **signaux techniques informatifs**, pas des conseils financiers.
Les marchés sont imprévisibles. N'investis jamais plus que tu ne peux te permettre de perdre.
Toujours exécuter manuellement sur **Revolut** après avoir vérifié le signal.
