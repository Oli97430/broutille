"""
Test du mode direct, sans webcam ni modèles : la vraie boucle Surveillance tourne avec ses trois
fils, une fausse caméra et de faux modèles. C'est le chemin que test_moteur.py, qui lit un fichier
vidéo d'un bloc, ne couvre pas.

    python tests/test_direct.py
"""

import ctypes
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import broutille_cam as m
import sources

BASE = np.random.default_rng(0).normal(size=64)
BASE /= np.linalg.norm(BASE)
BOITE = (200, 100, 120, 120)
DEUX = [BOITE, (440, 100, 120, 120)]


class Descripteur:
    delai = 0.0

    def charger(self):
        pass

    def decrire(self, _image):
        time.sleep(self.delai)
        v = BASE + 0.09 * np.random.default_rng().normal(size=64)
        return (v / np.linalg.norm(v))[None].astype(np.float32)


class Detecteur:
    def __init__(self):
        self.boites = []

    def charger(self):
        pass

    def detecter(self, _image):
        return [(0.9, b) for b in list(self.boites)]


class Classeur:
    def classer(self, _image):
        return 0.95, [("Tortue radiée", 0.9), ("Tortue sillonnée", 0.1)]


class Camera:
    def __init__(self, annonce=30, reel=30, taille=(640, 360)):
        self.annonce, self.reel, self.taille = annonce, reel, taille
        self.relachee, self.lues, self.trou, self.derniere = False, 0, 0.0, None
        self.panne = self.gel = False

    def get(self, _p):
        return self.annonce

    def release(self):
        self.relachee = True

    def read(self):
        time.sleep(1 / self.reel)
        while self.gel:
            time.sleep(0.05)
        if self.panne:
            return False, None
        n = time.perf_counter()
        if self.derniere:
            self.trou = max(self.trou, n - self.derniere)
        self.derniere = n
        self.lues += 1
        image = np.random.default_rng(self.lues).integers(40, 200, (self.taille[1], self.taille[0], 3), dtype=np.uint8)
        return True, cv2.GaussianBlur(image, (0, 0), 2)


def monter(camera, dossier, **options):
    m.ouvrir_source = lambda *_a: (camera, camera.read()[1]) if camera else (None, None)
    d, r = Detecteur(), m.Registre(dossier, Descripteur())
    messages = []
    s = m.Surveillance("0", dossier, registre=r, detecteur=d, classeur=Classeur(), analyse_toutes=0.2, veille_toutes=0.2,
                       apres=options.pop("apres", 0.8), sur_message=messages.append, **options)
    s.presence_min = 0.3
    return s, r, d, messages


def lancer(s):
    resultat = {}

    def corps():
        try:
            resultat["ok"] = s.executer()
        except BaseException as e:
            resultat["erreur"] = f"{type(e).__name__}: {e}"

    t = threading.Thread(target=corps, daemon=True)
    t.start()
    return t, resultat


def attendre(condition, delai=10):
    fin = time.time() + delai
    while time.time() < fin:
        if condition():
            return True
        time.sleep(0.02)
    return False


def essai_correction_concurrente(racine):
    """Une correction lente ne doit écraser aucune visite."""
    cam = Camera()
    s, r, d, msgs = monter(cam, racine / "a")
    autre = r.creer("Léa", "Tortue radiée")
    t, res = lancer(s)
    attendre(lambda: cam.lues > 15)
    d.boites = [BOITE]
    time.sleep(1.2)
    d.boites = []
    attendre(lambda: m.lire_journal(s.dossier))
    premiere = m.lire_journal(s.dossier)[0]
    d.boites = [BOITE]
    time.sleep(1.2)
    r.descripteur.delai = 0.5
    correction = threading.Thread(target=m.corriger_visite, args=(s.dossier, r, premiere["id_visite"], autre))
    correction.start()
    d.boites = []
    correction.join(15)
    r.descripteur.delai = 0
    attendre(lambda: len(m.lire_journal(s.dossier)) >= 2, 5)
    s.arreter()
    t.join(15)
    lignes = m.lire_journal(s.dossier)
    return len(lignes) == 2 and "erreur" not in res and any(l["individu"] == "Léa" for l in lignes), f"{len(lignes)} lignes, {res}"


