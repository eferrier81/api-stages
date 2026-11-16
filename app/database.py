"""Accès à la base SQLite : connexion, création de la table et données d'exemple."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

# Colonnes renvoyées par les requêtes SELECT, dans l'ordre du contrat de l'API.
COLONNES = "id, nom_etudiant, entreprise, intitule, date_debut, date_fin"

# Stages fictifs insérés au démarrage si la table est vide (personnes et entreprises inventées).
STAGES_EXEMPLE = [
    (1, "Alice Martin", "TechNova", "Développement d'une API REST", "2026-02-02", "2026-07-31"),
    (2, "Bastien Leroy", "AgriSens", "Tableau de bord de suivi des cultures", "2026-03-02", "2026-08-28"),
    (3, "Chloé Dubois", "Héliomed", "Analyse de données de capteurs médicaux", "2026-04-06", "2026-09-25"),
]


def chemin_base() -> Path:
    """Chemin du fichier SQLite, relu à chaque appel pour que les tests puissent le changer."""
    return Path(os.environ.get("DATABASE_PATH", "stages.db"))


@contextmanager
def ouvrir_connexion():
    """Ouvre une connexion, valide les modifications si tout s'est bien passé, puis la ferme."""
    chemin = chemin_base()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    connexion = sqlite3.connect(chemin)
    # Permet de lire les lignes comme des dictionnaires (ligne["nom_etudiant"]).
    connexion.row_factory = sqlite3.Row
    try:
        yield connexion
        connexion.commit()
    finally:
        connexion.close()


def initialiser_base() -> None:
    """Crée la table si besoin et y insère les stages d'exemple si elle est vide."""
    with ouvrir_connexion() as connexion:
        connexion.execute(
            """
            CREATE TABLE IF NOT EXISTS stages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom_etudiant TEXT NOT NULL,
                entreprise TEXT NOT NULL,
                intitule TEXT NOT NULL,
                date_debut TEXT NOT NULL,
                date_fin TEXT NOT NULL
            )
            """
        )
        nombre = connexion.execute("SELECT COUNT(*) FROM stages").fetchone()[0]
        if nombre == 0:
            connexion.executemany(
                f"INSERT INTO stages ({COLONNES}) VALUES (?, ?, ?, ?, ?, ?)",
                STAGES_EXEMPLE,
            )
