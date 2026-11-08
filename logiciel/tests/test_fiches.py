"""Identité des tortues (fiches.py) et album / carnet / vues du registre. Lancer : python tests/test_fiches.py"""
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PIL import Image

import broutille_cam as m
import fiches

AUJ = date(2026, 11, 8)
ok = 0


def verifier(nom, condition):
    global ok
    print(("OK   " if condition else "ÉCHEC") + " " + nom)
    if not condition:
        raise SystemExit(1)
    ok += 1


def refuse(texte):
    try:
        fiches.lire_date_partielle(texte, AUJ)
        return False
    except ValueError:
        return True


verifier("dates partielles", fiches.lire_date_partielle("2019", AUJ) == "2019"
         and fiches.lire_date_partielle("03/2019", AUJ) == "2019-03"
         and fiches.lire_date_partielle("15/03/2019", AUJ) == "2019-03-15"
         and fiches.lire_date_partielle("2019-03-15", AUJ) == "2019-03-15"
         and fiches.lire_date_partielle("15.03.19", AUJ) == "2019-03-15"
         and fiches.lire_date_partielle("  ", AUJ) == "")
verifier("dates impossibles refusées", refuse("31/02/2020") and refuse("2027") and refuse("11/2026") is False and refuse("12/2026")
         and refuse("09/11/2026") and refuse("13/2020") and refuse("abc") and refuse("1850"))
verifier("aller-retour saisie", fiches.date_saisie("2019-03-15") == "15/03/2019" and fiches.date_saisie("2019-03") == "03/2019")
verifier("date lisible", fiches.date_lisible("2019-03") == "mars 2019" and fiches.date_lisible("2019") == "2019")
verifier("âges", fiches.age_lisible("2019-11-08", AUJ) == "7 ans"
         and fiches.age_lisible("2025-08-01", AUJ) == "1 an et 3 mois"
         and fiches.age_lisible("2026-06-01", AUJ) == "5 mois"
         and fiches.age_lisible("2026-11-01", AUJ) == "moins d'un mois"
         and fiches.age_lisible("2019", AUJ) == "environ 7 ans"
         and fiches.age_lisible("", AUJ) == "")
verifier("résumé d'identité", fiches.resume_identite(
    {"espece": "Tortue d'Hermann", "sexe": "Femelle", "naissance": "2019"}, AUJ)
    == "Tortue d'Hermann  ·  Femelle  ·  environ 7 ans (née en 2019)"
    and fiches.resume_identite({"espece": "Tortue grecque"}, AUJ) == "Tortue grecque")

d = Path(tempfile.mkdtemp(prefix="broutille_fiches_"))
r = m.Registre(d, descripteur=object())
a, b = r.creer("Zoé", "Tortue d'Hermann"), r.creer("Zoé bis", "Tortue d'Hermann")
r.modifier(a, sexe="Femelle", naissance="2019")
r.modifier(b, signes="écaille marquée", naissance="2018")

photo = d / "souvenir.jpg"
Image.new("RGB", (3000, 1500), (80, 120, 60)).save(photo)
(d / "illisible.jpg").write_text("pas une image")
ecrits = r.ajouter_album(a, [photo, d / "illisible.jpg", photo])
verifier("album : copie réduite, doublon renommé, illisible ignoré", len(ecrits) == 2 and len(r.album(a)) == 2
         and max(Image.open(r.album(a)[0]).size) == 2000)
verifier("album hors reconnaissance", not list((d / "individus" / a).glob("*.jpg")))
verifier("photo de profil : album par défaut", r.photo_profil(a) == r.album(a)[0])
r.modifier(a, profil=f"{m.ALBUM}/{ecrits[1]}")
verifier("photo de profil choisie", r.photo_profil(a).name == ecrits[1])
r.retirer_album(a, ecrits[1])
verifier("retirer la photo de profil l'oublie", "profil" not in r.fiches[a] and len(r.album(a)) == 1)

r.ajouter_note(a, "2026-10-01", "Vermifuge", " Panacur ")
r.ajouter_note(a, "2026-03-01", "Hibernation", "Réveil")
verifier("carnet trié par date", [n["type"] for n in r.carnet(a)] == ["Hibernation", "Vermifuge"]
         and r.carnet(a)[1]["texte"] == "Panacur")
try:
    r.ajouter_note(a, "2026-10-02", "Note", "  ")
    verifier("note vide refusée", False)
except ValueError:
    verifier("note vide refusée", True)
r.retirer_note(a, 0)
verifier("note retirée", len(r.carnet(a)) == 1)

vue = d / "individus" / a / "import_1.jpg"
Image.new("RGB", (60, 40)).save(vue)
r.modifier(a, profil=vue.name)
r.retirer_vue(a, vue.name)
verifier("vue retirée de la galerie", not vue.exists() and "profil" not in r.fiches[a])

r.ajouter_note(b, "2026-05-05", "Soin", "Bain")
r.ajouter_album(b, [photo])
r.fusionner(b, a)
f = r.fiches[a]
verifier("fusion : album, carnet et identité réunis", len(r.album(a)) == 2 and len(f["carnet"]) == 2
         and f["signes"] == "écaille marquée" and f["naissance"] == "2019" and f["sexe"] == "Femelle")

r2 = m.Registre(d, descripteur=object())
verifier("tout est relu depuis le disque", r2.fiches[a]["signes"] == "écaille marquée" and len(r2.carnet(a)) == 2)
print(f"\n{ok} vérifications réussies")