def essai_journal_bloque(racine):
    """Excel ouvert : la surveillance continue et aucune visite n'est perdue."""
    cam = Camera()
    s, r, d, msgs = monter(cam, racine / "b")
    t, res = lancer(s)
    attendre(lambda: cam.lues > 15)
    d.boites = DEUX
    time.sleep(1.2)
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateFileW.restype = ctypes.c_void_p
    k.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32,
                              ctypes.c_uint32, ctypes.c_void_p]
    k.CloseHandle.argtypes = [ctypes.c_void_p]
    verrou = k.CreateFileW(str(s.dossier / "visites.csv"), 0xC0000000, 1, None, 3, 0x80, None)   # lecture partagée seule
    d.boites = []
    time.sleep(3)
    vivant = t.is_alive() and not s.arret.is_set()
    k.CloseHandle(verrou)
    d.boites = [BOITE]
    time.sleep(1.2)
    d.boites = []
    attendre(lambda: len(m.lire_journal(s.dossier)) >= 3, 5)
    s.arreter()
    t.join(15)
    n_csv = len(m._lire_csv(s.dossier / "visites.csv"))
    return vivant and n_csv == 3 and cam.relachee, f"surveillance vivante {vivant}, {n_csv} lignes écrites, relâchée {cam.relachee}"


def essai_objet_fixe(racine):
    """Une pierre permanente ne doit priver de clip aucune tortue suivante."""
    cam = Camera()
    s, r, d, msgs = monter(cam, racine / "c", clip_max=1)
    t, res = lancer(s)
    pierre = (20, 20, 100, 100)
    attendre(lambda: cam.lues > 15)
    d.boites = [pierre]
    time.sleep(2.2)
    d.boites = [pierre, (400, 100, 120, 120)]
    time.sleep(1.5)
    enregistre = s.video is not None or len(list(s.dossier.glob("*.mp4"))) >= 2
    d.boites = [pierre]
    attendre(lambda: m.lire_journal(s.dossier), 5)
    lignes = m.lire_journal(s.dossier)
    clip_ok = bool(lignes) and (s.dossier / lignes[0]["video"]).exists()
    s.arreter()
    t.join(15)
    return enregistre and clip_ok, f"clips {len(list(s.dossier.glob('*.mp4')))}, lignes {[l['video'] for l in lignes]}"


def essai_fps_faux(racine):
    """Caméra annoncée à 30 i/s, réelle à 10 : le clip doit garder la bonne durée."""
    cam = Camera(30, 10)
    s, r, d, msgs = monter(cam, racine / "d", apres=0.5, avant=1)
    t, res = lancer(s)
    attendre(lambda: cam.lues > 15)
    d.boites = [BOITE]
    debut = time.time()
    time.sleep(3)
    d.boites = []
    fin = time.time()
    time.sleep(1.5)
    s.arreter()
    t.join(15)
    clip = next(s.dossier.glob("*.mp4"), None)
    if clip is None:
        return False, "aucun clip"
    c = cv2.VideoCapture(str(clip))
    n, f = c.get(cv2.CAP_PROP_FRAME_COUNT), c.get(cv2.CAP_PROP_FPS)
    c.release()
    duree = n / f
    return f < 15 and (fin - debut) * 0.6 < duree < (fin - debut) + 3, f"{n:.0f} images à {f:.1f} i/s = {duree:.1f} s"


