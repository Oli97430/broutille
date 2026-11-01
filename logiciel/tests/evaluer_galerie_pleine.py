"""
Le vrai risque en usage : une tortue inconnue comparée à des galeries de 60 photos. Plus il y a de
photos, plus un imposteur trouve une vue ressemblante. Chaque fausse fiche réunit ici 60 photos de 60
animaux différents de la même espèce : c'est pire que la réalité, où ces vues montrent un seul animal,
et donne donc une borne haute du taux de fausse identité par image.

    python tests/evaluer_galerie_pleine.py
"""

import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import evaluer_troupeau as e
import vision


def notes(requete, galerie, bonus=0.01, plafond=40, candidats=3):
    """Même calcul que Registre.similarites."""
    bases = []
    for cle, photos in galerie.items():
        sims = np.array([requete["v"] @ p["v"] for p in photos])
        bases.append((float(sims.max()), cle, sims))
    bases.sort(key=lambda b: -b[0])
    sortie = []
    for rang, (s, cle, sims) in enumerate(bases):
        if rang < candidats:
            points = max(vision.appariement_sift(requete["s"], galerie[cle][i]["s"]) for i in np.argsort(-sims)[:4])
            s += bonus * min(points, plafond)
        sortie.append(s)
    return sorted(sortie, reverse=True)


def main():
    random.seed(2)
    fiches = e.fiches()
    for cle in ("radiata", "sulcata"):
        animaux = {}
        for f in fiches:
            if f["cle"] == cle:
                animaux.setdefault(f["obs"], []).append(f)
        noms = list(animaux)
        for k, par_fiche in ((5, 40), (5, 60), (10, 30), (2, 60)):
            if len(noms) < k * 1 + 1 or sum(len(v) for v in animaux.values()) < k * par_fiche + 20:
                print(f"{cle} : {k} fiches de {par_fiche} : pas assez de photos")
                continue
            resultats = []
            for _t in range(200):
                random.shuffle(noms)
                inconnue, reste = noms[0], noms[1:]
                vues = [p for n in reste for p in animaux[n]]
                random.shuffle(vues)
                galerie = {i: vues[i * par_fiche:(i + 1) * par_fiche] for i in range(k)}
                n = notes(random.choice(animaux[inconnue]), galerie)
                resultats.append((n[0], n[0] - n[1]))
            ligne = f"{cle}, {k} fiches de {par_fiche} photos : fausse identité par image"
            for seuil in (0.6, 0.65, 0.7, 0.8):
                ligne += f" | {seuil:.2f} : {np.mean([s >= seuil and m >= 0.03 for s, m in resultats]):.1%}"
            print(ligne, flush=True)


if __name__ == "__main__":
    main()
