from unittest.mock import Mock

import pytest

from triangulator.app import create_app
from triangulator.binary import decode_triangles
from triangulator.errors import (
    PointSetManagerBadRequestError,
    PointSetManagerUnavailableError,
    PointSetNotFoundError,
)

_UUID_VALIDE = "123e4567-e89b-12d3-a456-426614174000"
_UUID_VALIDE_MAJUSCULES = _UUID_VALIDE.upper()
_ROUTE = f"/triangulation/{_UUID_VALIDE}"

_POINTS_NON_ALIGNES = [(0.0, 0.0), (4.0, 0.0), (0.0, 3.0)]
_POINTS_ALIGNES = [(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)]


@pytest.fixture
def client():
    """Client de test Flask pour l'application `Triangulator`, sans serveur réel."""
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def _assert_corps_erreur(response):
    """Vérifie que le corps JSON respecte le schéma `Error` de `triangulator.yml`."""
    body = response.get_json()
    assert isinstance(body, dict)
    assert isinstance(body.get("code"), str) and body["code"]
    assert isinstance(body.get("message"), str) and body["message"]


def test_pointsetid_valide_et_pointset_correct_reussit(client, monkeypatch):
    """`PointSetID` valide, `PointSet` correct → succès, 200 + `Triangles` binaire."""
    monkeypatch.setattr(
        "triangulator.app.fetch_point_set", Mock(return_value=_POINTS_NON_ALIGNES)
    )

    response = client.get(_ROUTE)

    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("application/octet-stream")
    points, triangles = decode_triangles(response.data)
    assert points == _POINTS_NON_ALIGNES
    assert len(triangles) >= 1


def test_pointsetid_mal_forme_echoue_sans_appel_reseau(client, monkeypatch):
    """`PointSetID` mal formé (pas un UUID) → échec, 400, sans contacter le `PointSetManager`."""
    fetch = Mock()
    monkeypatch.setattr("triangulator.app.fetch_point_set", fetch)

    response = client.get("/triangulation/abc")

    assert response.status_code == 400
    _assert_corps_erreur(response)
    fetch.assert_not_called()


def test_pointsetid_en_majuscules_reussit_comme_le_cas_nominal(client, monkeypatch):
    """`PointSetID` en majuscules → succès, comme le cas nominal."""
    monkeypatch.setattr(
        "triangulator.app.fetch_point_set", Mock(return_value=_POINTS_NON_ALIGNES)
    )

    response = client.get(f"/triangulation/{_UUID_VALIDE_MAJUSCULES}")

    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("application/octet-stream")


def test_pointsetmanager_repond_not_found_echoue(client, monkeypatch):
    """`PointSetManager` répond "not found" → échec, 404."""
    monkeypatch.setattr(
        "triangulator.app.fetch_point_set",
        Mock(side_effect=PointSetNotFoundError(_UUID_VALIDE)),
    )

    response = client.get(_ROUTE)

    assert response.status_code == 404
    _assert_corps_erreur(response)


def test_pointsetmanager_repond_bad_request_echoue(client, monkeypatch):
    """`PointSetManager` répond "bad request" → échec, 400, l'erreur amont est relayée."""
    monkeypatch.setattr(
        "triangulator.app.fetch_point_set",
        Mock(side_effect=PointSetManagerBadRequestError(_UUID_VALIDE)),
    )

    response = client.get(_ROUTE)

    assert response.status_code == 400
    _assert_corps_erreur(response)


def test_pointsetmanager_injoignable_ou_en_erreur_echoue(client, monkeypatch):
    """`PointSetManager` injoignable, timeout, ou erreur serveur → échec, 503."""
    monkeypatch.setattr(
        "triangulator.app.fetch_point_set",
        Mock(side_effect=PointSetManagerUnavailableError(_UUID_VALIDE)),
    )

    response = client.get(_ROUTE)

    assert response.status_code == 503
    _assert_corps_erreur(response)


def test_pointsetmanager_renvoie_des_donnees_binaires_invalides_echoue(client, monkeypatch):
    """`PointSetManager` renvoie des données binaires invalides → échec, 500."""
    from triangulator.errors import BinaryFormatError

    monkeypatch.setattr(
        "triangulator.app.fetch_point_set",
        Mock(side_effect=BinaryFormatError("corrupted PointSet payload")),
    )

    response = client.get(_ROUTE)

    assert response.status_code == 500
    _assert_corps_erreur(response)


def test_pointset_degenere_echoue(client, monkeypatch):
    """`PointSet` récupéré correctement mais dégénéré (points alignés) → échec, 500."""
    monkeypatch.setattr(
        "triangulator.app.fetch_point_set", Mock(return_value=_POINTS_ALIGNES)
    )

    response = client.get(_ROUTE)

    assert response.status_code == 500
    _assert_corps_erreur(response)


def test_mauvaise_methode_http_echoue(client, monkeypatch):
    """Mauvaise méthode HTTP sur la route, ex. `POST` au lieu de `GET` → échec, 405."""
    fetch = Mock()
    monkeypatch.setattr("triangulator.app.fetch_point_set", fetch)

    response = client.post(_ROUTE)

    assert response.status_code == 405
    fetch.assert_not_called()