def essai_fin_de_visite_sans_trou(racine):
    """Le calcul de la galerie en fin de visite ne doit pas interrompre la lecture."""
    cam = Camera()
    s, r, d, msgs = monter(cam, racine / "e")
    cle = r.creer("Zoé", "Tortue radiée")
    image = cv2.GaussianBlur(np.random.default_rng(1).integers(0, 255, (384, 384, 3), dtype=np.uint8), (0, 0), 3)
    r.ajouter_exemple(cle, image, "ref.jpg")
    t, res = lancer(s)
    attendre(lambda: cam.lues > 15)
    d.boites = [BOITE]
    time.sleep(2)
    d.boites = []
    r.descripteur.delai = 0.5
    cam.trou = 0
    time.sleep(3)
    r.descripteur.delai = 0
    s.arreter()
    t.join(15)
    return cam.trou < 0.5, f"plus long trou {cam.trou:.2f} s"


def essai_photo_retiree(racine):
    """Une photo retirée à la main de la galerie ne casse pas l'analyse."""
    cam = Camera()
    s, r, d, msgs = monter(cam, racine / "f")
    cle = r.creer("Zoé", "Tortue radiée")
    image = cv2.GaussianBlur(np.random.default_rng(1).integers(0, 255, (384, 384, 3), dtype=np.uint8), (0, 0), 3)
    nom = r.ajouter_exemple(cle, image, "ref.jpg")
    t, res = lancer(s)
    attendre(lambda: cam.lues > 15)
    (r.dossier / cle / nom).unlink()
    r.points.clear()
    d.boites = [BOITE]
    time.sleep(1.2)
    d.boites = []
    attendre(lambda: m.lire_journal(s.dossier), 5)
    s.arreter()
    t.join(15)
    erreurs = [x for x in msgs if "impossible" in x]
    return not erreurs and len(m.lire_journal(s.dossier)) == 1, f"erreurs {erreurs}"


def essai_reconnexion(racine):
    """Débranchement puis retour dans une autre résolution : le clip reste lisible."""
    cam = Camera()
    s, r, d, msgs = monter(cam, racine / "g", apres=1.5)
    autre = Camera(taille=(320, 180))
    t, res = lancer(s)
    attendre(lambda: cam.lues > 15)
    d.boites = [BOITE]
    time.sleep(1)
    m.ouvrir_source = lambda *_a: (autre, autre.read()[1])
    cam.panne = True
    attendre(lambda: autre.lues > 15)
    time.sleep(0.5)
    d.boites = []
    attendre(lambda: m.lire_journal(s.dossier), 6)
    s.arreter()
    t.join(15)
    lignes = m.lire_journal(s.dossier)
    if not lignes:
        return False, "aucune visite"
    c = cv2.VideoCapture(str(s.dossier / lignes[0]["video"]))
    n = c.get(cv2.CAP_PROP_FRAME_COUNT)
    c.release()
    return n > 20, f"{n:.0f} images lisibles, {msgs[-2:]}"


def essai_source_figee(racine):
    """Une source figée (read() bloqué) est relancée, et l'arrêt reste possible."""
    cam = Camera()
    s, r, d, msgs = monter(cam, racine / "h")
    s.SILENCE_MAX = 1
    autre = Camera()
    t, res = lancer(s)
    attendre(lambda: cam.lues > 15)
    m.ouvrir_source = lambda *_a: (autre, autre.read()[1])
    cam.gel = True
    relance = attendre(lambda: autre.lues > 5, 6)
    s.arreter()
    t.join(10)
    cam.gel = False
    return relance and not t.is_alive(), f"relancée {relance}, arrêtée {not t.is_alive()}"


def essai_source_absente(racine):
    s, r, d, msgs = monter(None, racine / "i")
    return s.executer() is False and any("aucune image" in x for x in msgs), msgs[-1:] and msgs[-1][:60]


def essai_journal_abime(racine):
    """Excel réenregistre en cp1252 et une panne coupe une ligne : le journal reste lisible."""
    d = racine / "j"
    d.mkdir()
    entete = ";".join(m.COLONNES)
    bonne = ";".join(["v1", "2026-01-01", "10:00:00", "60", "Zoé", "Tortue radiée", "1.00", "c.mp4", "p.jpg", "image", "", "t1", "", ""])
    (d / "visites.csv").write_bytes((entete + "\r\n" + bonne + "\r\nv2;2026-01").encode("cp1252"))
    lignes = m.lire_journal(d)
    return len(lignes) == 1 and lignes[0]["individu"] == "Zoé", str([l["individu"] for l in lignes])


