"""Test de bout en bout d'un serveur déjà lancé (local, conteneur Docker ou Render).

Utilisation :
    python scripts/smoke_test.py [BASE_URL]

BASE_URL est lue en argument, sinon dans la variable d'environnement BASE_URL,
sinon vaut http://localhost:10000. Bibliothèque standard uniquement.

Le script attend que /health réponde (jusqu'à 180 s, le temps qu'un service Render
gratuit se réveille), puis déroule le CRUD complet en affichant une ligne par étape.
Il s'arrête au premier échec avec un code de sortie non nul et supprime toujours les
stages qu'il a créés, y compris en cas d'échec. Il ne suppose ni le nombre de stages
présents ni leurs ids.
"""

import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime

URL_PAR_DEFAUT = "http://localhost:10000"
ATTENTE_MAX_HEALTH = 180  # secondes
PAUSE_ENTRE_ESSAIS_HEALTH = 5  # secondes
TIMEOUT_REQUETE = 10  # secondes
ESSAIS_PAR_REQUETE = 3
PAUSE_ENTRE_ESSAIS = 3  # secondes
CODES_A_REESSAYER = {502, 503}

# Marqueur unique à cette exécution : il permet de retrouver et supprimer tout
# stage créé par le script, même si une réponse s'est perdue en route.
MARQUEUR = f"smoke-{uuid.uuid4().hex[:8]}"


class EchecEtape(Exception):
    """Une vérification du test de bout en bout a échoué."""


class Reponse:
    def __init__(self, status, corps):
        self.status = status
        self.corps = corps

    def json(self):
        return json.loads(self.corps.decode("utf-8"))

    def resume(self):
        texte = self.corps.decode("utf-8", errors="replace")
        return texte if len(texte) <= 300 else texte[:300] + "..."


def requete(base_url, methode, chemin, corps=None):
    """Envoie une requête HTTP ; réessaie sur 502, 503 et erreur réseau."""
    donnees = None if corps is None else json.dumps(corps).encode("utf-8")
    en_tetes = {"Accept": "application/json"}
    if donnees is not None:
        en_tetes["Content-Type"] = "application/json"

    derniere_erreur = None
    for essai in range(1, ESSAIS_PAR_REQUETE + 1):
        req = urllib.request.Request(base_url + chemin, data=donnees, headers=en_tetes, method=methode)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_REQUETE) as r:
                return Reponse(r.status, r.read())
        except urllib.error.HTTPError as e:
            reponse = Reponse(e.code, e.read())
            if e.code not in CODES_A_REESSAYER:
                return reponse
            derniere_erreur = f"HTTP {e.code}"
        except (OSError, http.client.HTTPException) as e:  # URLError, délai dépassé, connexion coupée
            derniere_erreur = f"erreur réseau ({getattr(e, 'reason', e)})"
        if essai < ESSAIS_PAR_REQUETE:
            time.sleep(PAUSE_ENTRE_ESSAIS)
    raise EchecEtape(f"{methode} {chemin} : pas de réponse exploitable après "
                     f"{ESSAIS_PAR_REQUETE} essais, dernière erreur : {derniere_erreur}")


def attendre_health(base_url):
    debut = time.monotonic()
    essais = 0
    derniere_erreur = None
    while True:
        essais += 1
        try:
            reponse = requete_unique_health(base_url)
            if reponse.status == 200 and reponse.json() == {"status": "ok"}:
                return essais, time.monotonic() - debut
            derniere_erreur = f"HTTP {reponse.status} {reponse.resume()}"
        except (OSError, http.client.HTTPException, ValueError) as e:
            derniere_erreur = f"erreur réseau ({getattr(e, 'reason', e)})"
        if time.monotonic() - debut + PAUSE_ENTRE_ESSAIS_HEALTH > ATTENTE_MAX_HEALTH:
            raise EchecEtape(f"/health ne répond pas après {essais} essais "
                             f"({time.monotonic() - debut:.0f} s), dernière erreur : {derniere_erreur}")
        time.sleep(PAUSE_ENTRE_ESSAIS_HEALTH)


