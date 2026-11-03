import random
import time

import pytest

from triangulator.app import create_app
from triangulator.binary import (
    decode_point_set,
    decode_triangles,
    encode_point_set,
    encode_triangles,
)
from triangulator.geometry import triangulate

pytestmark = pytest.mark.perf

# Bornes larges en secondes : des garde-fous, pas des objectifs de perf.
_SEUIL_TRIANGULATION_PAR_TAILLE = {
    100: 1.0,
    1_000: 5.0,
    5_000: 30.0,
}
_SEUIL_CAS_EXTREME = 120.0
_TAILLE_CAS_EXTREME = 20_000

_SEUIL_BINAIRE_VOLUMINEUX = 5.0
_TAILLE_BINAIRE_VOLUMINEUX = 200_000

_SEUIL_PRESQUE_ALIGNES = 30.0
_TAILLE_PRESQUE_ALIGNES = 3_000

_SEUIL_DISTRIBUTION = 30.0
_TAILLE_DISTRIBUTION = 3_000

_SEUIL_API_BOUT_EN_BOUT = 10.0
_TAILLE_API_BOUT_EN_BOUT = 2_000

_NB_APPELS_REPETES = 50
_TAILLE_APPELS_REPETES = 500
_FACTEUR_RALENTISSEMENT_MAX = 2.0

_NB_EXECUTIONS_VARIANCE = 5
_TAILLE_VARIANCE = 1_000
_FACTEUR_VARIANCE_MAX = 5.0


def _points_aleatoires(count, rng, borne=100.0):
    """`count` points uniformément répartis dans [-borne, borne]^2."""
    return [(rng.uniform(-borne, borne), rng.uniform(-borne, borne)) for _ in range(count)]


def _points_presque_alignes(count, rng, bruit=1e-3):
    """`count` points proches de la droite y = x, perturbés d'un faible bruit."""
    return [(float(i) + rng.uniform(-bruit, bruit), float(i) + rng.uniform(-bruit, bruit)) for i in range(count)]


def _chronometrer(fonction, *args, **kwargs):
    """Exécute `fonction` et renvoie (résultat, durée en secondes)."""
    debut = time.perf_counter()
    resultat = fonction(*args, **kwargs)
    return resultat, time.perf_counter() - debut


@pytest.mark.parametrize(
    ("taille", "seuil"),
    sorted(_SEUIL_TRIANGULATION_PAR_TAILLE.items()),
)
def test_temps_de_triangulation_croit_mais_reste_sous_les_seuils(taille, seuil):
    """Temps de triangulation sur des tailles croissantes → chaque taille reste sous son seuil."""
    rng = random.Random(taille)
    points = _points_aleatoires(taille, rng)

    _, duree = _chronometrer(triangulate, points)

    assert duree < seuil


def test_cas_extreme_de_points_ne_devient_pas_inutilisable():
    """Cas extrême (ex: 20 000 points), au-delà des tailles réalistes → reste sous un seuil large."""
    rng = random.Random(1)
    points = _points_aleatoires(_TAILLE_CAS_EXTREME, rng)

    _, duree = _chronometrer(triangulate, points)

    assert duree < _SEUIL_CAS_EXTREME


def test_encodage_decodage_binaire_de_gros_volumes_reste_rapide():
    """Encodage/décodage binaire sur des jeux de données volumineux → reste sous un seuil séparé de la triangulation."""
    rng = random.Random(2)
    points = _points_aleatoires(_TAILLE_BINAIRE_VOLUMINEUX, rng)
    triangles = [(i, (i + 1) % len(points), (i + 2) % len(points)) for i in range(len(points) - 2)]

    _, duree_encodage_points = _chronometrer(encode_point_set, points)
    encoded_points = encode_point_set(points)
    _, duree_decodage_points = _chronometrer(decode_point_set, encoded_points)

    encoded_triangles = encode_triangles(points, triangles)
    _, duree_decodage_triangles = _chronometrer(decode_triangles, encoded_triangles)
    _, duree_encodage_triangles = _chronometrer(encode_triangles, points, triangles)

    assert duree_encodage_points < _SEUIL_BINAIRE_VOLUMINEUX
    assert duree_decodage_points < _SEUIL_BINAIRE_VOLUMINEUX
    assert duree_encodage_triangles < _SEUIL_BINAIRE_VOLUMINEUX
    assert duree_decodage_triangles < _SEUIL_BINAIRE_VOLUMINEUX


def test_points_presque_alignes_en_grand_nombre_ne_degrade_pas_excessivement():
    """Points presque alignés en grand nombre (pire cas potentiel) → reste sous un seuil large."""
    rng = random.Random(3)
    points = _points_presque_alignes(_TAILLE_PRESQUE_ALIGNES, rng)

    _, duree = _chronometrer(triangulate, points)

    assert duree < _SEUIL_PRESQUE_ALIGNES


def test_distribution_groupee_et_distribution_etalee_restent_sous_le_meme_seuil():
    """Points très regroupés vs très étalés, même taille → la densité spatiale ne casse pas la performance."""
    rng_groupes = random.Random(4)
    points_groupes = _points_aleatoires(_TAILLE_DISTRIBUTION, rng_groupes, borne=1e-2)

    rng_etales = random.Random(5)
    points_etales = _points_aleatoires(_TAILLE_DISTRIBUTION, rng_etales, borne=1e8)

    _, duree_groupes = _chronometrer(triangulate, points_groupes)
    _, duree_etales = _chronometrer(triangulate, points_etales)

    assert duree_groupes < _SEUIL_DISTRIBUTION
    assert duree_etales < _SEUIL_DISTRIBUTION


def test_performance_api_bout_en_bout_pour_un_gros_pointset(monkeypatch):
    """Performance côté API bout-en-bout (sérialisation + décodage + calcul + ré-encodage), pas seulement l'algo isolé."""
    rng = random.Random(6)
    points = _points_aleatoires(_TAILLE_API_BOUT_EN_BOUT, rng)
    monkeypatch.setattr("triangulator.app.fetch_point_set", lambda point_set_id: points)

    app = create_app()
    app.config.update(TESTING=True)
    client = app.test_client()

    debut = time.perf_counter()
    response = client.get("/triangulation/123e4567-e89b-12d3-a456-426614174000")
    duree = time.perf_counter() - debut

    assert response.status_code == 200
    assert duree < _SEUIL_API_BOUT_EN_BOUT


def test_appels_repetes_a_la_triangulation_restent_stables():
    """Appels répétés successifs (50x) sur les mêmes données → pas de ralentissement progressif."""
    rng = random.Random(7)
    points = _points_aleatoires(_TAILLE_APPELS_REPETES, rng)

    durees = []
    for _ in range(_NB_APPELS_REPETES):
        _, duree = _chronometrer(triangulate, points)
        durees.append(duree)

    debut_moyenne = sum(durees[:10]) / 10
    fin_moyenne = sum(durees[-10:]) / 10

    assert fin_moyenne < debut_moyenne * _FACTEUR_RALENTISSEMENT_MAX + 1e-6


def test_variance_entre_plusieurs_executions_du_meme_test_reste_limitee():
    """Comparer plusieurs exécutions du même test → variance limitée entre les runs."""
    rng = random.Random(8)
    points = _points_aleatoires(_TAILLE_VARIANCE, rng)

    durees = [_chronometrer(triangulate, points)[1] for _ in range(_NB_EXECUTIONS_VARIANCE)]

    assert max(durees) < min(durees) * _FACTEUR_VARIANCE_MAX + 1e-6
