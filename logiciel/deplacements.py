"""
Broutille — déplacements des tortues pendant leurs visites (positions/AAAA-MM.csv).

  - trajets      : positions de chaque visite nommée, reliées au journal par id_visite
  - activite     : distance parcourue (en longueurs de carapace) et part du temps en mouvement
  - carte_zones  : où chaque tortue passe son temps, sur une grille de l'image
  - interactions : contacts, poursuites et chevauchements entre deux tortues présentes ensemble

Les positions sont prises à chaque analyse : toutes les secondes avec une carte graphique,
toutes les 5 s sur processeur. Plus elles sont espacées, moins les poursuites se voient.
"""

import math
from collections import defaultdict
from datetime import datetime, timedelta

from PIL import Image, ImageDraw

from comportement import sejours

BOUGE = 0.15             # en longueurs de carapace : en dessous, c'est le cadre qui tremble, pas la tortue
CONTACT = 1.0            # centres à moins d'une longueur : au contact
SIMULTANE_S = 0.6        # deux positions prises à la même analyse
POURSUITE_MIN = 3        # analyses d'affilée pour parler de poursuite
CHEVAUCHE = 0.3          # cadres qui se recouvrent à 30 % de la plus petite : l'une sur l'autre


def trajets(journal, positions, jours=None, fin=None):
    """[(cle, [(instant, cx, cy, taille, boite, rapport)])] des visites nommées qui ont des positions.
    Tout est en fractions de la largeur de l'image (cx, cy, boite) ; taille = racine de la surface du
    cadre, à peu près une longueur de carapace ; rapport = hauteur / largeur de l'image."""
    visites = {l.get("id_visite"): l for l in journal}
    retenues = {(c, d) for c, d, _f in sejours(journal, jours, fin)}
    res = []
    for id_visite, points in positions.items():
        l = visites.get(id_visite)
        if not l or not l.get("id_individu"):
            continue
        try:
            arrivee = datetime.fromisoformat(f"{l['date']}T{l['heure']}")
        except (KeyError, ValueError):
            continue
        if (l["id_individu"], arrivee) not in retenues:
            continue
        pts = []
        for t, x, y, w, h, il, ih in sorted(points):
            il, ih = max(il, 1), max(ih, 1)
            pts.append((arrivee + timedelta(seconds=t), (x + w / 2) / il, (y + h / 2) / il,
                        math.sqrt(w * h) / il, (x / il, y / il, w / il, h / il), ih / il))
        if pts:
            res.append((l["id_individu"], pts))
    return sorted(res, key=lambda r: r[1][0][0])


def activite(liste):
    """{cle: {"distance" (longueurs de carapace), "minutes" observées, "par_minute", "mouvement" (0 à 1)}}."""
    cumul = defaultdict(lambda: {"distance": 0.0, "secondes": 0.0, "bouge_s": 0.0})
    for cle, pts in liste:
        r = cumul[cle]
        for p0, p1 in zip(pts, pts[1:]):
            dt = (p1[0] - p0[0]).total_seconds()
            if dt <= 0 or dt > 30:
                continue
            pas = math.hypot(p1[1] - p0[1], p1[2] - p0[2]) / max((p0[3] + p1[3]) / 2, 1e-6)
            r["secondes"] += dt
            if pas >= BOUGE:
                r["distance"] += pas
                r["bouge_s"] += dt
    return {c: {"distance": r["distance"], "minutes": r["secondes"] / 60,
                "par_minute": r["distance"] / (r["secondes"] / 60) if r["secondes"] else 0.0,
                "mouvement": r["bouge_s"] / r["secondes"] if r["secondes"] else 0.0}
            for c, r in cumul.items()}


def carte_zones(liste, cle=None, grille=(32, 18)):
    """(grille [ligne][colonne] du temps passé à chaque endroit en secondes, rapport hauteur/largeur),
    pour une tortue ou toutes (cle=None)."""
    gl, gh = grille
    carte = [[0.0] * gl for _ in range(gh)]
    rapport = None
    for c, pts in liste:
        if cle and c != cle:
            continue
        for k, p in enumerate(pts):
            rapport = p[5]
            suivant = pts[k + 1][0] if k + 1 < len(pts) else p[0]
            dt = min(max((suivant - p[0]).total_seconds(), 1.0), 30.0)
            i = min(gh - 1, max(0, int(p[2] / max(rapport, 1e-6) * gh)))
            j = min(gl - 1, max(0, int(p[1] * gl)))
            carte[i][j] += dt
    return carte, rapport


