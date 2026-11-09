"""
Essais des déplacements : trajets inventés dont on connaît les réponses, puis écriture et relecture
du fichier des positions.

    python tests/test_deplacements.py
"""

import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import broutille_cam as m
import deplacements as dep

L, H = 1600, 900
T = 80                    # cadre de 80 px : une longueur de carapace


def ligne(id_visite, cle, heure):
    return {"id_visite": id_visite, "id_individu": cle, "individu": cle, "date": "2026-11-08", "heure": heure,
            "duree_s": "60"}


def points(chemin):
    """[(t, x, y)] -> positions au format du fichier : (t, x, y, l, h, image_l, image_h)."""
    return [(t, int(x), int(y), T, T, L, H) for t, x, y in chemin]


def main():
    res = []
    journal = [ligne("v1", "zoe", "10:00:00"), ligne("v2", "leon", "10:00:00"), ligne("v3", "max", "10:00:00"),
               ligne("v4", "rose", "11:00:00"), ligne("v5", "inconnue", "10:00:00")]
    journal[4]["id_individu"] = ""
    positions = {
        # Zoé marche tout droit : 1 longueur par seconde pendant 10 s ; Léon la suit à 1,5 longueur derrière
        "v1": points([(t, 200 + T * t, 400) for t in range(11)]),
        "v2": points([(t, 200 - 1.5 * T + T * t, 400) for t in range(11)]),
        # Max ne bouge pas (tremblement du cadre de 5 px)
        "v3": points([(t, 1200 + (5 if t % 2 else 0), 300) for t in range(11)]),
        # Rose arrive une heure après : jamais en même temps
        "v4": points([(t, 1200, 300) for t in range(11)]),
        "v5": points([(t, 700, 700) for t in range(11)]),
    }
    fin = datetime(2026, 11, 8).date()
    tr = dep.trajets(journal, positions, fin=fin)
    res.append(("trajets : visites nommées seules", sorted(c for c, _p in tr) == ["leon", "max", "rose", "zoe"],
                str(sorted(c for c, _p in tr))))
    act = dep.activite(tr)
    res.append(("activité : Zoé fait 10 longueurs", abs(act["zoe"]["distance"] - 10) < 0.01 and act["zoe"]["mouvement"] == 1,
                f"{act['zoe']['distance']:.1f}"))
    res.append(("activité : le tremblement de Max ne compte pas", act["max"]["distance"] == 0, f"{act['max']}"))
    carte, rapport = dep.carte_zones(tr, "max")
    i, j = max(((i, j) for i in range(18) for j in range(32)), key=lambda c: carte[c[0]][c[1]])
    res.append(("zones : Max reste en haut à droite", j == int(1240 / L * 32) and i == int(340 / H * 18) and abs(rapport - H / L) < 1e-6,
                f"case ({i}, {j})"))
    inter = dep.interactions(tr)
    zl = inter.get(("leon", "zoe"), {})
    res.append(("poursuite : Léon suit Zoé", zl.get("poursuites") == {"leon": 1}, str(zl)))
    res.append(("pas d'interaction avec Rose ni Max", set(inter) == {("leon", "zoe")}, str(sorted(inter))))
    # deux tortues l'une sur l'autre : un chevauchement
    pos2 = {"v1": points([(t, 600, 400) for t in range(6)]), "v2": points([(t, 600 + (20 if 2 <= t <= 3 else 300), 400)
                                                                         for t in range(6)])}
    inter2 = dep.interactions(dep.trajets(journal[:2], pos2, fin=fin))
    res.append(("chevauchement compté une fois", inter2.get(("leon", "zoe"), {}).get("chevauchements") == 1,
                str(inter2)))
    img = dep.image_zones(carte, rapport)
    res.append(("image des zones", img.size == (640, 360), str(img.size)))

    # écriture et relecture, comme la surveillance le fait à la fin d'une visite
    d = Path(tempfile.mkdtemp(prefix="broutille_positions_"))
    piste = m.Piste((10, 20, 30, 40), 100.0)
    piste.trajet = [(100.0, 10, 20, 30, 40), (101.0, 15, 20, 30, 40)]
    piste.taille_image = (L, H)
    # arrivée à 10:00:00,7 : le journal écrit 10:00:00, les temps comptent donc depuis la seconde ronde
    piste.arrivee = piste.arrivee.replace(microsecond=700000)
    m.ecrire_positions(d, "vX", piste)
    m.ecrire_positions(d, "vY", piste)
    (d / m.POSITIONS / f"{piste.arrivee:%Y-%m}.csv").open("a", encoding="utf-8").write("vZ;abîmée\n")
    lu = m.lire_positions(d)
    res.append(("positions écrites puis relues, ligne abîmée ignorée",
                lu.get("vX") == [(0.7, 10, 20, 30, 40, L, H), (1.7, 15, 20, 30, 40, L, H)] and set(lu) == {"vX", "vY"},
                str(lu.get("vX"))))
    shutil.rmtree(d, ignore_errors=True)

    ok = True
    for nom, reussi, detail in res:
        print(("OK   " if reussi else "RATÉ ") + nom, "—", detail)
        ok &= bool(reussi)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
