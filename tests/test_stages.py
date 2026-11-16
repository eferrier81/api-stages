"""Tests de l'API de gestion des stages, écrits d'après le contrat du plan (sections 1 et 8).

Chaque test reçoit, via la fixture ``client``, une base neuve contenant exactement
les 3 stages d'exemple (ids 1 à 3). Toutes les données utilisées ici sont fictives.
"""

from datetime import date

import pytest

ID_INEXISTANT = 999999

ORDRE_DES_CHAMPS = ["id", "nom_etudiant", "entreprise", "intitule", "date_debut", "date_fin"]
CHAMPS_DU_CORPS = ORDRE_DES_CHAMPS[1:]
CHAMPS_TEXTE = ["nom_etudiant", "entreprise", "intitule"]
CORPS_404 = {"detail": "Stage introuvable"}


def stage_valide(**modifications):
    """Corps de POST ou PUT valide (sans id), éventuellement modifié."""
    corps = {
        "nom_etudiant": "Jeanne Exemple",
        "entreprise": "Société Imaginaire",
        "intitule": "Mise en place d'une chaîne MLOps",
        "date_debut": "2026-03-02",
        "date_fin": "2026-08-28",
    }
    corps.update(modifications)
    return corps


def nombre_de_stages(client):
    return len(client.get("/stages").json())


# --- GET / et GET /health ---------------------------------------------------


def test_accueil_renvoie_le_message_et_le_lien_vers_la_documentation(client):
    reponse = client.get("/")

    assert reponse.status_code == 200
    assert reponse.json() == {"message": "API de gestion des stages", "docs": "/docs"}


def test_health_renvoie_status_ok(client):
    reponse = client.get("/health")

    assert reponse.status_code == 200
    assert reponse.json() == {"status": "ok"}


def test_documentation_swagger_et_schema_openapi_sont_disponibles(client):
    assert client.get("/docs").status_code == 200

    reponse = client.get("/openapi.json")
    assert reponse.status_code == 200
    schema = reponse.json()
    assert schema["info"]["title"] == "API de gestion des stages"
    tags_des_routes_stages = [
        operation.get("tags", [])
        for chemin, operations in schema["paths"].items()
        if chemin.startswith("/stages")
        for operation in operations.values()
    ]
    assert tags_des_routes_stages
    assert all("stages" in tags for tags in tags_des_routes_stages)


# --- GET /stages -------------------------------------------------------------


def test_une_base_neuve_contient_exactement_les_3_stages_d_exemple(client):
    reponse = client.get("/stages")

    assert reponse.status_code == 200
    stages = reponse.json()
    assert isinstance(stages, list)
    assert [stage["id"] for stage in stages] == [1, 2, 3]


def test_les_stages_d_exemple_sont_complets_et_coherents(client):
    for stage in client.get("/stages").json():
        assert list(stage.keys()) == ORDRE_DES_CHAMPS
        for champ in CHAMPS_TEXTE:
            assert stage[champ] != ""
            assert stage[champ] == stage[champ].strip()
        assert date.fromisoformat(stage["date_debut"]) <= date.fromisoformat(stage["date_fin"])


def test_la_liste_des_stages_reste_triee_par_id_apres_des_modifications(client):
    client.post("/stages", json=stage_valide())
    client.put("/stages/1", json=stage_valide(entreprise="Atelier Fictif"))
    client.post("/stages", json=stage_valide())

    ids = [stage["id"] for stage in client.get("/stages").json()]

    assert ids == [1, 2, 3, 4, 5]


# --- GET /stages/{id} --------------------------------------------------------


def test_lire_un_stage_existant_renvoie_200_et_le_stage(client):
    stage_dans_la_liste = client.get("/stages").json()[0]

    reponse = client.get(f"/stages/{stage_dans_la_liste['id']}")

    assert reponse.status_code == 200
    assert reponse.json() == stage_dans_la_liste
    assert list(reponse.json().keys()) == ORDRE_DES_CHAMPS


def test_lire_un_stage_inexistant_renvoie_404(client):
    reponse = client.get(f"/stages/{ID_INEXISTANT}")

    assert reponse.status_code == 404
    assert reponse.json() == CORPS_404


# --- POST /stages ------------------------------------------------------------


def test_creer_un_stage_renvoie_201_et_le_stage_avec_son_id(client):
    reponse = client.post("/stages", json=stage_valide())

    assert reponse.status_code == 201
    cree = reponse.json()
    assert list(cree.keys()) == ORDRE_DES_CHAMPS
    assert {champ: cree[champ] for champ in CHAMPS_DU_CORPS} == stage_valide()


