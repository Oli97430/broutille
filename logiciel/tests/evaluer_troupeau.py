"""
Identification dans un petit troupeau : le vrai usage d'une mangeoire, loin des 200 animaux du banc
d'essai. On tire au sort k tortues de même espèce (le cas le plus dur), avec 1 ou 2 photos de
référence chacune, puis on identifie une autre photo d'une d'entre elles. Une observation à 2 photos
sert aussi de « tortue jamais vue » : retirée de la galerie, elle ne doit recevoir aucun nom.

    python tests/evaluer_troupeau.py
"""

import pickle
import random
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vision

DOSSIER = Path(__file__).parent / "photos_inat"
CACHE = Path(__file__).parent / "fiches_test.pkl"     # écrit par ce script, en local ; jamais reçu d'ailleurs


def fiches():
    if CACHE.exists():
        return pickle.loads(CACHE.read_bytes())
    det, des = vision.DetecteurTortues(), vision.Descripteur()
    sortie = []
    for cle in ("radiata", "sulcata"):
        for p in sorted((DOSSIER / cle).glob("*.jpg")):
            image = cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)
            d = det.detecter(image) if image is not None else None
            if not d:
                continue
            tortue = vision.isoler_tortue(image, max(d, key=lambda x: x[0])[1])
            sortie.append({"cle": cle, "obs": p.stem.split("_")[0], "v": des.decrire(tortue)[0],
                           "s": vision.points_sift(tortue)})
    CACHE.write_bytes(pickle.dumps(sortie))
    return sortie


def note(requete, galerie, bonus=0.01, plafond=40):
    """Score de chaque animal : meilleure ressemblance d'une photo + cohérence des écailles."""
    notes = {}
    for animal, photos in galerie.items():
        sims = [float(requete["v"] @ p["v"]) for p in photos]
        i = int(np.argmax(sims))
        notes[animal] = sims[i] + bonus * min(vision.appariement_sift(requete["s"], photos[i]["s"]), plafond)
    return sorted(notes.items(), key=lambda x: -x[1])


def tirages(animaux, k, refs, n, inconnu):
    for _i in range(n):
        troupeau = random.sample(animaux, k)
        galerie, cible = {}, None
        for j, (obs, photos) in enumerate(troupeau):
            photos = random.sample(photos, len(photos))
            galerie[obs] = photos[:refs]
            if j == 0:
                cible = photos[refs]
        if inconnu:
            vraie = troupeau[0][0]
            del galerie[vraie]
        else:
            vraie = troupeau[0][0]
        yield note(cible, galerie), vraie


def main():
    random.seed(1)
    par_animal = defaultdict(list)
    espece = {}
    for f in fiches():
        par_animal[f["obs"]].append(f)
        espece[f["obs"]] = f["cle"]
    for cle in ("radiata", "sulcata"):
        for refs in (1, 2):
            animaux = [(o, l) for o, l in par_animal.items() if espece[o] == cle and len(l) > refs]
            print(f"{cle}, {refs} photo(s) de référence, {len(animaux)} animaux disponibles")
            for k in (3, 5, 10):
                connus = list(tirages(animaux, k, refs, 300, False))
                nouveaux = list(tirages(animaux, k + 1, refs, 300, True))
                rang1 = np.mean([n[0][0] == v for n, v in connus])
                ligne = f"  troupeau {k:2d} : rang 1 {rang1:5.1%} |"
                for seuil in (0.42, 0.5, 0.6):
                    juste = np.mean([n[0][1] >= seuil and n[0][0] == v for n, v in connus])
                    faux = np.mean([n[0][1] >= seuil for n, _v in nouveaux])
                    ligne += f"  seuil {seuil:.2f} : juste {juste:5.1%}, nouvelle prise pour une autre {faux:5.1%} |"
                print(ligne, flush=True)


if __name__ == "__main__":
    main()
