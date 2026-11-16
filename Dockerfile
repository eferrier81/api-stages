# Image Python officielle allégée : Python 3.11 sans les outils de compilation inutiles à l'exécution
FROM python:3.11-slim

# Pas de fichiers .pyc dans l'image, et journaux affichés sans tampon (lisibles en direct sur Render)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Dossier de travail : tous les chemins suivants sont relatifs à /app
WORKDIR /app

# Dépendances copiées avant le code : cette couche reste en cache tant que requirements.txt ne change pas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code de l'application seul (tests, scripts et documentation restent hors de l'image)
COPY app/ ./app/

# Base SQLite dans un dossier dédié ; sur Render gratuit le disque est éphémère, la base est recréée au démarrage
ENV DATABASE_PATH=/app/data/stages.db

# Utilisateur sans privilèges, propriétaire du seul dossier où SQLite écrit (base et fichier journal)
RUN useradd --system --no-create-home appuser \
    && mkdir -p /app/data \
    && chown appuser:appuser /app/data
USER appuser

# Port par défaut, à titre indicatif : Render fournit le port réel dans la variable PORT
EXPOSE 10000

# Forme shell pour lire PORT ; exec remplace le shell par uvicorn, qui reçoit alors les signaux d'arrêt
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}
