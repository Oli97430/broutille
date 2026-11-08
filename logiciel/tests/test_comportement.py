"""
Essais de l'analyse du comportement, sur un journal inventé dont on connaît les réponses.

    python tests/test_comportement.py
"""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import comportement as c

FIN = date(2026, 11, 8)


def visite(cle, jour, heure, duree_s):
    d = datetime.combine(jour, datetime.strptime(heure, "%H:%M:%S").time())
    return {"id_individu": cle, "individu": cle.upper(), "date": d.strftime("%Y-%m-%d"), "heure": d.strftime("%H:%M:%S"),
            "duree_s": str(duree_s)}


def journal():
    j = []
    for k in range(20):                                       # 20 jours d'habitudes
        jour = FIN - timedelta(days=19 - k)
        j.append(visite("zoe", jour, "09:00:00", 1200))       # Zoé : 9 h, 20 min
        j.append(visite("leon", jour, "09:05:00", 900))       # Léon mange avec Zoé
        if k < 13:                                            # Max vient à 15 h... puis plus du tout
            j.append(visite("max", jour, "15:00:00", 600))
    # Bruno arrive 3 fois pendant le repas de Léon, qui part dans la minute
    for k in range(3):
        jour = FIN - timedelta(days=k + 1)
        j.append(visite("bruno", jour, "09:15:00", 900))
    j.append({"id_individu": "", "individu": "Inconnue", "date": "2026-11-07", "heure": "09:00:00", "duree_s": "500"})
    return j


def main():
    j = journal()
    s = c.sejours(j, fin=FIN)
    res = []
    r = c.rythme(s)
    res.append(("rythme : Zoé mange à 9 h, pas à 15 h", r["zoe"][9] > 0 and r["zoe"][15] == 0, f"{r['zoe'][9]:.0f} min"))
    res.append(("rythme : Inconnue ignorée", set(r) == {"zoe", "leon", "max", "bruno"}, str(sorted(r))))
    reg = c.regularite(s)
    res.append(("régularité : Zoé arrive à 9 h 00 pile", abs(reg["zoe"]["arrivee_moy"] - 9) < 0.01 and reg["zoe"]["ecart_min"] < 1,
                c.heure_lisible(reg["zoe"]["arrivee_moy"])))
    reseau = c.reseau_social(s)
    zl = reseau.get(("leon", "zoe"))
    res.append(("réseau : Zoé et Léon mangent ensemble", zl and zl["fois"] >= 20 and zl["affinite"] > 0.5,
                f"{zl}"))
    res.append(("réseau : Max ne croise personne", not any("max" in p for p in reseau), ""))
    comptes, classement = c.dominance(s)
    # Léon (9 h 05 → 9 h 20) part 5 min après l'arrivée de Bruno à 9 h 15 : pas dans la minute
    res.append(("dominance : départ 5 min après, pas un déplacement", comptes.get(("bruno", "leon"), 0) == 0, str(comptes)))
    j2 = j + [visite("bruno", FIN, "09:19:30", 600)]          # arrive 30 s avant la fin du repas de Léon
    comptes, classement = c.dominance(c.sejours(j2, fin=FIN))
    res.append(("dominance : Bruno fait partir Léon", comptes.get(("bruno", "leon"), 0) == 1 and classement[0][0] == "bruno",
                str(classement[:2])))
    sa = c.sante(s, fin=FIN)
    res.append(("santé : Max absent depuis 7 jours signalé", any("pas venue" in a for a in sa["max"]["alertes"]),
                str(sa["max"]["alertes"])))
    res.append(("santé : Zoé sans alerte", not sa["zoe"]["alertes"], str(sa["zoe"]["alertes"])))
    res.append(("santé : Bruno, trop récent, sans alerte", not sa["bruno"]["alertes"], ""))
    noms = c.noms(j)
    img = c.image_rythme(r, noms)
    img2 = c.image_reseau(reseau, {k: sum(v) for k, v in r.items()}, noms)
    res.append(("images", img.size[1] > 100 and img2.size == (620, 520), f"{img.size} {img2.size}"))
    ok = True
    for nom, reussi, detail in res:
        print(("OK   " if reussi else "RATÉ ") + nom, "—", detail)
        ok &= bool(reussi)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
