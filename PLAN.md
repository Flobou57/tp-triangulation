# BOUSSER Florian Ilsen Gr 2 
# TODO

## Organisation des tests

Organisation des tests en 3 dossiers séparés :
- `tests/unit/` : tests unitaires purs (algorithme de triangulation, format binaire)
- `tests/api/` : tests bout-en-bout de l'API HTTP, via le client de test Flask
- `tests/perf/` : tests de performance

Egalement il va y avoir un `Makefile` à la racine du projet exposera les cibles demandées :
- `make test` : lance tous les tests (`pytest`)
- `make unit_test` : lance tous les tests sauf les tests de performance
- `make perf_test` : lance uniquement les tests de performance
- `make coverage` : génère un rapport de couverture de code (`coverage`)
- `make lint` : vérifie la qualité du code (`ruff check`)
- `make doc` : génère la documentation HTML (`pdoc3`)

## Plan de tests

## 1. Tests de l'algorithme de triangulation

But général : garantir que l'algorithme implémenté produit des triangulations géométriquement correctes, et échoue proprement sur les cas impossibles plutôt que de planter ou de renvoyer un résultat faux

- 3 points non alignés → succès, 1 triangle (cas de base : le strict minimum de points pour former une triangulation)
- Carré (4 points) → succès, 2 triangles, aire totale cohérente (vérifie qu'on sait connecter plusieurs triangles entre eux, pas juste en produire un seul isolé)
- Nuage de points aléatoires (dizaines/centaines de points) → succès, vérifié via la propriété de Delaunay (aucun point dans le cercle circonscrit d'un triangle) plutôt qu'un résultat figé (impossible d'écrire "le bon résultat" à la main pour autant de points, donc on vérifie la propriété mathématique qui définit une triangulation de Delaunay valide)
- Moins de 3 points → échec, erreur explicite (géométriquement impossible de former un triangle, il faut une erreur claire plutôt qu'un plantage ou un résultat vide silencieux)
- Points tous alignés → échec, erreur explicite, aucune aire possible (même s'il y a 3 points ou plus, s'ils sont sur une même ligne aucun triangle n'a de surface, donc pas de triangulation possible)
- Sous-ensemble de points alignés au sein d'un nuage plus large → succès (cas différent du précédent : ici il y a d'autres points hors de la ligne, donc une triangulation reste possible, l'algo ne doit pas se faire piéger par ce sous-cas)
- Points dupliqués, mêmes coordonnées exactes → succès, pas de plantage, pas de triangle d'aire nulle (un doublon peut faire planter un calcul géométrique, comme un cercle circonscrit mal défini, donc on veut vérifier que l'algo l'ignore proprement)
- Points très proches mais pas identiques → succès, robustesse numérique (teste que l'algo ne devient pas instable quand deux points sont presque confondus, un cas réaliste avec des données mesurées)
- Points à coordonnées négatives ou très grandes → succès (vérifie que le calcul ne dépend pas d'une hypothèse cachée sur la plage de valeurs, ex: coordonnées toujours positives)
- Points concycliques, plusieurs points sur un même cercle → succès, la propriété de Delaunay reste respectée même si le découpage exact peut varier (cas ambigu mathématiquement : plusieurs triangulations sont valides à la fois, donc on ne peut pas vérifier "LE bon résultat", seulement que le résultat obtenu respecte bien la propriété)
- Un point très éloigné du reste du nuage → succès, ne casse pas le calcul (l'algo utilise un grand triangle englobant au démarrage, ce test vérifie qu'il reste assez grand même avec un point extrême)
- Ordre des points mélangé en entrée → résultat géométriquement équivalent (l'algo insère les points un par un, le résultat ne doit pas dépendre arbitrairement de l'ordre dans lequel on les a donnés)

## 2. Tests du format binaire (PointSet / Triangles)

But général : garantir que la conversion vers/depuis le format binaire imposé est fidèle, et que les données corrompues sont détectées plutôt que de planter silencieusement

- Encodage puis décodage d'un `PointSet` → données identiques (garantit que la conversion aller-retour ne perd ni ne déforme aucune donnée)
- Idem pour `Triangles` (sommets + triangles) → données identiques (même logique que `PointSet`, mais avec la partie supplémentaire dédiée aux triangles, qui a son propre risque d'erreur)
- Ensemble vide (0 points / 0 triangles) → succès (cas limite bas : le compteur vaut 0, pas d'octets de points/triangles après, il ne faut pas planter en essayant de lire des données qui n'existent pas)
- 1 seul point / 1 seul triangle → succès (juste au-dessus du cas vide, vérifie qu'on ne fait pas d'erreur d'index en lisant exactement 1 élément)
- Grand nombre de points/triangles → succès (vérifie que le format tient à l'échelle, pas de limite ou d'erreur qui apparaîtrait seulement sur de gros volumes)
- Coordonnées négatives, grande précision décimale → succès (le format utilise des `float`, donc on veut être sûr qu'on gère bien le signe et qu'on ne tronque pas la précision au-delà de ce qu'un `float` permet)
- Données dont la taille ne correspond pas au compteur annoncé, tronquées ou avec des octets en trop → échec (le compteur en tête de message dit "il y a N points", si la taille réelle des données ne colle pas, c'est que le message est une erreur, on doit le détecter plutôt que lire n'importe quoi ou planter)
- Compteur annoncé absurde, ex: des milliards, avec un buffer minuscule → échec propre, pas de plantage ni d'allocation déraisonnable (un compteur qui est erroné ne doit pas faire planter ou tenter de réserver une quantité de mémoire déraisonnable)
- Triangle référençant un indice de sommet hors bornes, y compris pile à la limite (indice == nombre de sommets) → échec (les indices valides vont de `0` à `nombre_de_sommets - 1` ; un indice égal au nombre de sommets est une erreur à éviter, donc un cas à tester)

## 3. Tests de l'API HTTP

But général : vérifier que le service se comporte comme décrit dans `triangulator.yml`, notamment sur tous les cas d'erreur liés à l'interaction avec le `PointSetManager`. Le `PointSetManager` est simulé (mock) dans ces tests, aucun vrai service externe n'est démarré

- `PointSetID` valide, `PointSet` correct → succès, 200 + `Triangles` binaire, `Content-Type: application/octet-stream` (le cas nominal, tout fonctionne comme prévu de bout en bout)
- `PointSetID` mal formé (pas un UUID, ex: `"abc"`) → échec, 400 (il faut rejeter avant même d'essayer de contacter le `PointSetManager`, inutile de faire un appel réseau pour une requête invalide)
- `PointSetID` en majuscules → succès, comme le cas nominal (il ne faut pas rejeter à tort un ID valide juste écrit différemment)
- `PointSetManager` répond "not found" (le `PointSetID` n'existe pas côté `PointSetManager`) → échec, 404 (on relaie l'absence de la donnée)
- `PointSetManager` répond "bad request" → échec, 400 (on relaie l'erreur du service en amont plutôt que de la masquer)
- `PointSetManager` injoignable, timeout, ou erreur serveur → échec, 503 (on distingue bien "le service est en panne" d'une vraie erreur 400/404 métier, pour que le client sache qu'il peut réessayer plus tard)
- `PointSetManager` renvoie des données binaires invalides → échec, 500 (le format binaire attendu n'est pas respecté, le décodeur doit le détecter plutôt que planter ou produire un résultat incohérent)
- `PointSet` récupéré correctement mais dégénéré, ex. points alignés → échec, 500 (les données sont valides au format mais géométriquement impossibles à trianguler, l'erreur vient de l'algorithme, pas du réseau)
- Mauvaise méthode HTTP sur la route, ex. `POST` au lieu de `GET` → échec, 405 (vérifie que le routage Flask rejette bien les méthodes non prévues par l'API)

## 4. Tests de performance

But général : s'assurer que la triangulation et la conversion binaire restent utilisables à des tailles réalistes, sans ralentir la suite de tests principale

- Chaque test définit un seuil explicite (borne large, pas un objectif de perf strict) au-delà duquel il échoue (ex: "triangulation de 5000 points doit rester sous X secondes"). Sans ça, "mesurer" ne sert à rien en automatique, il faut un critère pass/fail exploitable
- Temps de triangulation sur des jeux de points de tailles croissantes (ex: 100, 1000, quelques milliers de points) (permet de voir comment le temps évolue avec la taille des données)
- Au moins un cas extrême (ex: 10 000 ou 50 000 points), au-delà des tailles "réalistes" (pour voir où ça commence vraiment à devenir problématique, même si ce n'est pas un usage normal)
- Temps d'encodage/décodage binaire sur des jeux de données volumineux (la conversion binaire est censée être rapide, on veut vérifier qu'elle le reste vraiment même à grande échelle, séparément de la triangulation qui est l'opération la plus coûteuse)
- Points presque alignés en grand nombre (pire cas potentiel pour l'algo) (un algorithme de triangulation implémenté sans structure d'optimisation peut ralentir fortement sur des configurations géométriques particulières, ce test sert à détecter ce genre de cas limite plutôt que de découvrir le problème en production)
- Points très regroupés et très étalés (compare deux distributions spatiales différentes pour voir si la densité des points a un impact sur le temps de calcul, un scénario réaliste selon d'où viennent les données)
- Performance côté API bout-en-bout, pas seulement l'algorithme isolé (un gros `PointSet` envoyé via le `PointSetManager` simulé, pour capturer le coût réel perçu par un client : sérialisation + décodage + calcul + ré-encodage, pas juste le calcul pur)
- Appels répétés successifs à la triangulation (ex: 50 fois de suite sur les mêmes données) → doit rester stable, pas de fuite mémoire ni de ralentissement progressif
- Comparer plusieurs exécutions du même test → variance limitée entre les runs (un temps qui varie énormément d'une exécution à l'autre n'est pas bon)
