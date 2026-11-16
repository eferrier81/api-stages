"""Modèles Pydantic : validation des corps de requête et forme des réponses."""

from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationInfo, field_validator

# Chaîne débarrassée de ses espaces de bord, non vide, 200 caractères au plus.
Texte = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class StageEntree(BaseModel):
    """Corps attendu par POST et PUT : les cinq champs d'un stage, sans l'identifiant."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "nom_etudiant": "Inès Garnier",
                    "entreprise": "Datavera",
                    "intitule": "Mise en place d'un pipeline MLOps",
                    "date_debut": "2026-02-09",
                    "date_fin": "2026-08-07",
                }
            ]
        }
    )

    nom_etudiant: Texte = Field(description="Nom complet de l'étudiant")
    entreprise: Texte = Field(description="Entreprise d'accueil")
    intitule: Texte = Field(description="Intitulé du stage")
    date_debut: date = Field(description="Date de début (AAAA-MM-JJ)")
    date_fin: date = Field(description="Date de fin (AAAA-MM-JJ), postérieure ou égale à la date de début")

    @field_validator("date_fin")
    @classmethod
    def verifier_ordre_des_dates(cls, date_fin: date, info: ValidationInfo) -> date:
        """Refuse une date de fin antérieure à la date de début."""
        date_debut = info.data.get("date_debut")  # absente si elle-même invalide
        if date_debut is not None and date_fin < date_debut:
            raise ValueError("la date de fin doit être postérieure ou égale à la date de début")
        return date_fin


class Stage(BaseModel):
    """Stage tel que renvoyé par l'API."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "nom_etudiant": "Alice Martin",
                    "entreprise": "TechNova",
                    "intitule": "Développement d'une API REST",
                    "date_debut": "2026-02-02",
                    "date_fin": "2026-07-31",
                }
            ]
        }
    )

    id: int = Field(description="Identifiant attribué par l'API")
    nom_etudiant: str
    entreprise: str
    intitule: str
    date_debut: date
    date_fin: date


class MessageErreur(BaseModel):
    """Corps des réponses d'erreur 404."""

    model_config = ConfigDict(json_schema_extra={"examples": [{"detail": "Stage introuvable"}]})

    detail: str
