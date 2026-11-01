"""
Photos réelles pour tester la reconnaissance : observations iNaturalist de tortues
radiées et sillonnées qui ont au moins 2 photos. Plusieurs photos d'une observation
montrent le même animal, ce qui donne de vraies paires pour la ré-identification.

Photos sous licence Creative Commons, gardées en local pour les tests (photos_inat/ est
ignoré par git, elles ne sont pas redistribuées).

    python tests/telecharger_photos_test.py [nb_observations_par_espece]
"""

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

AGENT = {"User-Agent": "Carapace/1.0 (tests de reconnaissance de tortues)"}
ESPECES = {"radiata": "Astrochelys radiata", "sulcata": "Centrochelys sulcata"}
LICENCES = "cc0,cc-by,cc-by-nc,cc-by-sa,cc-by-nc-sa"
DOSSIER = Path(__file__).parent / "photos_inat"


def lire(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=AGENT), timeout=30) as r:
        return r.read()


def observations(nom, voulues):
    """Observations à 2 photos ou plus (captifs compris : c'est le cas de nos tortues)."""
    trouvees, page = [], 1
    while len(trouvees) < voulues and page <= 12:
        params = {"taxon_name": nom, "photos": "true", "photo_license": LICENCES, "per_page": 200, "page": page,
                  "order_by": "votes", "verifiable": "any", "captive": "any"}
        reponse = json.loads(lire("https://api.inaturalist.org/v1/observations?" + urllib.parse.urlencode(params)))
        if not reponse["results"]:
            break
        trouvees += [o for o in reponse["results"] if len(o.get("photos", [])) >= 2]
        page += 1
        time.sleep(1)
    return trouvees[:voulues]


def main():
    voulues = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    index = {}
    for cle, nom in ESPECES.items():
        dossier = DOSSIER / cle
        dossier.mkdir(parents=True, exist_ok=True)
        obs = observations(nom, voulues)
        print(f"{nom} : {len(obs)} observations", flush=True)
        for o in obs:
            for i, p in enumerate(o["photos"][:4]):
                cible = dossier / f"{o['id']}_{i}.jpg"
                index[f"{cle}/{cible.name}"] = {"licence": p.get("license_code"), "auteur": p.get("attribution"),
                                                "observation": o["id"]}
                if cible.exists():
                    continue
                try:
                    cible.write_bytes(lire(p["url"].replace("square", "large")))
                    time.sleep(0.25)
                except OSError as e:
                    print("  raté :", cible.name, e, flush=True)
    (DOSSIER / "attributions.json").write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding="utf-8")
    print("Terminé :", len(index), "photos", flush=True)


if __name__ == "__main__":
    main()
