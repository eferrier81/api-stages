"""Fixtures partagées par les tests de l'API de gestion des stages."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Client HTTP de test branché sur une base SQLite temporaire, propre à chaque test.

    Le bloc ``with`` déclenche le lifespan de l'application : la table est créée
    et les 3 stages d'exemple (ids 1 à 3) sont insérés dans cette base neuve.
    """
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as c:
        yield c
