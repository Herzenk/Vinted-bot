# =====================================================
#  BOT VINTED -> DISCORD  (version GitHub Actions)
# =====================================================
import os
import json
import time
import requests

# =====================================================
#  ✏️ TES RÉGLAGES : MODIFIE UNIQUEMENT CETTE PARTIE
# =====================================================

# 👉 LA MARQUE : écris son nom entre guillemets.
# Une seule marque :   MARQUES = ["Nike"]
# Plusieurs marques :  MARQUES = ["Nike", "Adidas", "Levi's"]
# Toutes les marques : MARQUES = []
MARQUES = ["Montbell"]

# Mot en plus pour préciser (facultatif). Exemples : "air max", "veste"
# Laisse "" (vide) pour avoir TOUS les articles de la marque.
MOTS_CLES = ""

# Prix maximum en euros (0 = pas de limite)
PRIX_MAX = 120

# Prix minimum en euros (0 = pas de minimum)
PRIX_MIN = 0

# Tailles acceptées. [] = toutes. Exemples : ["M", "L"] ou ["42"]
TAILLES = ["M"]

# Pays de Vinted : "www.vinted.fr", "www.vinted.be", etc.
DOMAINE = "www.vinted.fr"

# True = au tout premier lancement, envoie 3 articles pour TESTER.
# Quand tu as reçu les 3 messages, passe à False.
TESTER_AU_DEMARRAGE = True

# =====================================================
#  🛠️ LE RESTE : PAS BESOIN DE TOUCHER
# =====================================================

WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")
FICHIER_MEMOIRE = "seen.json"


def nouvelle_session():
    """Fait semblant d'être un navigateur pour que Vinted réponde."""
    s = requests.Session()
    s.headers.update({
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0 Safari/537.36"),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "fr-FR,fr;q=0.9",
    })
    s.get(f"https://{DOMAINE}", timeout=20)
    return s


def chercher(session, texte):
    """Cherche un texte sur Vinted, du plus récent au plus ancien."""
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
    r = session.get(f"https://{DOMAINE}/api/v2/catalog/items",
                    params=params, timeout=20)
    r.raise_for_status()
    return r.json().get("items", [])


def chercher_tout(session):
    """Fait une recherche par marque et rassemble les résultats."""
    if not MARQUES:
        return chercher(session, MOTS_CLES)

    resultats = {}
    for marque in MARQUES:
        texte = f"{marque} {MOTS_CLES}".strip()
        for a in chercher(session, texte):
            if marque_ok(a):  # garde seulement la VRAIE marque
                resultats[a["id"]] = a
        time.sleep(2)  # petite pause entre deux marques
    # Du plus récent au plus ancien (les numéros les plus grands = les plus récents)
    return sorted(resultats.values(), key=lambda x: x["id"], reverse=True)


def marque_ok(a):
    if not MARQUES:
        return True
    marque = str(a.get("brand_title", "")).strip().lower()
    return marque in [m.strip().lower() for m in MARQUES]


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
    lien = a.get("url") or f"https://{DOMAINE}/items/{a.get('id')}"
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

    articles = chercher_tout(nouvelle_session())
    print(f"🔎 {len(articles)} articles trouvés")

    if premier_lancement:
        if TESTER_AU_DEMARRAGE:
            for a in [x for x in articles if taille_ok(x)][:3]:
                envoyer_discord(a)
        deja_vus = [a["id"] for a in articles]
    else:
        for a in reversed(articles):  # du plus ancien au plus récent
            if a["id"] not in deja_vus:
                deja_vus.append(a["id"])
                if taille_ok(a):
                    envoyer_discord(a)
                    print("📨 Notification :", a.get("title"))

    with open(FICHIER_MEMOIRE, "w") as f:
        json.dump(deja_vus[-500:], f)


if __name__ == "__main__":
    main()
