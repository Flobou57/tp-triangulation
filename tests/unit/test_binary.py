"""Tests du format binaire `PointSet` / `Triangles` (PLAN.md, section 2)."""

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

# 4294967295 (max d'un unsigned long 4 bytes), sert à simuler un compteur
# de points/triangles délirant, quel que soit le boutisme
_COMPTEUR_ABSURDE = b"\xff\xff\xff\xff"


def _points_exacts(count):
    """Génère `count` points à coordonnées exactement représentables en binary32."""
    # Des multiples de 1/4 et 1/8 restent exacts en float 32 bits
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

    decoded = decode_triangles(encode_triangles(points, [(0, 1, 2)]))
    assert decoded == (points, [(0, 1, 2)])


def test_grand_nombre_de_points_et_de_triangles_fait_un_aller_retour():
    """Grand nombre de points/triangles → succès, le format tient à l'échelle."""
    points = _points_exacts(10_000)
    triangles = _triangles_chaines(len(points) - 2)

    assert decode_point_set(encode_point_set(points)) == points
    assert decode_triangles(encode_triangles(points, triangles)) == (points, triangles)


def test_coordonnees_negatives_et_precision_decimale_sont_preservees():
    """Coordonnées négatives, précision décimale → succès, sans troncature excessive."""
    points = [(-0.1, 0.2), (math.pi, -math.e), (1e-7, -1e7), (-1.0 / 3.0, 2.0 / 3.0)]

    decoded = decode_point_set(encode_point_set(points))

    assert len(decoded) == len(points)
    # Le format stocke des float 32 bits : une perte de précision au-delà de
    # ~7 chiffres significatifs est normale, pas un bug
    for (x, y), (expected_x, expected_y) in zip(decoded, points, strict=True):
        assert x == pytest.approx(expected_x, rel=1e-6)
        assert y == pytest.approx(expected_y, rel=1e-6)


def test_point_set_tronque_echoue():
    """`PointSet` tronqué (taille ≠ compteur annoncé) → échec."""
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
    """`Triangles` tronqué (taille ≠ compteurs annoncés) → échec."""
    points = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    data = encode_triangles(points, [(0, 1, 2)])

    with pytest.raises(BinaryFormatError):
        decode_triangles(data[:-1])
    with pytest.raises(BinaryFormatError):
        decode_triangles(data[:4])


def test_triangles_avec_octets_en_trop_echouent():
    """`Triangles` avec des octets en trop par rapport au compteur annoncé → échec."""
    points = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    data = encode_triangles(points, [(0, 1, 2)])

    with pytest.raises(BinaryFormatError):
        decode_triangles(data + b"\x00")


def test_compteur_de_points_absurde_echoue_proprement():
    """Compteur de points absurde → échec propre, sans grosse allocation mémoire."""
    data = _COMPTEUR_ABSURDE + b"\x00" * 8

    start = time.perf_counter()
    with pytest.raises(BinaryFormatError):
        decode_point_set(data)
    assert time.perf_counter() - start < 1.0


def test_compteur_de_triangles_absurde_echoue_proprement():
    """Compteur de triangles absurde → échec propre, sans grosse allocation mémoire."""
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

    with pytest.raises(BinaryFormatError):
        encode_triangles(points, [(0, 1, len(points))])