def test_le_premier_stage_cree_sur_une_base_neuve_recoit_l_id_4(client):
    reponse = client.post("/stages", json=stage_valide())

    assert reponse.json()["id"] == 4


def test_un_stage_cree_est_ensuite_lisible_et_present_dans_la_liste(client):
    cree = client.post("/stages", json=stage_valide()).json()

    assert client.get(f"/stages/{cree['id']}").json() == cree
    assert cree in client.get("/stages").json()
    assert nombre_de_stages(client) == 4


def test_creer_un_stage_supprime_les_espaces_de_bord_des_chaines(client):
    corps = stage_valide(
        nom_etudiant="  Jeanne Exemple  ",
        entreprise="\tSociété Imaginaire ",
        intitule=" Mise en place d'une chaîne MLOps\n",
    )

    cree = client.post("/stages", json=corps).json()

    assert cree["nom_etudiant"] == "Jeanne Exemple"
    assert cree["entreprise"] == "Société Imaginaire"
    assert cree["intitule"] == "Mise en place d'une chaîne MLOps"
    assert client.get(f"/stages/{cree['id']}").json() == cree


def test_creer_un_stage_ignore_les_champs_inconnus(client):
    corps = stage_valide(champ_inconnu="valeur ignorée")

    reponse = client.post("/stages", json=corps)

    assert reponse.status_code == 201
    assert "champ_inconnu" not in reponse.json()


def test_creer_un_stage_ignore_un_id_fourni_dans_le_corps(client):
    stage_1_avant = client.get("/stages/1").json()

    reponse = client.post("/stages", json=stage_valide(id=1))

    assert reponse.status_code == 201
    assert reponse.json()["id"] == 4
    assert client.get("/stages/1").json() == stage_1_avant


def test_un_stage_d_une_seule_journee_est_accepte(client):
    corps = stage_valide(date_debut="2026-05-15", date_fin="2026-05-15")

    reponse = client.post("/stages", json=corps)

    assert reponse.status_code == 201


def test_une_chaine_de_200_caracteres_est_acceptee(client):
    reponse = client.post("/stages", json=stage_valide(intitule="a" * 200))

    assert reponse.status_code == 201
    assert reponse.json()["intitule"] == "a" * 200


# --- POST /stages : erreurs de validation (422) -------------------------------


def test_creer_un_stage_avec_date_de_fin_avant_date_de_debut_renvoie_422(client):
    corps = stage_valide(date_debut="2026-08-28", date_fin="2026-03-02")

    reponse = client.post("/stages", json=corps)

    assert reponse.status_code == 422
    assert "detail" in reponse.json()
    assert nombre_de_stages(client) == 3


@pytest.mark.parametrize("champ", CHAMPS_TEXTE)
def test_creer_un_stage_avec_un_champ_texte_vide_renvoie_422(client, champ):
    reponse = client.post("/stages", json=stage_valide(**{champ: ""}))

    assert reponse.status_code == 422
    assert nombre_de_stages(client) == 3


@pytest.mark.parametrize("champ", CHAMPS_TEXTE)
def test_creer_un_stage_avec_un_champ_texte_fait_d_espaces_renvoie_422(client, champ):
    reponse = client.post("/stages", json=stage_valide(**{champ: "   "}))

    assert reponse.status_code == 422
    assert nombre_de_stages(client) == 3


@pytest.mark.parametrize("champ", CHAMPS_TEXTE)
def test_creer_un_stage_avec_un_champ_texte_de_plus_de_200_caracteres_renvoie_422(client, champ):
    reponse = client.post("/stages", json=stage_valide(**{champ: "a" * 201}))

    assert reponse.status_code == 422
    assert nombre_de_stages(client) == 3


@pytest.mark.parametrize("champ", CHAMPS_DU_CORPS)
def test_creer_un_stage_avec_un_champ_manquant_renvoie_422(client, champ):
    corps = stage_valide()
    del corps[champ]

    reponse = client.post("/stages", json=corps)

    assert reponse.status_code == 422
    assert nombre_de_stages(client) == 3


@pytest.mark.parametrize("champ_date", ["date_debut", "date_fin"])
@pytest.mark.parametrize("date_mal_formee", ["02/03/2026", "2026-13-01", "pas une date"])
def test_creer_un_stage_avec_une_date_mal_formee_renvoie_422(client, champ_date, date_mal_formee):
    reponse = client.post("/stages", json=stage_valide(**{champ_date: date_mal_formee}))

    assert reponse.status_code == 422
    assert nombre_de_stages(client) == 3