def essai_galerie_abimee(racine):
    """Cache tronqué et photo vide ne doivent pas empêcher le démarrage."""
    r = m.Registre(racine / "k", Descripteur())
    cle = r.creer("Zoé", "Tortue radiée")
    image = cv2.GaussianBlur(np.random.default_rng(1).integers(0, 255, (384, 384, 3), dtype=np.uint8), (0, 0), 3)
    r.ajouter_exemple(cle, image, "ok.jpg")
    (r.dossier / cle / "vecteurs.npz").write_bytes(b"PK\x03\x04tronque")
    (r.dossier / cle / "vide.jpg").write_bytes(b"")
    r2 = m.Registre(racine / "k", Descripteur())
    r2.preparer()
    return len(r2.fichiers[cle]) == 1, str(r2.fichiers[cle])


def essai_prefixe_visite(racine):
    """La visite _3 ne doit pas emporter les photos de la visite _31."""
    r = m.Registre(racine / "l", Descripteur())
    cle = r.creer("Zoé", "Tortue radiée")
    image = cv2.GaussianBlur(np.random.default_rng(1).integers(0, 255, (384, 384, 3), dtype=np.uint8), (0, 0), 3)
    for nom in ("v_3_0.jpg", "v_31_0.jpg"):
        r.ajouter_exemple(cle, image, nom)
    retires = r.retirer_exemples(cle, "v_3")
    return [n for n, _c in retires] == ["v_3_0.jpg"], str([n for n, _c in retires])


def essai_galerie_pleine(racine):
    r = m.Registre(racine / "n", Descripteur())
    cle = r.creer("Zoé", "Tortue radiée")
    image = np.full((64, 64, 3), 100, np.uint8)
    r.ajouter_exemple(cle, image, "import_0.jpg")
    for i in range(m.MAX_EXEMPLES + 3):
        r.ajouter_exemple(cle, image, f"2026-01-01_{i:03d}.jpg")
    noms = r.fichiers[cle]
    return len(noms) == m.MAX_EXEMPLES and "import_0.jpg" in noms and "2026-01-01_000.jpg" not in noms, f"{len(noms)} photos"


def essai_fusion_en_cours(racine):
    r = m.Registre(racine / "o", Descripteur())
    a, b = r.creer("A", "Tortue radiée"), r.creer("B", "Tortue radiée")
    r.fusionner(a, b)
    autre = r.creer("C", "Tortue radiée")
    r.supprimer(autre)
    return r.resoudre(a) == b and r.resoudre(autre) is None, "alias"


def essai_menage(racine):
    d = racine / "p"
    d.mkdir()
    for nom in ("2020-01-01_10-00-00.mp4", "2020-01-01_10-00-00_1_photo.jpg", "2099-01-01_10-00-00.mp4"):
        (d / nom).write_bytes(b"x" * 100)
    n = m.nettoyer(d, jours=60, max_go=0)
    return n == 1 and not (d / "2020-01-01_10-00-00_1_photo.jpg").exists() and (d / "2099-01-01_10-00-00.mp4").exists(), f"{n}"


def _piste_visible(etats):
    """Numéro de la première piste montrée sur la vidéo (clé « pistes » de l'état)."""
    return next((p[0] for e in reversed(etats) for p in e.get("pistes", [])), None)


