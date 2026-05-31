"""
Analyste IA via Claude Haiku — synthèse de toutes les sources.
Nécessite la variable d'environnement ANTHROPIC_API_KEY.
Si absente, retourne None et le bot fonctionne sans IA.
"""
import json
import os
from typing import Any

_ENABLED: bool | None = None  # None = pas encore vérifié


def is_enabled() -> bool:
    global _ENABLED
    if _ENABLED is None:
        _ENABLED = bool(os.getenv("ANTHROPIC_API_KEY"))
        if _ENABLED:
            print("[ai] Analyste IA activé (Claude Haiku)")
        else:
            print("[ai] ANTHROPIC_API_KEY non défini — analyste IA désactivé")
    return _ENABLED


def analyze(
    asset: str,
    asset_type: str,
    rsi: float,
    momentum: float,
    reddit: dict[str, Any],
    fear_greed: dict[str, Any],
    news: list[str],
    fundamentals: dict[str, Any],
) -> dict[str, Any] | None:
    """Retourne {action, confiance, resume} ou None si IA désactivée."""
    if not is_enabled():
        return None
    try:
        import anthropic
        client = anthropic.Anthropic()

        news_str = "\n".join(f"- {h}" for h in news[:5]) or "Aucune actualité disponible"
        fg_str = f"{fear_greed['value']}/100 ({fear_greed['label']})" if asset_type == "crypto" else "N/A (action)"
        fund_str = ""
        if fundamentals.get("pe_ratio"):
            fund_str = f"P/E: {fundamentals['pe_ratio']:.1f} | EPS: {fundamentals.get('eps','N/A')} | Rec. analyste: {fundamentals.get('analyst_rec','N/A')}"

        prompt = f"""Tu es un trader professionnel. Analyse cet actif et donne une recommandation.

ACTIF: {asset.upper()} ({'Crypto' if asset_type == 'crypto' else 'Action'})
RSI: {rsi:.1f} | Momentum 3h: {momentum:+.2f}%
Reddit: {reddit['ratio']*100:.0f}% positif sur {reddit['total']} posts ({reddit['label']})
Fear & Greed: {fg_str}
{f'Fondamentaux: {fund_str}' if fund_str else ''}

Actualités récentes:
{news_str}

Réponds UNIQUEMENT en JSON valide (sans markdown):
{{"action":"ACHAT","confiance":85,"resume":"momentum fort confirmé par sentiment positif"}}
action doit être "ACHAT", "VENTE" ou "NEUTRE"
confiance entre 0 et 100"""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=120,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        # Nettoie les éventuels backticks markdown
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)

    except Exception as e:
        print(f"[ai] Erreur analyse {asset}: {e}")
        return None
