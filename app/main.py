"""Application FastAPI : déclaration des routes de l'API de gestion des stages."""

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path, Response, status

from app.database import COLONNES, initialiser_base, ouvrir_connexion
from app.schemas import MessageErreur, Stage, StageEntree


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Au démarrage : création de la table et insertion des données d'exemple si besoin."""
    initialiser_base()
    yield


app = FastAPI(
    title="API de gestion des stages",
    description=(
        "API REST permettant de consulter, créer, modifier et supprimer des stages "
        "d'étudiants. Les données d'exemple sont fictives."
    ),
    version="1.0.0",
    openapi_tags=[
        {"name": "stages", "description": "Opérations CRUD sur les stages."},
        {"name": "général", "description": "Accueil et état du service."},
    ],
    lifespan=lifespan,
)

# Réponse 404 commune aux routes qui reçoivent un identifiant.
REPONSE_404 = {404: {"model": MessageErreur, "description": "Stage introuvable"}}

# Paramètre de chemin commun : un id non entier est refusé avec une erreur 422.
IdStage = Annotated[int, Path(description="Identifiant du stage", examples=[1])]


def stage_introuvable() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stage introuvable")


@app.get("/", tags=["général"], summary="Message d'accueil")
def accueil():
    """Indique le nom de l'API et l'adresse de sa documentation interactive."""
    return {"message": "API de gestion des stages", "docs": "/docs"}


@app.get("/health", tags=["général"], summary="État du service")
def sante():
    """Répond `{"status": "ok"}` tant que le service fonctionne (utilisé par Render)."""
    return {"status": "ok"}


@app.get("/stages", response_model=list[Stage], tags=["stages"], summary="Lister les stages")
def lister_stages():
    """Renvoie tous les stages, triés par identifiant croissant."""
    with ouvrir_connexion() as connexion:
        lignes = connexion.execute(f"SELECT {COLONNES} FROM stages ORDER BY id").fetchall()
    return [dict(ligne) for ligne in lignes]


@app.get(
    "/stages/{id}",
    response_model=Stage,
    responses=REPONSE_404,
    tags=["stages"],
    summary="Consulter un stage",
)
def lire_stage(id: IdStage):
    """Renvoie le stage correspondant à l'identifiant, ou une erreur 404 s'il n'existe pas."""
    with ouvrir_connexion() as connexion:
        ligne = connexion.execute(f"SELECT {COLONNES} FROM stages WHERE id = ?", (id,)).fetchone()
    if ligne is None:
        raise stage_introuvable()
    return dict(ligne)


@app.post(
    "/stages",
    response_model=Stage,
    status_code=status.HTTP_201_CREATED,
    tags=["stages"],
    summary="Créer un stage",
)
def creer_stage(stage: StageEntree):
    """Enregistre un nouveau stage et le renvoie avec l'identifiant attribué.

    Les cinq champs sont obligatoires ; la date de fin ne peut pas précéder la date de début.
    """
    with ouvrir_connexion() as connexion:
        curseur = connexion.execute(
            "INSERT INTO stages (nom_etudiant, entreprise, intitule, date_debut, date_fin) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                stage.nom_etudiant,
                stage.entreprise,
                stage.intitule,
                stage.date_debut.isoformat(),
                stage.date_fin.isoformat(),
            ),
        )
        nouvel_id = curseur.lastrowid
    return Stage(id=nouvel_id, **stage.model_dump())


@app.put(
    "/stages/{id}",
    response_model=Stage,
    responses=REPONSE_404,
    tags=["stages"],
    summary="Modifier un stage",
)
def modifier_stage(stage: StageEntree, id: IdStage):
    """Remplace entièrement le stage indiqué (les cinq champs sont obligatoires).

    L'identifiant est conservé ; erreur 404 si le stage n'existe pas.
    """
    with ouvrir_connexion() as connexion:
        curseur = connexion.execute(
            "UPDATE stages SET nom_etudiant = ?, entreprise = ?, intitule = ?, "
            "date_debut = ?, date_fin = ? WHERE id = ?",
            (
                stage.nom_etudiant,
                stage.entreprise,
                stage.intitule,
                stage.date_debut.isoformat(),
                stage.date_fin.isoformat(),
                id,
            ),
        )
        trouve = curseur.rowcount > 0
    if not trouve:
        raise stage_introuvable()
    return Stage(id=id, **stage.model_dump())


@app.delete(
    "/stages/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=REPONSE_404,
    tags=["stages"],
    summary="Supprimer un stage",
)
def supprimer_stage(id: IdStage):
    """Supprime le stage indiqué. Réponse 204 sans corps, ou 404 si le stage n'existe pas."""
    with ouvrir_connexion() as connexion:
        curseur = connexion.execute("DELETE FROM stages WHERE id = ?", (id,))
        trouve = curseur.rowcount > 0
    if not trouve:
        raise stage_introuvable()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