def requete_unique_health(base_url):
    req = urllib.request.Request(base_url + "/health", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_REQUETE) as r:
            return Reponse(r.status, r.read())
    except urllib.error.HTTPError as e:
        return Reponse(e.code, e.read())


def verifier_statut(reponse, attendu, contexte):
    if reponse.status != attendu:
        raise EchecEtape(f"{contexte} : statut {reponse.status} au lieu de {attendu}, corps : {reponse.resume()}")


def stage_de_test(**modifications):
    """Stage entièrement fictif, marqué pour pouvoir être nettoyé."""
    corps = {
        "nom_etudiant": f"Etudiant Fictif {MARQUEUR}",
        "entreprise": "Entreprise Imaginaire",
        "intitule": "Stage de test automatique",
        "date_debut": "2026-03-02",
        "date_fin": "2026-08-28",
    }
    corps.update(modifications)
    return corps


def derouler(base_url, ids_crees, etape):
    essais, duree = attendre_health(base_url)
    etape(f"GET /health -> 200 {{\"status\": \"ok\"}} (après {essais} essai(s), {duree:.0f} s)")

    r = requete(base_url, "POST", "/stages", stage_de_test())
    verifier_statut(r, 201, "POST /stages")
    cree = r.json()
    stage_id = cree.get("id")
    if not isinstance(stage_id, int):
        raise EchecEtape(f"POST /stages : réponse sans id entier : {r.resume()}")
    ids_crees.append(stage_id)
    if {k: cree.get(k) for k in stage_de_test()} != stage_de_test():
        raise EchecEtape(f"POST /stages : le stage renvoyé ne correspond pas au corps envoyé : {r.resume()}")
    etape(f"POST /stages -> 201, stage créé avec l'id {stage_id}")

    r = requete(base_url, "GET", "/stages")
    verifier_statut(r, 200, "GET /stages")
    liste = r.json()
    if cree not in liste:
        raise EchecEtape(f"GET /stages : le stage {stage_id} est absent de la liste")
    etape(f"GET /stages -> 200, {len(liste)} stage(s), contient le stage {stage_id}")

    r = requete(base_url, "GET", f"/stages/{stage_id}")
    verifier_statut(r, 200, f"GET /stages/{stage_id}")
    if r.json() != cree:
        raise EchecEtape(f"GET /stages/{stage_id} : stage différent de celui créé : {r.resume()}")
    etape(f"GET /stages/{stage_id} -> 200, stage identique à celui créé")

    modifie = stage_de_test(intitule="Stage de test automatique (modifié)", date_fin="2026-09-30")
    r = requete(base_url, "PUT", f"/stages/{stage_id}", modifie)
    verifier_statut(r, 200, f"PUT /stages/{stage_id}")
    if r.json() != {"id": stage_id, **modifie}:
        raise EchecEtape(f"PUT /stages/{stage_id} : modification non appliquée : {r.resume()}")
    r = requete(base_url, "GET", f"/stages/{stage_id}")
    if r.status != 200 or r.json().get("intitule") != modifie["intitule"]:
        raise EchecEtape(f"PUT /stages/{stage_id} : modification non relue par GET : {r.resume()}")
    etape(f"PUT /stages/{stage_id} -> 200, intitulé et date de fin modifiés (relus par GET)")

    r = requete(base_url, "DELETE", f"/stages/{stage_id}")
    verifier_statut(r, 204, f"DELETE /stages/{stage_id}")
    if r.corps:
        raise EchecEtape(f"DELETE /stages/{stage_id} : corps non vide : {r.resume()}")
    ids_crees.remove(stage_id)
    etape(f"DELETE /stages/{stage_id} -> 204, corps vide")

    r = requete(base_url, "GET", f"/stages/{stage_id}")
    verifier_statut(r, 404, f"GET /stages/{stage_id} après suppression")
    etape(f"GET /stages/{stage_id} -> 404 {r.resume()}")

    # L'id du stage qui vient d'être supprimé est, par construction, inexistant.
    r = requete(base_url, "PUT", f"/stages/{stage_id}", stage_de_test())
    verifier_statut(r, 404, f"PUT /stages/{stage_id} (id inexistant)")
    etape(f"PUT /stages/{stage_id} (id inexistant) -> 404 {r.resume()}")

    r = requete(base_url, "DELETE", f"/stages/{stage_id}")
    verifier_statut(r, 404, f"DELETE /stages/{stage_id} (id inexistant)")
    etape(f"DELETE /stages/{stage_id} (id inexistant) -> 404 {r.resume()}")

    r = requete(base_url, "POST", "/stages", stage_de_test(date_debut="2026-08-28", date_fin="2026-03-02"))
    if r.status == 201:
        ids_crees.append(r.json().get("id"))
    verifier_statut(r, 422, "POST /stages avec date de fin avant date de début")
    etape("POST /stages avec date de fin avant date de début -> 422")


