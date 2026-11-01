"""
Test de bout en bout du moteur, sans webcam : une vidéo simule des visites à partir de vraies
photos (tests/photos_inat) collées sur une scène de jardin.

Scénario : A et B sont inscrites avec leurs deux photos, puis
  visite 1 : tortue A, reste immobile une partie du temps ; nommée A attendu
  visite 2 : tortue B ; nommée B attendu
  visite 3 : tortue C, jamais vue ; « Inconnue » attendu, pas le nom d'une autre
  visite 4 : une pierre grise ; aucune visite attendue
  visite 5 : A et B ensemble ; une ligne par tortue attendue

    python tests/test_moteur.py
"""

import shutil
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import broutille_cam as moteur
import vision

ICI = Path(__file__).parent
FPS, L, H = 12, 1280, 720


def decor():
    """Herbe bruitée et auges grises : un fond stable, un peu texturé."""
    g = np.random.default_rng(1)
    image = np.zeros((H, L, 3), np.uint8)
    image[:] = (50, 95, 60)
    bruit = cv2.GaussianBlur(g.integers(0, 60, (H, L, 1), dtype=np.uint8), (0, 0), 3)
    image = cv2.add(image, cv2.merge([bruit, bruit, bruit]))
    cv2.rectangle(image, (360, 560), (920, 650), (120, 120, 118), -1)
    return image


def lutin(det, chemin, cible=300):
    """Tortue découpée dans une photo : (image BGR, masque), à la taille voulue."""
    image = moteur.lire_image(chemin)
    d = det.detecter(image)
    if not d:
        return None
    x, y, w, h = max(d, key=lambda v: v[0])[1]
    t = image[y:y + h, x:x + w]
    e = cible / max(w, h)
    t = cv2.resize(t, None, fx=e, fy=e, interpolation=cv2.INTER_AREA)
    m = np.zeros(t.shape[:2], np.uint8)
    cv2.ellipse(m, (t.shape[1] // 2, t.shape[0] // 2), (t.shape[1] // 2 - 3, t.shape[0] // 2 - 3), 0, 0, 360, 255, -1)
    return t, cv2.GaussianBlur(m, (15, 15), 0)[..., None] / 255.0


def poser(fond, l, x, y):
    t, m = l
    h, w = t.shape[:2]
    x, y = int(x), int(y)
    # la tortue entre et sort du cadre : seule la partie visible est collée
    x0, x1, y0, y1 = max(x, 0), min(x + w, L), max(y, 0), min(y + h, H)
    if x0 >= x1 or y0 >= y1:
        return
    t, m = t[y0 - y:y1 - y, x0 - x:x1 - x], m[y0 - y:y1 - y, x0 - x:x1 - x]
    fond[y0:y1, x0:x1] = (t * m + fond[y0:y1, x0:x1] * (1 - m)).astype(np.uint8)


def pierre():
    t = np.full((180, 260, 3), 128, np.uint8)
    t = cv2.add(t, cv2.GaussianBlur(np.random.default_rng(2).integers(0, 70, (180, 260, 3), dtype=np.uint8), (0, 0), 4))
    m = np.zeros((180, 260), np.uint8)
    cv2.ellipse(m, (130, 90), (125, 85), 0, 0, 360, 255, -1)
    return t, cv2.GaussianBlur(m, (15, 15), 0)[..., None] / 255.0


def scene(ecriture, base, lutins, secondes):
    """Les lutins (lutin, x0, x1, y) traversent puis s'arrêtent, repartent ; le décor reste seul autour."""
    n = int(secondes * FPS)
    for i in range(n):
        image = base.copy()
        for l, x0, x1, y in lutins:
            p = min(1.0, i / (n * 0.3))             # arrivée, puis immobile
            p = p if i < n * 0.8 else max(0.0, 1 - (i - n * 0.8) / (n * 0.2))
            poser(image, l, x0 + (x1 - x0) * p, y)
        ecriture.write(image)


def creer_video(chemin, a, b, c):
    base = decor()
    e = cv2.VideoWriter(str(chemin), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (L, H))
    vide = lambda s: scene(e, base, [], s)
    vide(5)
    scene(e, base, [(a, -320, 300, 200)], 30)
    vide(30)
    scene(e, base, [(b, 1300, 650, 200)], 30)
    vide(30)
    scene(e, base, [(c, -320, 480, 200)], 30)
    vide(30)
    scene(e, base, [(pierre(), 1300, 700, 300)], 15)
    vide(30)
    scene(e, base, [(a, -320, 120, 200), (b, 1300, 800, 200)], 30)
    vide(30)
    e.release()


def main():
    det = vision.DetecteurTortues()
    photos = ICI / "photos_inat"
    par_obs = {}
    for p in sorted((photos / "radiata").glob("*.jpg")) + sorted((photos / "sulcata").glob("*.jpg")):
        par_obs.setdefault(p.stem.split("_")[0], []).append(p)
    choix = []
    for obs, liste in par_obs.items():
        l = [(p, lutin(det, p)) for p in liste[:3]]
        l = [x for x in l if x[1]]
        if len(l) >= 2:
            choix.append(l)
        if len(choix) == 3:
            break
    (a, b, c) = choix
    dossier = Path(tempfile.mkdtemp(prefix="broutille_test_"))
    video = dossier / "scene.mp4"
    # la vidéo montre la 1re vue ; la galerie contient la même vue et une autre
    creer_video(video, a[0][1], b[0][1], c[0][1])
    sortie = dossier / "visites"
    r = moteur.Registre(sortie)
    ida = r.creer("Tortue A", "Tortue radiée")
    idb = r.creer("Tortue B", "Tortue radiée")
    print("Inscrites :", moteur.inscrire_photos(r, det, ida, [p for p, _l in a]),
          moteur.inscrire_photos(r, det, idb, [p for p, _l in b]))
    messages = []
    s = moteur.Surveillance(str(video), sortie, registre=r, detecteur=det, analyse_toutes=2.0, apres=12, veille_toutes=5,
                            sur_message=messages.append)
    assert s.executer(), "\n".join(messages)
    lignes = moteur.lire_journal(sortie)
    for l in lignes:
        print(" ", l["individu"], "|", l["espece"], "|", l["duree_s"], "s |", l["confiance"], "| proposition :", l["proposition"], "| clip", l["video"])
    print("Clips :", sorted(p.name for p in sortie.glob("*.mp4")))
    noms = [l["individu"] for l in lignes]
    ok = True
    for condition, texte in ((len(lignes) == 5, "5 lignes : la pierre est ignorée"),
                             (noms[:2] == ["Tortue A", "Tortue B"], "visites 1 et 2 nommées"),
                             (len(noms) > 2 and noms[2] == moteur.INCONNUE, "tortue jamais vue : Inconnue"),
                             (sorted(noms[3:]) == ["Tortue A", "Tortue B"], "visite 5 : les deux tortues"),
                             (len(r.fiches) == 2, "pas de fiche en trop")):
        print(("OK   " if condition else "RATÉ ") + texte)
        ok &= bool(condition)
    # correction : la visite inconnue devient une nouvelle tortue et rejoint une galerie
    if len(lignes) >= 3:
        nouvelle = r.creer("Tortue C", "Tortue radiée")
        corrigee = moteur.corriger_visite(sortie, r, lignes[2]["id_visite"], nouvelle)
        condition = corrigee and corrigee["individu"] == "Tortue C" and bool(r.fichiers[nouvelle])
        print(("OK   " if condition else "RATÉ ") + "correction : la photo rejoint la galerie de C")
        ok &= bool(condition)
    shutil.rmtree(dossier, ignore_errors=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
