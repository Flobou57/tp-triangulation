import math
import time

import pytest

from triangulator.binary import (
    decode_point_set,
    decode_triangles,
    encode_point_set,
    encode_triangles,
)
from triangulator.errors import BinaryFormatError

# Entête des deux structures : un unsigned long de 4 bytes donnant un nombre d'éléments. Cette valeur est 4294967295 quel que soit le boutisme, ce qui permet de forger un compteur absurde sans présumer de celui du format.
_COMPTEUR_ABSURDE = b"\xff\xff\xff\xff"


def _points_exacts(count):
    """`count` points distincts, à coordonnées exactement représentables en binary32."""
    return [(i / 4.0, -i / 8.0) for i in range(count)]


def _triangles_chaines(count):
    """`count` triangles référençant des sommets consécutifs (indices valides)."""
    return [(i, i + 1, i + 2) for i in range(count)]


def test_aller_retour_dun_point_set_rend_les_memes_donnees():
    """Encodage puis décodage d'un `PointSet` → données identiques."""
    points = [(0.0, 0.0), (1.25, -3.75), (-512.5, 2048.25), (0.5, 0.125)]

    assert decode_point_set(encode_point_set(points)) == points


def test_aller_retour_de_triangles_rend_les_memes_donnees():
    """Idem pour `Triangles` (sommets + triangles) → données identiques."""
    points = [(0.0, 0.0), (4.0, 0.0), (0.0, 4.0), (4.0, 4.0)]
    triangles = [(0, 1, 2), (1, 3, 2)]

    assert decode_triangles(encode_triangles(points, triangles)) == (points, triangles)


def test_point_set_vide_fait_un_aller_retour():
    """Ensemble vide (0 point) → succès, pas de lecture au-delà du compteur."""
    assert decode_point_set(encode_point_set([])) == []


def test_triangles_vides_font_un_aller_retour():
    """Ensemble vide (0 triangle) → succès, avec ou sans sommets."""
    points = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]

    assert decode_triangles(encode_triangles(points, [])) == (points, [])
    assert decode_triangles(encode_triangles([], [])) == ([], [])


def test_un_seul_point_fait_un_aller_retour():
    """1 seul point → succès, pas d'erreur d'index sur un unique élément."""
    assert decode_point_set(encode_point_set([(1.5, -2.5)])) == [(1.5, -2.5)]


def test_un_seul_triangle_fait_un_aller_retour():
    """1 seul triangle → succès, pas d'erreur d'index sur un unique élément."""
    points = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]

    assert decode_triangles(encode_triangles(points, [(0, 1, 2)])) == (points, [(0, 1, 2)])


def test_grand_nombre_de_points_et_de_triangles_fait_un_aller_retour():
    """Grand nombre de points/triangles → succès, le format tient à l'échelle."""
    points = _points_exacts(10_000)
    triangles = _triangles_chaines(len(points) - 2)

    assert decode_point_set(encode_point_set(points)) == points
    assert decode_triangles(encode_triangles(points, triangles)) == (points, triangles)


def test_coordonnees_negatives_et_precision_decimale_sont_preservees():
    """Coordonnées négatives, grande précision décimale → succès, pas de troncature au-delà du `float`."""
    points = [(-0.1, 0.2), (math.pi, -math.e), (1e-7, -1e7), (-1.0 / 3.0, 2.0 / 3.0)]

    decoded = decode_point_set(encode_point_set(points))

    assert len(decoded) == len(points)
    # binary32 garantit ~7 chiffres significatifs : on vérifie que rien n'est perdu au-delà de cette limite intrinsèque au format imposé.
    for (x, y), (expected_x, expected_y) in zip(decoded, points, strict=True):
        assert x == pytest.approx(expected_x, rel=1e-6)
        assert y == pytest.approx(expected_y, rel=1e-6)


def test_point_set_tronque_echoue():
    """`PointSet` dont la taille ne correspond pas au compteur annoncé (tronqué) → échec."""
    data = encode_point_set(_points_exacts(3))

    with pytest.raises(BinaryFormatError):
        decode_point_set(data[:-1])
    with pytest.raises(BinaryFormatError):
        decode_point_set(data[:6])
    with pytest.raises(BinaryFormatError):
        decode_point_set(b"\x00\x01")


def test_point_set_avec_octets_en_trop_echoue():
    """`PointSet` avec des octets en trop par rapport au compteur annoncé → échec."""
    data = encode_point_set(_points_exacts(3))

    with pytest.raises(BinaryFormatError):
        decode_point_set(data + b"\x00")


def test_triangles_tronques_echouent():
    """`Triangles` dont la taille ne correspond pas aux compteurs annoncés (tronqué) → échec."""
    points = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    data = encode_triangles(points, [(0, 1, 2)])

    with pytest.raises(BinaryFormatError):
        decode_triangles(data[:-1])
    with pytest.raises(BinaryFormatError):
        decode_triangles(data[:4])


def test_triangles_avec_octets_en_trop_echouent():
    """`Triangles` avec des octets en trop par rapport aux compteurs annoncés → échec."""
    points = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    data = encode_triangles(points, [(0, 1, 2)])

    with pytest.raises(BinaryFormatError):
        decode_triangles(data + b"\x00")


def test_compteur_de_points_absurde_echoue_proprement():
    """Compteur de points absurde avec un buffer minuscule → échec propre, pas d'allocation déraisonnable."""
    data = _COMPTEUR_ABSURDE + b"\x00" * 8

    start = time.perf_counter()
    with pytest.raises(BinaryFormatError):
        decode_point_set(data)
    # Un rejet quasi instantané est la trace observable du fait que le décodeur a comparé la taille annoncée à la taille réelle avant de réserver quoi que ce soit pour 4 milliards de points.
    assert time.perf_counter() - start < 1.0


def test_compteur_de_triangles_absurde_echoue_proprement():
    """Compteur de triangles absurde avec un buffer minuscule → échec propre, pas d'allocation déraisonnable."""
    points = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    data = encode_point_set(points) + _COMPTEUR_ABSURDE + b"\x00" * 12

    start = time.perf_counter()
    with pytest.raises(BinaryFormatError):
        decode_triangles(data)
    assert time.perf_counter() - start < 1.0


def test_indice_de_sommet_hors_bornes_echoue():
    """Triangle référençant un indice de sommet hors bornes → échec."""
    points = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]

    with pytest.raises(BinaryFormatError):
        encode_triangles(points, [(0, 1, 42)])


def test_indice_de_sommet_egal_au_nombre_de_sommets_echoue():
    """Indice de sommet pile à la limite (indice == nombre de sommets) → échec."""
    points = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]

    # Les indices valides vont de 0 à len(points) - 1 : 3 est donc le premier indice invalide, et le plus susceptible de passer à travers un test de bornes écrit avec un <= au lieu d'un <.
    with pytest.raises(BinaryFormatError):
        encode_triangles(points, [(0, 1, len(points))])
