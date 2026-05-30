# Trading Signal Bot — Guide de démarrage

## 1. Crée ton bot Telegram (5 minutes)

1. Ouvre Telegram → cherche **@BotFather**
2. Tape `/newbot` → donne un nom → copie le **token** (ex: `7123456789:AAF...`)
3. Cherche **@userinfobot** → tape `/start` → copie ton **chat_id** (ex: `123456789`)

## 2. Configure le bot

Ouvre `config.py` et remplace :
```python
TELEGRAM_TOKEN  = "7123456789:AAFxxx..."   # ton token BotFather
TELEGRAM_CHAT_ID = "123456789"              # ton chat_id
```

Tu peux aussi modifier la liste des actifs à surveiller dans `STOCKS` et `CRYPTO`.

## 3. Installe les dépendances

```bash
cd trading_bot
pip install -r requirements.txt
```

## 4. Lance le bot

```bash
python main.py
```

Tu recevras un message Telegram de confirmation, puis des alertes automatiques.

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