def nettoyer(base_url, ids_crees):
    """Supprime les stages créés par cette exécution ; renvoie un message de bilan."""
    a_supprimer = set(i for i in ids_crees if isinstance(i, int))
    try:
        r = requete(base_url, "GET", "/stages")
        if r.status == 200:
            a_supprimer |= {s["id"] for s in r.json() if MARQUEUR in str(s.get("nom_etudiant", ""))}
    except (EchecEtape, ValueError, KeyError, TypeError):
        pass  # on se contente des ids connus
    if not a_supprimer:
        return "rien à supprimer"
    restants = []
    for stage_id in sorted(a_supprimer):
        try:
            r = requete(base_url, "DELETE", f"/stages/{stage_id}")
            if r.status not in (204, 404):
                restants.append(stage_id)
        except EchecEtape:
            restants.append(stage_id)
    if restants:
        return f"ÉCHEC, stage(s) à supprimer à la main : {restants}"
    return f"stage(s) supprimé(s) : {sorted(a_supprimer)}"


def main():
    # Sortie en UTF-8 même redirigée vers un fichier sous Windows (sinon cp1252).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    base_url = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BASE_URL", URL_PAR_DEFAUT)).rstrip("/")

    print(f"Test de bout en bout de {base_url} ({datetime.now():%Y-%m-%d %H:%M:%S}, marqueur {MARQUEUR})")
    compteur = {"n": 0}

    def etape(message):
        compteur["n"] += 1
        print(f"[OK]    {compteur['n']:>2}. {message}", flush=True)

    ids_crees = []
    code_sortie = 0
    try:
        derouler(base_url, ids_crees, etape)
    except EchecEtape as e:
        print(f"[ECHEC] {compteur['n'] + 1:>2}. {e}", flush=True)
        code_sortie = 1
    except Exception as e:  # erreur inattendue (JSON invalide, etc.)
        print(f"[ECHEC] {compteur['n'] + 1:>2}. erreur inattendue : {type(e).__name__}: {e}", flush=True)
        code_sortie = 1
    finally:
        # Toujours exécuté : retrouve aussi, grâce au marqueur, un éventuel doublon
        # créé par un réessai de POST dont la première réponse s'est perdue.
        bilan = nettoyer(base_url, ids_crees)
        print(f"Nettoyage : {bilan}", flush=True)
        if bilan.startswith("ÉCHEC"):
            code_sortie = 1

    if code_sortie == 0:
        print(f"Résultat : SUCCÈS, {compteur['n']} étapes réussies.")
    else:
        print(f"Résultat : ÉCHEC après {compteur['n']} étape(s) réussie(s).")
    return code_sortie


if __name__ == "__main__":
    sys.exit(main())
