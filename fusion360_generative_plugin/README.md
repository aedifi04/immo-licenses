# Fusion 360 — Generative Design & Pieds Contour Base

Plugin (Add-In) Fusion 360 offrant deux outils dans l'espace **Solid Design** :

---

## Outils disponibles

### 1. Generative Design Sommaire
Panneau de configuration rapide pour lancer une étude de conception générative :
- Sélection du **corps à préserver** (le solide de départ)
- Sélection des **corps obstacles** (zones interdites)
- Définition d'une **force** (magnitude + direction)
- Définition des **faces fixes** (contraintes d'encastrement)
- Cible de **réduction de masse** en %
- Choix de la **méthode de fabrication** et du **matériau**

Si l'API Generative Design est disponible, l'étude est créée automatiquement.  
Sinon, le plugin affiche un résumé à copier dans l'interface native Generative Design.

---

### 2. Pieds Contour Base (Détoureur / Contoureur)
Crée des pieds dont le **sommet épouse parfaitement le contour de la face inférieure** d'un objet.

**Paramètres :**
| Paramètre | Description |
|---|---|
| Corps cible | L'objet (cube, pièce quelconque) |
| Nombre de pieds | 2 à 8 |
| Hauteur | Hauteur totale de chaque pied |
| Rayon | Rayon (ou demi-largeur pour rectangulaire) |
| Style | Cylindrique / Conique (effilé) / Rectangulaire |
| Positionnement | Coins · Circulaire · Bords symétriques |
| Retrait du bord | Distance entre le bord de la base et le centre du pied |

**Comment ça marche (algorithme) :**
1. Le plugin détecte la face la plus basse du corps (Z minimum de la bounding box).
2. Crée un plan de construction à `(Z_base − hauteur_pied)`.
3. Crée chaque pied légèrement plus haut que la base (`+0.5 mm`) pour garantir l'intersection avec le corps.
4. Applique un **Boolean Cut** : le corps principal coupe le sommet de chaque pied.
5. Résultat : le sommet de chaque pied suit **exactement** la surface inférieure du corps, même si elle est courbe ou irrégulière.

---

## Installation

1. Copier ce dossier (`fusion360_generative_plugin/`) dans :
   - **Windows :** `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\`
   - **macOS :** `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/`

2. Dans Fusion 360 : **Outils → Add-Ins → Scripts and Add-Ins**

3. Onglet **Add-Ins** → trouver `fusion360_generative_plugin` → ☑ Activer

4. Les deux boutons apparaissent dans **Solid → Créer**.

---

## Compatibilité

| Élément | Requis |
|---|---|
| Fusion 360 | 2.0.14000+ |
| Python API | 3.x (intégré Fusion) |
| Generative Design API | 2.0.14700+ (optionnel, fallback message sinon) |