def essai_nommer_sur_video(racine):
    """Clic sur la tortue de la vidéo, « Zoé » : la visite est notée Zoé, corrigée à la main,
    et ses vues rejoignent la galerie de Zoé."""
    cam = Camera()
    etats = []
    s, r, d, msgs = monter(cam, racine / "n1", sur_image=lambda _i, e: etats.append(e))
    zoe = r.creer("Zoé", "Tortue radiée")
    t, res = lancer(s)
    attendre(lambda: cam.lues > 15)
    d.boites = [BOITE]
    attendre(lambda: _piste_visible(etats) is not None)
    nommee = s.nommer_piste(_piste_visible(etats), zoe)
    etiquette = next((p[2] for p in etats[-1].get("pistes", [])), "")
    time.sleep(1.0)
    etiquette = next((p[2] for p in etats[-1].get("pistes", [])), etiquette)
    d.boites = []
    attendre(lambda: m.lire_journal(s.dossier))
    s.arreter()
    t.join(15)
    lignes = m.lire_journal(s.dossier)
    galerie = len(list((r.dossier / zoe).glob("*.jpg")))
    positions = m.lire_positions(s.dossier).get(lignes[0]["id_visite"], []) if lignes else []
    ok = nommee and etiquette == "Zoé" and len(lignes) == 1 and lignes[0]["individu"] == "Zoé" \
        and lignes[0]["corrige"] == "1" and lignes[0]["id_individu"] == zoe and galerie >= 1 and len(positions) >= 2
    return ok, (f"nommée {nommee}, étiquette {etiquette!r}, lignes {[(l['individu'], l['corrige']) for l in lignes]}, "
                f"galerie {galerie}, positions {len(positions)}")


def essai_pas_une_tortue_sur_video(racine):
    """Clic sur un objet de la vidéo, « Pas une tortue » : aucune visite, son cadre disparaît
    et ses vues vont aux rejets. Une tortue partie ne peut plus être nommée."""
    cam = Camera()
    etats = []
    s, r, d, msgs = monter(cam, racine / "n2", sur_image=lambda _i, e: etats.append(e))
    t, res = lancer(s)
    attendre(lambda: cam.lues > 15)
    d.boites = [BOITE]
    attendre(lambda: _piste_visible(etats) is not None)
    numero = _piste_visible(etats)
    s.nommer_piste(numero, m.PAS_UNE_TORTUE)
    time.sleep(0.5)
    cache = not any(p[0] == numero for p in etats[-1].get("pistes", []))
    d.boites = []
    attendre(lambda: not s.pistes, 5)
    time.sleep(0.5)
    partie = s.nommer_piste(numero, m.PAS_UNE_TORTUE)
    s.arreter()
    t.join(15)
    lignes = m.lire_journal(s.dossier)
    rejets = r.nombre_rejets()
    return cache and not lignes and rejets >= 1 and partie is False,         f"cadre caché {cache}, lignes {len(lignes)}, rejets {rejets}, piste partie {partie}"


def essai_masque():
    return sources.masquer("rtsp://admin:secret@192.168.1.5:554/H.264") == "rtsp://admin:•••@192.168.1.5:554/H.264", ""


def main():
    ouvrir = m.ouvrir_source
    racine = Path(tempfile.mkdtemp(prefix="broutille_direct_"))
    ok = True
    essais = [essai_correction_concurrente, essai_journal_bloque, essai_objet_fixe, essai_fps_faux,
              essai_fin_de_visite_sans_trou, essai_photo_retiree, essai_reconnexion, essai_source_figee,
              essai_source_absente, essai_journal_abime, essai_galerie_abimee, essai_prefixe_visite,
              essai_galerie_pleine, essai_fusion_en_cours, essai_menage, essai_nommer_sur_video,
              essai_pas_une_tortue_sur_video]
    for essai in essais:
        m.ouvrir_source = ouvrir
        reussi, detail = essai(racine)
        print(("OK   " if reussi else "RATÉ ") + essai.__name__.removeprefix("essai_"), "—", detail, flush=True)
        ok &= bool(reussi)
    reussi, _d = essai_masque()
    print(("OK   " if reussi else "RATÉ ") + "masque du mot de passe")
    ok &= reussi
    shutil.rmtree(racine, ignore_errors=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
