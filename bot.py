# =====================================================
#  BOT VINTED -> DISCORD  (version GitHub Actions v4)
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
TAILLES = ["M"]

# Pays de Vinted : "https://www.vinted.fr", "https://www.vinted.be"...
SITE = "https://www.vinted.fr"

# True = au tout premier lancement, envoie 3 articles pour TESTER.
TESTER_AU_DEMARRAGE = False

# =====================================================
#  🛠️ LE RESTE : PAS BESOIN DE TOUCHER
# =====================================================

WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")
FICHIER_MEMOIRE = "seen.json"


def extraire_items(reponse):
    """Retrouve la liste d'articles, quel que soit le format de Vinted."""
    if isinstance(reponse, list):
        return reponse
    if isinstance(reponse, dict):
        for cle in ("items", "catalog_items", "data"):
            if isinstance(reponse.get(cle), list):
                return reponse[cle]
        for valeur in reponse.values():
            if (isinstance(valeur, list) and valeur
                    and isinstance(valeur[0], dict)):
                return valeur
        print("⚠️ Format inconnu. Clés reçues :", list(reponse.keys()))
    return []


def chercher(vinted, texte):
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
    return extraire_items(vinted.search(params))


def infos(a):
    """Lit marque, taille et état (dans item_box, ou à l'ancienne)."""
    box = a.get("item_box")
    if not isinstance(box, dict):
        box = {}
    marque = box.get("first_line") or a.get("brand_title") or "Non précisée"
    ligne2 = box.get("second_line") or ""
    morceaux = [m.strip() for m in str(ligne2).split("·")]
    taille = a.get("size_title") or (morceaux[0] if morceaux[0] else "Non précisée")
    etat = morceaux[1] if len(morceaux) > 1 else ""
    return str(marque), str(taille), str(etat)


def marque_ok(a):
    if not MARQUES:
        return True
    marque, _, _ = infos(a)
    texte = f"{marque} {a.get('title', '')}".lower()
    return any(m.strip().lower() in texte for m in MARQUES)


def taille_ok(a):
    if not TAILLES:
        return True
    _, taille, _ = infos(a)
    return taille.upper() in [t.upper() for t in TAILLES]


def chercher_tout(vinted):
    if not MARQUES:
        return chercher(vinted, MOTS_CLES)
    resultats = {}
    for marque in MARQUES:
        texte = f"{marque} {MOTS_CLES}".strip()
        bruts = chercher(vinted, texte)
        print(f"Vinted a renvoyé {len(bruts)} articles pour « {texte} »")
        if bruts:
            print("item_box du 1er article :", bruts[0].get("item_box"))
            print("prix du 1er article :", bruts[0].get("price"))
        for a in bruts:
            if marque_ok(a):
                resultats[a["id"]] = a
        time.sleep(2)
    return sorted(resultats.values(), key=lambda x: x["id"], reverse=True)


def lire_prix(a):
    p = a.get("price")
    if isinstance(p, dict):
        return f"{p.get('amount', '?')} {p.get('currency_code', '€')}"
    return f"{p} €"


def envoyer_discord(a):
    titre = a.get("title", "Sans titre")
    prix = lire_prix(a)
    marque, taille, etat = infos(a)
    lien = a.get("url") or f"{SITE}/items/{a.get('id')}"
    if lien.startswith("/"):
        lien = SITE + lien
    photo = a.get("photo")
    photo = photo.get("url") if isinstance(photo, dict) else None

    champs = [
        {"name": "🏷️ Marque", "value": marque, "inline": True},
        {"name": "💰 Prix", "value": prix, "inline": True},
        {"name": "📏 Taille", "value": taille, "inline": True},
    ]
    if etat:
        champs.append({"name": "✨ État", "value": etat, "inline": True})

    donnees = {
        "content": f"🆕 {marque} | {titre} | {prix} | Taille {taille}",
        "embeds": [{
            "title": titre,
            "url": lien,
            "color": 3066993,
            "fields": champs,
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

    if not articles:
        print("Aucun article : rien à faire ce tour-ci.")
        return

    if premier_lancement:
        print("Premier lancement : test activé =", TESTER_AU_DEMARRAGE)
        if TESTER_AU_DEMARRAGE:
            for a in [x for x in articles if taille_ok(x)][:3]:
                envoyer_discord(a)
                print("📨 Test envoyé :", a.get("title"))
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
