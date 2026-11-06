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


def ouvrir_en_animant(root, source):
    """ouvrir_source observe la fenêtre plusieurs secondes : la boucle Tk doit tourner pendant
    ce temps, sinon Windows remplace la fenêtre « ne répond pas » par un fantôme."""
    resultat = {}
    fil = threading.Thread(target=lambda: resultat.update(zip(("camera", "image"), sources.ouvrir_source(source))))
    fil.start()
    while fil.is_alive():
        root.update()
        time.sleep(0.05)
    return resultat.get("camera"), resultat.get("image")


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
    camera, image = ouvrir_en_animant(root, source)
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
    # la source suit la nouvelle taille ; la surveillance la remet au format du clip sans déformer
    resultats.append(("redimensionnement suivi", ok and image.shape[:2] == (500, 800), str(image.shape if ok else None)))
    camera.release()
    root.destroy()
    return resultats


def essai_bandes():
    """Comme EZVIZ Studio : une vidéo verticale dans une tuile étroite, le reste de la fenêtre
    en gris uni. La capture ne doit garder que la tuile."""
    root = tk.Tk()
    root.title("Broutille essai de bandes")
    root.geometry("900x500+120+120")
    root.configure(bg="#404040")
    bruit = np.random.default_rng(1).integers(0, 256, (420, 260, 3), np.uint8)
    entete = f"P6 {bruit.shape[1]} {bruit.shape[0]} 255 ".encode()
    photo = tk.PhotoImage(data=entete + bruit[:, :, ::-1].tobytes(), format="PPM")
    tk.Label(root, image=photo, bd=0, highlightthickness=0).place(x=30, y=40)
    root.update()
    time.sleep(0.5)
    root.update()
    camera, image = ouvrir_en_animant(root, sources.PREFIXE_FENETRE + "essai de bandes")
    if camera is None:
        root.destroy()
        return [("bandes unies : fenêtre trouvée", False, "non")]
    ok, image = camera.read()
    camera.release()
    root.destroy()
    h, l = image.shape[:2] if ok else (0, 0)
    return [("bandes unies enlevées", ok and abs(l - 260) <= 4 and abs(h - 420) <= 4, f"{l}x{h}, attendu 260x420")]


def essai_lecteur_cache():
    """Comme EZVIZ Studio derrière d'autres fenêtres : une vidéo qui bouge au milieu d'une
    interface fixe (boutons, liste). La fenêtre est cachée par une autre ; la capture doit
    voir la vidéo et ne garder qu'elle."""
    root = tk.Tk()
    root.title("Broutille essai de lecteur")
    root.geometry("900x600+150+150")
    root.configure(bg="#f4f4f4")
    for i, texte in enumerate(("Caméras", "Jardin", "Galerie", "Réglages")):
        tk.Button(root, text=texte, width=14).place(x=10, y=20 + 40 * i)
    tk.Label(root, text="caméra jardin", bg="#f4f4f4").place(x=200, y=10)
    rng = np.random.default_rng(2)
    fond = rng.integers(40, 200, (300, 480, 3), np.uint8)
    video = tk.Label(root, bd=0, highlightthickness=0)
    video.place(x=200, y=40)
    cache = tk.Toplevel(root)
    cache.title("fenêtre posée par-dessus")
    cache.geometry("1000x700+100+100")
    cache.configure(bg="#00c800")
    cache.attributes("-topmost", True)

    def image_suivante():
        bruit = np.clip(fond.astype(np.int16) + rng.integers(-12, 13, fond.shape), 0, 255).astype(np.uint8)
        photo = tk.PhotoImage(data=f"P6 480 300 255 ".encode() + bruit[:, :, ::-1].tobytes(), format="PPM")
        video.configure(image=photo)
        video.image = photo

    image_suivante()
    root.update()
    time.sleep(0.3)
    root.update()
    resultat = {}
    fil = threading.Thread(target=lambda: resultat.update(
        zip(("camera", "image"), sources.ouvrir_source(sources.PREFIXE_FENETRE + "essai de lecteur"))))
    fil.start()
    while fil.is_alive():
        image_suivante()
        root.update()
        time.sleep(0.08)
    camera, image = resultat.get("camera"), resultat.get("image")
    mode = camera.mode if camera else "aucun"
    if camera:
        camera.release()
    root.destroy()
    if image is None:
        return [("lecteur caché : capturé", False, mode)]
    h, l = image.shape[:2]
    vert = image.reshape(-1, 3).mean(axis=0)[1] > 180 and image.reshape(-1, 3).mean(axis=0)[0] < 60
    return [("lecteur caché : capturé, pas la fenêtre du dessus", not vert, mode),
            ("lecteur caché : seule la vidéo est gardée", abs(l - 480) <= 6 and abs(h - 300) <= 6,
             f"{l}x{h}, attendu 480x300")]


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
    resultats = essai_fenetre() + essai_bandes() + essai_lecteur_cache() + essai_flux()
    if len(sys.argv) > 1:
        resultats += essai_page(sys.argv[1])
    for nom, reussi, detail in resultats:
        print(("OK   " if reussi else "RATÉ ") + nom, "—", detail)
        ok &= bool(reussi)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
