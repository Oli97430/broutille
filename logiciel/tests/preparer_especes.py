"""
Références d'espèces : BioCLIP seul, à partir du nom scientifique, confond les tortues terrestres
(une radiée sur deux passait pour une étoilée ou une charbonnière). On lui donne donc de vrais
exemples : 100 observations iNaturalist par espèce, une seule photo par animal. Seuls les vecteurs
sont gardés (modeles/references_especes.npz), pas les photos.

Une partie des photos est mise de côté pour mesurer la précision sur des animaux jamais vus.

    python tests/preparer_especes.py [nb_par_espece]
"""

import json
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vision

AGENT = {"User-Agent": "Broutille/1.0 (references d'especes de tortues)"}
LICENCES = "cc0,cc-by,cc-by-nc,cc-by-sa,cc-by-nc-sa"
PHOTOS = Path(__file__).parent / "photos_especes"
SORTIE = Path(__file__).resolve().parents[1] / "modeles" / "references_especes.npz"


def lire(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=AGENT), timeout=30) as r:
        return r.read()


def telecharger(sci, voulues):
    dossier = PHOTOS / sci.replace(" ", "_")
    dossier.mkdir(parents=True, exist_ok=True)
    if len(list(dossier.glob("*.jpg"))) >= voulues:
        return
    params = {"taxon_name": sci, "photos": "true", "photo_license": LICENCES, "per_page": 200, "order_by": "votes",
              "verifiable": "any", "captive": "any"}
    obs = json.loads(lire("https://api.inaturalist.org/v1/observations?" + urllib.parse.urlencode(params)))["results"]
    taches = [(dossier / f"{o['id']}.jpg", o["photos"][0]["url"].replace("square", "medium")) for o in obs if o.get("photos")]

    def une(t):
        if not t[0].exists():
            try:
                t[0].write_bytes(lire(t[1]))
            except OSError:
                pass

    with ThreadPoolExecutor(4) as e:
        list(e.map(une, taches[:int(voulues * 1.2)]))
    print(sci, len(list(dossier.glob("*.jpg"))), "photos", flush=True)
    time.sleep(1)


def main():
    voulues = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    for _nom, sci, _en in vision.ESPECES_DEFAUT:
        telecharger(sci, voulues)
    det, esp = vision.DetecteurTortues(), vision.ClasseurEspeces()
    vecteurs = {}
    for _nom, sci, _en in vision.ESPECES_DEFAUT:
        liste = []
        for p in sorted((PHOTOS / sci.replace(" ", "_")).glob("*.jpg")):
            image = cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                continue
            d = det.detecter(image)
            if d:
                liste.append(esp.vecteur(vision.recadrer(image, max(d, key=lambda x: x[0])[1])))
        vecteurs[sci] = np.stack(liste)
        print(sci, len(liste), "tortues détectées", flush=True)

    # précision sur des animaux mis de côté : 1 sur 4 tour à tour
    for noms in (list(vecteurs)[:2], list(vecteurs)):
        bons, totaux = dict.fromkeys(noms, 0), dict.fromkeys(noms, 0)
        for pli in range(4):
            classes = [np.delete(vecteurs[n], np.arange(pli, len(vecteurs[n]), 4), axis=0) for n in noms]
            W, b = vision.entrainer_lineaire(classes, vision.ClasseurEspeces.ECHELLE)
            for i, n in enumerate(noms):
                choix = (vision.ClasseurEspeces.ECHELLE * vecteurs[n][pli::4] @ W + b).argmax(axis=1)
                totaux[n] += len(choix)
                bons[n] += int((choix == i).sum())
        for n in noms:
            print(f"{n} : {bons[n]}/{totaux[n]} ({bons[n] / max(totaux[n], 1):.1%})")
        print(f"{len(noms)} espèces : {sum(bons.values()) / sum(totaux.values()):.1%}")
    SORTIE.parent.mkdir(exist_ok=True)
    np.savez_compressed(SORTIE, **{n: v.astype(np.float32) for n, v in vecteurs.items()})
    print("Écrit :", SORTIE, flush=True)


if __name__ == "__main__":
    main()