def _recouvrement(a, b):
    """Surface commune de deux cadres (x, y, l, h), en part du plus petit."""
    l = max(0.0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    h = max(0.0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    petite = min(a[2] * a[3], b[2] * b[3])
    return l * h / petite if petite > 0 else 0.0


def _simultanes(pa, pb):
    """Positions des deux tortues prises à la même analyse : [(pa[i], pb[j])]."""
    communs, j = [], 0
    for p in pa:
        while j < len(pb) and (pb[j][0] - p[0]).total_seconds() < -SIMULTANE_S:
            j += 1
        if j < len(pb) and abs((pb[j][0] - p[0]).total_seconds()) <= SIMULTANE_S:
            communs.append((p, pb[j]))
    return communs


def interactions(liste):
    """{(a, b): {"contact_s", "chevauchements", "poursuites": {cle_qui_suit: n}}}, a < b, pour les
    paires vues au même moment.
    - contact : centres à moins d'une longueur de carapace ;
    - chevauchement : un cadre recouvre l'autre (une tortue sur l'autre : monte, ou bélier) ;
    - poursuite : les deux avancent dans la même direction, à moins de 3 longueurs, POURSUITE_MIN
      analyses d'affilée ; celle qui suit est celle qui avance vers l'autre."""
    res = {}
    for i, (a, pa) in enumerate(liste):
        for b, pb in liste[i + 1:]:
            if a == b or pa[-1][0] < pb[0][0] or pb[-1][0] < pa[0][0]:
                continue
            x, px, y, py = (a, pa, b, pb) if a < b else (b, pb, a, pa)
            r = res.setdefault((x, y), {"contact_s": 0.0, "chevauchements": 0, "poursuites": defaultdict(int)})
            _paire(r, x, y, _simultanes(px, py))
    return {p: {**v, "poursuites": dict(v["poursuites"])} for p, v in res.items()
            if v["contact_s"] or v["chevauchements"] or v["poursuites"]}


def _paire(r, a, b, communs):
    suite, qui, dessus = 0, None, False

    def fin_episode():
        if qui and suite >= POURSUITE_MIN - 1:      # POURSUITE_MIN positions = POURSUITE_MIN - 1 pas
            r["poursuites"][qui] += 1

    for k, (p, q) in enumerate(communs):
        taille = (p[3] + q[3]) / 2
        dist = math.hypot(p[1] - q[1], p[2] - q[2]) / max(taille, 1e-6)
        if k + 1 < len(communs):
            dt = (communs[k + 1][0][0] - p[0]).total_seconds()
            if dist < CONTACT and 0 < dt <= 30:
                r["contact_s"] += dt
        chevauche = _recouvrement(p[4], q[4]) >= CHEVAUCHE
        if chevauche and not dessus:
            r["chevauchements"] += 1
        dessus = chevauche
        suiveuse = None
        if k:
            p0, q0 = communs[k - 1]
            va, vb = (p[1] - p0[1], p[2] - p0[2]), (q[1] - q0[1], q[2] - q0[2])
            na, nb = math.hypot(*va), math.hypot(*vb)
            if na >= BOUGE * taille and nb >= BOUGE * taille and dist < 3 \
                    and (va[0] * vb[0] + va[1] * vb[1]) / (na * nb) > 0.7:
                a_vers_b = (q[1] - p[1]) * va[0] + (q[2] - p[2]) * va[1]
                suiveuse = a if a_vers_b > 0 else b
        if suiveuse is not None and suiveuse == qui:
            suite += 1
        else:
            fin_episode()
            suite, qui = (1, suiveuse) if suiveuse else (0, None)
    fin_episode()


def image_zones(carte, rapport, fond_image=None, largeur=640, chaud=(248, 81, 73)):
    """Carte de chaleur posée sur une photo de la mangeoire (Image PIL), ou sur un fond sombre."""
    l = largeur
    h = max(1, int(l * (rapport or 9 / 16)))
    base = fond_image.convert("RGB").resize((l, h)) if fond_image is not None else Image.new("RGB", (l, h), (27, 33, 25))
    base = Image.blend(base, Image.new("RGB", (l, h), (0, 0, 0)), 0.35)
    gh, gl = len(carte), len(carte[0])
    maxi = max(max(ligne) for ligne in carte) or 1
    calque = Image.new("RGBA", (l, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(calque)
    for i, ligne in enumerate(carte):
        for j, v in enumerate(ligne):
            if v:
                a = int(40 + 180 * math.sqrt(v / maxi))
                d.rectangle([j * l / gl, i * h / gh, (j + 1) * l / gl, (i + 1) * h / gh], fill=(*chaud, a))
    return Image.alpha_composite(base.convert("RGBA"), calque).convert("RGB")
