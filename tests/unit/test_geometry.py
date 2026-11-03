"""Tests de l'algorithme de triangulation (PLAN.md, section 1)."""

import math
import random

import pytest

from triangulator.errors import TriangulationError
from triangulator.geometry import triangulate


def _triangle_area(a, b, c):
    """Aire non signée du triangle (a, b, c)."""
    ax, ay = a
    bx, by = b
    cx, cy = c
    return abs((bx - ax) * (cy - ay) - (cx - ax) * (by - ay)) / 2.0


def _total_area(points, triangles):
    """Somme des aires de tous les triangles d'une triangulation."""
    return sum(_triangle_area(points[i], points[j], points[k]) for i, j, k in triangles)


def _circumcircle_contains(a, b, c, p, tolerance=1e-9):
    """Détermine si p est strictement dans le cercle circonscrit à (a, b, c)."""
    ax, ay = a[0] - p[0], a[1] - p[1]
    bx, by = b[0] - p[0], b[1] - p[1]
    cx, cy = c[0] - p[0], c[1] - p[1]
    det = (
        (ax * ax + ay * ay) * (bx * cy - cx * by)
        - (bx * bx + by * by) * (ax * cy - cx * ay)
        + (cx * cx + cy * cy) * (ax * by - bx * ay)
    )
    orientation = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
    if orientation < 0:
        # Le signe du déterminant dépend du sens (horaire/anti-horaire) de a, b, c :
        # on le corrige pour que "det > 0" signifie toujours "p est dedans"
        det = -det
    return det > tolerance


def _is_delaunay(points, triangles, tolerance=1e-9):
    """Vérifie qu'aucun point n'est dans le cercle circonscrit des triangles."""
    for i, j, k in triangles:
        a, b, c = points[i], points[j], points[k]
        for idx, p in enumerate(points):
            if idx in (i, j, k):
                continue
            if _circumcircle_contains(a, b, c, p, tolerance):
                return False
    return True


def test_trois_points_non_alignes_donnent_un_triangle():
    """3 points non alignés → succès, 1 triangle."""
    points = [(0.0, 0.0), (4.0, 0.0), (0.0, 3.0)]
    triangles = triangulate(points)
    assert len(triangles) == 1
    assert _is_delaunay(points, triangles)


def test_carre_donne_deux_triangles_avec_aire_totale_coherente():
    """Carré (4 points) → succès, 2 triangles, aire totale cohérente."""
    points = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    triangles = triangulate(points)
    assert len(triangles) == 2
    assert _total_area(points, triangles) == pytest.approx(100.0)


def test_nuage_de_points_aleatoires_respecte_la_propriete_de_delaunay():
    """Nuage de points aléatoires → succès, vérifié via la propriété de Delaunay."""
    rng = random.Random(42)
    points = [(rng.uniform(-100, 100), rng.uniform(-100, 100)) for _ in range(150)]
    triangles = triangulate(points)
    assert _is_delaunay(points, triangles)


def test_moins_de_trois_points_echoue():
    """Moins de 3 points → échec, erreur explicite."""
    with pytest.raises(TriangulationError):
        triangulate([(0.0, 0.0), (1.0, 1.0)])


def test_points_tous_alignes_echoue():
    """Points tous alignés → échec, erreur explicite, aucune aire possible."""
    points = [(float(i), float(i)) for i in range(10)]
    with pytest.raises(TriangulationError):
        triangulate(points)


def test_sous_ensemble_de_points_alignes_dans_un_nuage_plus_large_reussit():
    """Sous-ensemble de points alignés au sein d'un nuage plus large → succès."""
    points = [(float(i), float(i)) for i in range(5)] + [(2.0, 5.0), (2.0, -5.0)]
    triangles = triangulate(points)
    assert len(triangles) > 0
    assert _is_delaunay(points, triangles)


def test_points_dupliques_ne_plantent_pas_et_pas_de_triangle_daire_nulle():
    """Points dupliqués (mêmes coordonnées) → succès, sans plantage ni aire nulle."""
    points = [(0.0, 0.0), (0.0, 0.0), (4.0, 0.0), (0.0, 4.0)]
    triangles = triangulate(points)
    assert len(triangles) > 0
    for i, j, k in triangles:
        assert _triangle_area(points[i], points[j], points[k]) > 0.0


def test_points_tres_proches_mais_pas_identiques_sont_stables():
    """Points très proches mais pas identiques → succès, robustesse numérique."""
    points = [(0.0, 0.0), (1e-6, 1e-6), (4.0, 0.0), (0.0, 4.0)]
    triangles = triangulate(points)
    assert _is_delaunay(points, triangles)


def test_coordonnees_negatives_ou_tres_grandes_reussissent():
    """Points à coordonnées négatives ou très grandes → succès."""
    points = [(-1e6, -1e6), (1e6, -1e6), (0.0, 1e6), (0.0, 0.0)]
    triangles = triangulate(points)
    assert _is_delaunay(points, triangles)


def test_points_concycliques_respectent_la_propriete_de_delaunay():
    """Points concycliques → succès, la propriété de Delaunay reste respectée."""
    n = 8
    points = [
        (math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n)) for i in range(n)
    ]
    triangles = triangulate(points)
    # Tolérance plus large : avec des points pile sur le même cercle, le test
    # "dans/hors du cercle" est numériquement limite
    assert _is_delaunay(points, triangles, tolerance=1e-6)


def test_point_tres_eloigne_ne_casse_pas_le_calcul():
    """Un point très éloigné du reste du nuage → succès, ne casse pas le calcul."""
    rng = random.Random(1)
    points = [(rng.uniform(-10, 10), rng.uniform(-10, 10)) for _ in range(20)]
    points += [(1e9, 1e9)]
    triangles = triangulate(points)
    # Tolérance large : avec un point à 1e9, les calculs de cercle circonscrit
    # perdent en précision, une tolérance stricte donnerait des faux négatifs
    assert _is_delaunay(points, triangles, tolerance=1.0)


def test_ordre_des_points_melange_donne_un_resultat_geometriquement_equivalent():
    """Ordre des points mélangé en entrée → résultat géométriquement équivalent."""
    rng = random.Random(7)
    points = [(rng.uniform(-100, 100), rng.uniform(-100, 100)) for _ in range(30)]
    shuffled = list(reversed(points))

    triangles = triangulate(points)
    shuffled_triangles = triangulate(shuffled)

    # On compare l'aire totale, pas la liste des triangles : un ordre d'entrée
    # différent peut produire une triangulation différente mais tout aussi valide
    aire_originale = _total_area(points, triangles)
    aire_melangee = _total_area(shuffled, shuffled_triangles)
    assert aire_originale == pytest.approx(aire_melangee)