# --- PUT /stages/{id} --------------------------------------------------------


def test_modifier_un_stage_existant_renvoie_200_et_le_stage_modifie(client):
    corps = stage_valide(entreprise="Atelier Fictif", date_fin="2026-09-30")

    reponse = client.put("/stages/2", json=corps)

    assert reponse.status_code == 200
    assert reponse.json() == {"id": 2, **corps}
    assert list(reponse.json().keys()) == ORDRE_DES_CHAMPS


def test_une_modification_est_conservee_et_ne_touche_pas_les_autres_stages(client):
    avant = client.get("/stages").json()

    client.put("/stages/2", json=stage_valide())

    apres = client.get("/stages").json()
    assert client.get("/stages/2").json() == {"id": 2, **stage_valide()}
    assert [s for s in apres if s["id"] != 2] == [s for s in avant if s["id"] != 2]
    assert len(apres) == 3


def test_modifier_un_stage_conserve_son_id_meme_si_le_corps_en_fournit_un_autre(client):
    stage_3_avant = client.get("/stages/3").json()

    reponse = client.put("/stages/2", json=stage_valide(id=3))

    assert reponse.status_code == 200
    assert reponse.json()["id"] == 2
    assert client.get("/stages/3").json() == stage_3_avant


def test_modifier_un_stage_supprime_les_espaces_de_bord_des_chaines(client):
    reponse = client.put("/stages/1", json=stage_valide(nom_etudiant="  Jeanne Exemple  "))

    assert reponse.json()["nom_etudiant"] == "Jeanne Exemple"


def test_modifier_un_stage_inexistant_renvoie_404(client):
    reponse = client.put(f"/stages/{ID_INEXISTANT}", json=stage_valide())

    assert reponse.status_code == 404
    assert reponse.json() == CORPS_404
    assert nombre_de_stages(client) == 3


def test_modifier_un_stage_avec_date_de_fin_avant_date_de_debut_renvoie_422(client):
    avant = client.get("/stages/1").json()
    corps = stage_valide(date_debut="2026-08-28", date_fin="2026-03-02")

    reponse = client.put("/stages/1", json=corps)

    assert reponse.status_code == 422
    assert client.get("/stages/1").json() == avant


def test_modifier_un_stage_avec_un_champ_manquant_renvoie_422(client):
    """PUT est un remplacement complet : les 5 champs sont obligatoires."""
    corps = stage_valide()
    del corps["intitule"]

    reponse = client.put("/stages/1", json=corps)

    assert reponse.status_code == 422


def test_modifier_un_stage_avec_un_champ_texte_fait_d_espaces_renvoie_422(client):
    reponse = client.put("/stages/1", json=stage_valide(entreprise="   "))

    assert reponse.status_code == 422


# --- DELETE /stages/{id} -----------------------------------------------------


def test_supprimer_un_stage_existant_renvoie_204_avec_un_corps_vide(client):
    reponse = client.delete("/stages/3")

    assert reponse.status_code == 204
    assert reponse.content == b""


def test_un_stage_supprime_n_est_plus_lisible_ni_dans_la_liste(client):
    client.delete("/stages/3")

    assert client.get("/stages/3").status_code == 404
    assert [stage["id"] for stage in client.get("/stages").json()] == [1, 2]


def test_supprimer_un_stage_inexistant_renvoie_404(client):
    reponse = client.delete(f"/stages/{ID_INEXISTANT}")

    assert reponse.status_code == 404
    assert reponse.json() == CORPS_404
    assert nombre_de_stages(client) == 3


def test_supprimer_deux_fois_le_meme_stage_renvoie_404_la_seconde_fois(client):
    assert client.delete("/stages/1").status_code == 204

    reponse = client.delete("/stages/1")

    assert reponse.status_code == 404
    assert reponse.json() == CORPS_404


# --- Identifiant non entier dans le chemin (422) ------------------------------


@pytest.mark.parametrize("methode", ["GET", "PUT", "DELETE"])
def test_un_id_non_entier_dans_le_chemin_renvoie_422(client, methode):
    corps = stage_valide() if methode == "PUT" else None

    reponse = client.request(methode, "/stages/abc", json=corps)

    assert reponse.status_code == 422
    assert nombre_de_stages(client) == 3
