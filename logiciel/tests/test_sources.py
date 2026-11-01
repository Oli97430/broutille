"""
Test des sources réelles : capture d'une vraie fenêtre, et flux Internet servi en local.

    python tests/test_sources.py [adresse_d_un_direct_ou_d_une_page_video]
"""

import functools
import http.server
import shutil
import sys
import tempfile
import threading
import time
import tkinter as tk
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sources


def essai_fenetre():
    """Une fenêtre rouge puis cachée par une autre : la capture doit toujours voir le rouge."""
    root = tk.Tk()
    titre = "Broutille essai de capture"
    root.title(titre)
    root.geometry("640x360+100+100")
    root.configure(bg="#c80000")
    root.update()
    time.sleep(0.5)
    root.update()
    source = sources.PREFIXE_FENETRE + "essai de capture"
    camera, image = sources.ouvrir_source(source)
    resultats = []
    if camera is None:
        root.destroy()
        return [("fenêtre trouvée", False, "non")]
    b, g, r = image.reshape(-1, 3).mean(axis=0)
    resultats.append(("fenêtre capturée", r > 150 and g < 60, f"{image.shape[1]}x{image.shape[0]} BGR {b:.0f},{g:.0f},{r:.0f}"))
    resultats.append(("liste des fenêtres", any(titre == t for t, _h in sources.lister_fenetres()), ""))
    autre = tk.Toplevel(root)
    autre.geometry("800x600+50+50")
    autre.configure(bg="#00c800")
    autre.attributes("-topmost", True)
    root.update()
    time.sleep(0.5)
    root.update()
    ok, image = camera.read()
    b, g, r = image.reshape(-1, 3).mean(axis=0)
    resultats.append(("fenêtre cachée par une autre", ok and r > 150 and g < 60, f"BGR {b:.0f},{g:.0f},{r:.0f}"))
    root.iconify()
    root.update()
    time.sleep(0.5)
    ok, _image = camera.read()
    resultats.append(("fenêtre réduite : signalée", not ok, ""))
    root.deiconify()
    autre.destroy()
    root.update()
    time.sleep(0.3)
    root.geometry("800x500")
    root.update()
    time.sleep(0.3)
    ok, image = camera.read()
    resultats.append(("taille stable après redimensionnement", ok and image.shape[:2] == (360, 640), str(image.shape if ok else None)))
    camera.release()
    root.destroy()
    return resultats


def essai_flux():
    """Vidéo servie en HTTP local : même chemin qu'un flux Internet direct."""
    d = Path(tempfile.mkdtemp(prefix="broutille_flux_"))
    v = cv2.VideoWriter(str(d / "flux.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 10, (320, 180))
    for i in range(40):
        v.write(np.full((180, 320, 3), i * 5, np.uint8))
    v.release()

    class Discret(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *_a):
            pass

    serveur = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Discret, directory=str(d)))
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    source = f"http://127.0.0.1:{serveur.server_address[1]}/flux.mp4"
    camera, image = sources.ouvrir_source(source)
    n = 0
    if camera is not None:
        while camera.read()[0]:
            n += 1
        camera.release()
    serveur.shutdown()
    shutil.rmtree(d, ignore_errors=True)
    return [("flux HTTP lu", n > 30, f"{n} images")]


def essai_page(adresse):
    debut = time.time()
    camera, image = sources.ouvrir_source(adresse)
    if camera is None:
        return [("page vidéo", False, "aucune image")]
    n = sum(camera.read()[0] for _i in range(30))
    camera.release()
    return [("page vidéo (yt-dlp)", n >= 25, f"{image.shape[1]}x{image.shape[0]}, {n}/30 images, {time.time() - debut:.0f} s")]


def main():
    ok = True
    resultats = essai_fenetre() + essai_flux()
    if len(sys.argv) > 1:
        resultats += essai_page(sys.argv[1])
    for nom, reussi, detail in resultats:
        print(("OK   " if reussi else "RATÉ ") + nom, "—", detail)
        ok &= bool(reussi)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
