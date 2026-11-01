"""
Banc d'essai sur les photos iNaturalist (tests/photos_inat) :
  - détection : une tortue trouvée sur la photo ?
  - espèce    : radiée / sillonnée justes ?
  - individu  : pour chaque observation, 1re photo = galerie, autres photos = requêtes.
                Rang 1, et séparation « même animal / animal différent » (seuil à 1 % de faux).

    python tests/evaluer_reconnaissance.py [--max 200]
"""

import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vision

DOSSIER = Path(__file__).parent / "photos_inat"
NOMS = {"radiata": "Tortue radiée", "sulcata": "Tortue sillonnée"}
BONUS, PLAFOND = 0.01, 40


def lire(p):
    return cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=100000)
    a = ap.parse_args()
    det, esp, des = vision.DetecteurTortues(), vision.ClasseurEspeces(), vision.Descripteur()
    fiches, vues, trouvees = [], 0, 0
    bonnes_esp, total_esp = defaultdict(int), defaultdict(int)
    t_det, t_des = 0.0, 0.0
    for cle in NOMS:
        for p in sorted((DOSSIER / cle).glob("*.jpg"))[:a.max]:
            image = lire(p)
            if image is None:
                continue
            vues += 1
            t = time.time()
            d = det.detecter(image)
            t_det += time.time() - t
            if not d:
                continue
            trouvees += 1
            boite = max(d, key=lambda x: x[0])[1]
            _p, classes = esp.classer(vision.recadrer(image, boite))
            total_esp[cle] += 1
            bonnes_esp[cle] += classes[0][0] == NOMS[cle]
            t = time.time()
            tortue = vision.isoler_tortue(image, boite)
            v = des.decrire(tortue)
            t_des += time.time() - t
            fiches.append({"cle": cle, "obs": p.stem.split("_")[0], "v": v, "s": vision.points_sift(tortue)})
    print(f"Détection : {trouvees}/{vues} ({trouvees / max(vues, 1):.1%}), {t_det / max(vues, 1):.2f} s/image ; "
          f"description : {t_des / max(trouvees, 1):.2f} s")
    for cle in NOMS:
        print(f"Espèce {cle} : {bonnes_esp[cle]}/{total_esp[cle]} ({bonnes_esp[cle] / max(total_esp[cle], 1):.1%})")

    for cle in list(NOMS) + ["toutes"]:
        evaluer_identite(cle, [f for f in fiches if cle in (f["cle"], "toutes")])


def evaluer_identite(cle, sel):
    """Galerie : 1re photo de chaque animal. Requêtes : ses autres photos. Monde fermé (l'animal est
    en galerie) et monde ouvert (on le retire : toute acceptation est alors une fausse identité)."""
    par_obs = defaultdict(list)
    for f in sel:
        par_obs[f["obs"]].append(f)
    galerie = [l[0] for l in par_obs.values()]
    requetes = [(f, o) for o, l in par_obs.items() if len(l) >= 2 for f in l[1:]]
    if not requetes:
        return
    G = np.stack([g["v"][0] for g in galerie])
    obs_g = [g["obs"] for g in galerie]

    def classement(f, sans=None):
        sims = (f["v"] @ G.T).max(axis=0)
        idx = [i for i in np.argsort(-sims) if obs_g[i] != sans][:8]
        points = {i: vision.appariement_sift(f["s"], galerie[i]["s"]) for i in idx[:3]}
        notes = sorted(((sims[i] + BONUS * min(points.get(i, 0), PLAFOND), i) for i in idx), reverse=True)
        return notes

    fermes = [(classement(f), o) for f, o in requetes]
    ouverts = [classement(f, sans=o) for f, o in requetes]
    rang1 = np.mean([obs_g[n[0][1]] == o for n, o in fermes])
    rang5 = np.mean([o in [obs_g[i] for _s, i in n[:5]] for n, o in fermes])
    print(f"[{cle}] {len(galerie)} animaux, {len(requetes)} requêtes : rang 1 {rang1:.1%}, rang 5 {rang5:.1%}")
    print("    seuil marge | juste  fausse  refusée | monde ouvert : fausse identité")
    for seuil in (0.45, 0.5, 0.55, 0.6, 0.7, 0.8):
        for marge in (0.03, 0.08):
            def accepte(n):
                return n[0][0] >= seuil and n[0][0] - n[1][0] >= marge
            juste = np.mean([accepte(n) and obs_g[n[0][1]] == o for n, o in fermes])
            fausse = np.mean([accepte(n) and obs_g[n[0][1]] != o for n, o in fermes])
            ouvert = np.mean([accepte(n) for n in ouverts])
            print(f"    {seuil:.2f} {marge:.2f}  | {juste:6.1%} {fausse:6.1%} {1 - juste - fausse:6.1%}  | {ouvert:6.1%}")


if __name__ == "__main__":
    main()
