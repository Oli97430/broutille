"""
Ouvre la vraie interface sur un dossier temporaire, joue une vidéo de visite et capture la fenêtre.

    python tests/test_interface.py <video.mp4> <capture.png> [<photo A> ...]
"""

import shutil
import sys
import tempfile
import tkinter as tk
from pathlib import Path

from PIL import ImageGrab

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import broutille_app as appli
import broutille_cam as moteur


def main():
    video, capture = sys.argv[1], sys.argv[2]
    dossier = Path(tempfile.mkdtemp(prefix="broutille_ui_"))
    appli.CONFIG = dossier / "config.json"
    appli.DEFAUTS["dossier"] = str(dossier / "visites")
    appli.DEFAUTS["source"] = video
    root = tk.Tk()
    app = appli.App(root)
    root.state("normal")
    root.geometry("1440x900+20+20")
    etapes = {"pret": False, "capture_direct": False}

    def surveiller():
        if app.modeles_prets and not etapes["pret"]:
            etapes["pret"] = True
            cle = app.registre.creer("Zoé", "Tortue radiée")
            if len(sys.argv) > 3:
                moteur.inscrire_photos(app.registre, app.detecteur, cle, sys.argv[3:])
            app.charger_historique()
            app.var_source.set(video)
            app.demarrer()
        if etapes["pret"] and app.surveillance and not etapes["capture_direct"] and app.surveillance.pistes:
            nom = next((p.etiquette for p in app.surveillance.pistes if p.analyses >= 3), None)
            if nom:
                etapes["capture_direct"] = True
                root.update()
                root.lift()
                root.attributes("-topmost", True)
                root.after(300, lambda: ImageGrab.grab(bbox=fenetre(root)).save(capture.replace(".png", "_direct.png")))
        if etapes["pret"] and app.surveillance is None and etapes.get("demarre"):
            root.after(600, fin)
            return
        if app.surveillance:
            etapes["demarre"] = True
        root.after(200, surveiller)

    def fin():
        root.update()
        root.attributes("-topmost", True)
        root.lift()
        root.update()
        ImageGrab.grab(bbox=fenetre(root)).save(capture)
        print("Visites :", [(l["individu"], l["proposition"], l["duree_s"]) for l in moteur.lire_journal(dossier / "visites")])
        print("Lignes affichées :", len(app.lignes), "; tortues affichées :", len(app.arbre_t.get_children()))
        root.destroy()

    root.after(500, surveiller)
    root.after(240000, root.destroy)     # filet : jamais de test bloqué
    root.mainloop()
    shutil.rmtree(dossier, ignore_errors=True)


def fenetre(root):
    x, y = root.winfo_rootx(), root.winfo_rooty()
    return x, y, x + root.winfo_width(), y + root.winfo_height()


if __name__ == "__main__":
    main()
