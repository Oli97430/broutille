"""Plusieurs caméras : colonne « camera » au journal (ancien journal mis à jour sans perte), clips
nommés par caméra, deux surveillances en même temps dans l'application (modèles factices).
Lancer : python tests/test_multicam.py"""
import ctypes
import sys
import tempfile
import time
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cv2
import numpy as np

import broutille_cam as m

ok = 0


def verifier(nom, condition, detail=""):
    global ok
    print(("OK   " if condition else "ÉCHEC") + f" {nom} {detail}")
    if not condition:
        raise SystemExit(1)
    ok += 1


d = Path(tempfile.mkdtemp(prefix="broutille_multicam_"))

# --- ancien journal (14 colonnes) : mis à jour au premier ajout, rien de perdu
anciennes = m.COLONNES[:-1]
(d / "visites.csv").write_text(";".join(anciennes) + "\n" +
                               "v1;2026-11-01;10:00:00;60;Zoé;Tortue radiée;0.9;a.mp4;;image;;t1;;\n", encoding="utf-8-sig")
m.ajouter_ligne(d, {"id_visite": "v2", "date": "2026-11-02", "heure": "11:00:00", "duree_s": "30", "individu": "Léon",
                    "espece": "Tortue radiée", "camera": "Abri"})
lignes = m.lire_journal(d)
entete = (d / "visites.csv").read_text(encoding="utf-8-sig").splitlines()[0].split(";")
verifier("ancien journal mis à jour sans perte", entete == m.COLONNES and [l["id_visite"] for l in lignes] == ["v1", "v2"]
         and lignes[0]["camera"] == "" and lignes[1]["camera"] == "Abri" and lignes[0]["id_individu"] == "t1", entete[-2:])

# --- application : deux caméras sur deux vidéos, en même temps
import broutille_app as A
import vision


class FauxDetecteur:
    def charger(self):
        pass

    def detecter(self, image):
        return []


class FauxClasseur:
    especes = [("Tortue radiée", "Astrochelys radiata")]

    def charger(self):
        pass


class FauxDescripteur:
    def charger(self):
        pass


vision.DetecteurTortues = lambda *a, **k: FauxDetecteur()
vision.ClasseurEspeces = lambda *a, **k: FauxClasseur()
vision.Descripteur = lambda *a, **k: FauxDescripteur()
vision.appareil = lambda: "cpu"
A.CONFIG = d / "config.json"                       # jamais le vrai ~/.broutille.json
videos = []
for k, couleur in enumerate(((40, 120, 50), (90, 60, 30))):
    chemin = d / f"camera{k}.mp4"
    e = cv2.VideoWriter(str(chemin), cv2.VideoWriter_fourcc(*"mp4v"), 10, (640, 360))
    for i in range(600):
        im = np.full((360, 640, 3), couleur, np.uint8)
        cv2.circle(im, (50 + i % 500, 180), 30, (200, 200, 200), -1)
        e.write(im)
    e.release()
    videos.append(str(chemin))
A.CONFIG.write_text(__import__("json").dumps({"dossier": str(d / "donnees"), "source": videos[0]}), encoding="utf-8")
ctypes.windll.shcore.SetProcessDpiAwareness(2)
root = tk.Tk()
app = A.App(root)
root.state("normal")
root.geometry("1400x860+0+0")
verifier("ancienne source devenue la 1re caméra", [c["source"] for c in app.cfg["cameras"]] == [videos[0]])
app.cfg["cameras"].append({"id": "c2", "nom": "Abri", "source": videos[1]})
app.tout_demarrer()
for _ in range(80):
    root.update()
    time.sleep(0.05)
verifier("deux surveillances en même temps", set(app.surveillances) == {"c1", "c2"}, list(app.surveillances))
verifier("images des deux caméras reçues", set(app.image_web) == {"c1", "c2"}, list(app.image_web))
clips_noms = [s.camera_id for s in app.surveillances.values()]
verifier("chaque surveillance connaît sa caméra", sorted(clips_noms) == ["c1", "c2"])
app.choisir_camera("c2")
for _ in range(20):
    root.update()
    time.sleep(0.05)
verifier("caméra affichée changée", app.cfg["camera_courante"] == "c2" and app.surveillance is app.surveillances["c2"]
         and app.cfg["source"] == videos[1])
x, y = root.winfo_rootx(), root.winfo_rooty()
from PIL import ImageGrab
ImageGrab.grab((x, y, x + root.winfo_width(), y + root.winfo_height()), all_screens=True).save(d / "ecran.png")
print("capture :", d / "ecran.png")
app.arreter("c1")
for _ in range(60):
    root.update()
    time.sleep(0.05)
verifier("arrêter une caméra laisse l'autre tourner", set(app.surveillances) == {"c2"}, list(app.surveillances))
etat = app.etat_pastilles
verifier("pastilles à jour", [e[2] for e in etat] == [False, True], etat)
app.quitter()
for _ in range(200):
    try:
        root.update()
    except tk.TclError:
        break
    time.sleep(0.05)
reglages = __import__("json").loads(A.CONFIG.read_text(encoding="utf-8"))
verifier("caméras gardées dans les réglages", [c["nom"] for c in reglages["cameras"]] == ["Mangeoire", "Abri"])
print(f"\n{ok} vérifications réussies")
