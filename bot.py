# =====================================================
#  BOT VINTED -> DISCORD  (version GitHub Actions v2)
# =====================================================
import os
import json
import time
import requests
from vinted_scraper import VintedWrapper

# =====================================================
#  ✏️ TES RÉGLAGES : MODIFIE UNIQUEMENT CETTE PARTIE
# =====================================================

# 👉 LA MARQUE (écris-la entre guillemets)
# Une marque :   MARQUES = ["Montbell"]
# Plusieurs :    MARQUES = ["Nike", "Adidas"]
# Toutes :       MARQUES = []
MARQUES = ["Montbell"]

# Mot en plus pour préciser (facultatif). "" = tous les articles.
MOTS_CLES = ""

# Prix maximum en euros (0 = pas de limite)
PRIX_MAX = 120

# Prix minimum en euros (0 = pas de minimum)
PRIX_MIN = 0

# Tailles acceptées. [] = toutes. Exemples : ["M", "L"] ou ["42"]
TAILLES = []

# Pays de Vinted : "https://www.vinted.fr", "https://www.vinted.be"...
SITE = "https://www.vinted.fr"

# True = au tout premier lancement, envoie 3 articles pour TESTER.
TESTER_AU_DEMARRAGE = True

# =====================================================
#  🛠️ LE RESTE : PAS BESOIN DE TOUCHER
# =====================================================

WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")
FICHIER_MEMOIRE = "seen.json"


def chercher(vinted, texte):
    """Demande à Vinted les articles les plus récents."""
    params = {
        "search_text": texte,
        "order": "newest_first",
        "per_page": 30,
        "page": 1,
    }
    if PRIX_MAX:
        params["price_to"] = PRIX_MAX
    if PRIX_MIN:
        params["price_from"] = PRIX_MIN
    reponse = vinted.search(params)
    if isinstance(reponse, dict):
        return reponse.get("items", [])
    return reponse or []


def marque_ok(a):
    if not MARQUES:
        return True
    marque = str(a.get("brand_title", "")).strip().lower()
    return marque in [m.strip().lower() for m in MARQUES]


def chercher_tout(vinted):
    if not MARQUES:
        return chercher(vinted, MOTS_CLES)
    resultats = {}
    for marque in MARQUES:
        texte = f"{marque} {MOTS_CLES}".strip()
        for a in chercher(vinted, texte):
            if marque_ok(a):
                resultats[a["id"]] = a
        time.sleep(2)
    return sorted(resultats.values(), key=lambda x: x["id"], reverse=True)


def taille_ok(a):
    if not TAILLES:
        return True
    return str(a.get("size_title", "")).upper() in [t.upper() for t in TAILLES]


def lire_prix(a):
    p = a.get("price")
    if isinstance(p, dict):
        return f"{p.get('amount', '?')} {p.get('currency_code', '€')}"
    return f"{p} €"


def envoyer_discord(a):
    titre = a.get("title", "Sans titre")
    prix = lire_prix(a)
    taille = a.get("size_title") or "Non précisée"
    marque = a.get("brand_title") or "Non précisée"
    lien = a.get("url") or f"{SITE}/items/{a.get('id')}"
    if lien.startswith("/"):
        lien = SITE + lien
    photo = (a.get("photo") or {}).get("url")

    donnees = {
        "content": f"🆕 {marque} | {titre} | {prix} | Taille {taille}",
        "embeds": [{
            "title": titre,
            "url": lien,
            "color": 3066993,
            "fields": [
                {"name": "🏷️ Marque", "value": str(marque), "inline": True},
                {"name": "💰 Prix", "value": prix, "inline": True},
                {"name": "📏 Taille", "value": str(taille), "inline": True},
            ],
        }],
    }
    if photo:
        donnees["embeds"][0]["thumbnail"] = {"url": photo}

    r = requests.post(WEBHOOK, json=donnees, timeout=20)
    if r.status_code == 429:
        time.sleep(3)
    elif r.status_code >= 400:
        raise SystemExit("Discord a refusé : vérifie ton secret DISCORD_WEBHOOK_URL")


def main():
    if not WEBHOOK:
        raise SystemExit("Secret DISCORD_WEBHOOK_URL introuvable")

    premier_lancement = not os.path.exists(FICHIER_MEMOIRE)
    if premier_lancement:
        deja_vus = []
    else:
        with open(FICHIER_MEMOIRE) as f:
            deja_vus = json.load(f)

    vinted = VintedWrapper(SITE)
    articles = chercher_tout(vinted)
    print(f"🔎 {len(articles)} articles trouvés")
    if articles:
        # Aide au dépannage : montre les champs reçus de Vinted
        print("Champs du 1er article :", sorted(articles[0].keys()))

    if premier_lancement:
        if TESTER_AU_DEMARRAGE:
            for a in [x for x in articles if taille_ok(x)][:3]:
                envoyer_discord(a)
        deja_vus = [a["id"] for a in articles]
    else:
        for a in reversed(articles):
            if a["id"] not in deja_vus:
                deja_vus.append(a["id"])
                if taille_ok(a):
                    envoyer_discord(a)
                    print("📨 Notification :", a.get("title"))

    with open(FICHIER_MEMOIRE, "w") as f:
        json.dump(deja_vus[-500:], f)


if __name__ == "__main__":
    main()

