"""
Broutille — moteur : présence des tortues, enregistrement, espèce, individu, journal, ménage.

Utilisé par l'application graphique (broutille_app.py) et par la ligne de commande.

Source vidéo : webcam, fenêtre ouverte, flux Internet ou fichier vidéo (voir sources.py).

Différences avec une mangeoire à oiseaux : une tortue peut rester des heures sans bouger.
La présence ne repose donc pas sur le mouvement, qui ne sert qu'à réveiller la détection ;
tant qu'une tortue est suivie, le détecteur la revoit à intervalle régulier. Plusieurs tortues
peuvent manger ensemble : chacune a sa piste, et une ligne dans le journal.

Pour chaque tortue :
  1. elle est suivie d'une analyse à l'autre (recouvrement des boîtes),
  2. BioCLIP confirme que c'est une tortue et propose l'espèce,
  3. elle est isolée de son décor et comparée à la galerie de chaque individu,
  4. à son départ, la tortue est nommée si plusieurs images sont sûres. Sinon la visite reste
     « Inconnue » avec une proposition, à confirmer dans l'application. Ainsi une tortue vue sous
     un angle nouveau ne crée pas de fausse fiche, et chaque confirmation enrichit sa galerie.
     Reconnue une fois, une tortue ajoute à sa galerie ses autres vues de la même visite.
"""

import argparse
import csv
import json
import queue
import shutil
import threading
import time
import unicodedata
import zipfile
from collections import defaultdict, deque
from datetime import date, datetime, timedelta
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

import vision
from sources import est_fichier, masquer, ouvrir_source, source_depuis_texte

COLONNES = ["id_visite", "date", "heure", "duree_s", "individu", "espece", "confiance", "video", "photo", "source",
            "corrige", "id_individu", "proposition", "id_proposition"]
INCONNUE = "Inconnue"
PAS_UNE_TORTUE = "Pas une tortue"
MAX_EXEMPLES = 60               # photos gardées par individu
EXEMPLE_DIFFERENT = 0.92        # une nouvelle vue n'entre en galerie que si elle apporte du neuf
ALBUM = "album"                 # individus/<id>/album : photos souvenirs, jamais lues par la reconnaissance
CHAMPS_IDENTITE = ("sexe", "naissance", "arrivee", "origine", "signes", "notes", "profil")


def sans_accents(texte):
    return unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()


def ajuster(image, taille):
    """Met l'image à la taille (l, h) sans la déformer : mise à l'échelle, puis bandes noires.
    Une tortue étirée serait moins bien reconnue."""
    l, h = taille
    e = min(l / image.shape[1], h / image.shape[0])
    nl, nh = max(1, round(image.shape[1] * e)), max(1, round(image.shape[0] * e))
    sortie = np.zeros((h, l, 3), np.uint8)
    x, y = (l - nl) // 2, (h - nh) // 2
    sortie[y:y + nh, x:x + nl] = cv2.resize(image, (nl, nh))
    return sortie


def nom_fichier(texte):
    return "".join(c if c.isalnum() else "_" for c in sans_accents(texte)).strip("_")


def _date_photo(img, chemin):
    """Date de prise de vue (EXIF DateTimeOriginal), sinon date du fichier."""
    try:
        brut = img.getexif().get_ifd(0x8769).get(0x9003) or img.getexif().get(0x0132)
        if brut:
            return datetime.strptime(str(brut).strip("\x00 ")[:19], "%Y:%m:%d %H:%M:%S")
    except (ValueError, KeyError, AttributeError, OSError):
        pass
    return datetime.fromtimestamp(Path(chemin).stat().st_mtime)


def lire_image(chemin):
    """Image BGR, ou None si le fichier est absent, vide ou abîmé."""
    try:
        return cv2.imdecode(np.fromfile(str(chemin), np.uint8), cv2.IMREAD_COLOR)
    except (OSError, ValueError, cv2.error):
        return None


def ecrire_image(chemin, image):
    """Écriture en deux temps : une coupure ne laisse jamais de .jpg à moitié écrit."""
    ok, tampon = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if ok:
        tmp = Path(str(chemin) + ".part")
        tmp.write_bytes(tampon.tobytes())
        tmp.replace(chemin)
    return ok


# ------------------------------------------------------------------
#  Journal et ménage
# ------------------------------------------------------------------
class JournalOccupe(Exception):
    """visites.csv est bloqué, en général ouvert dans Excel."""


VERROU_JOURNAL = threading.RLock()      # tout le cycle lecture-modification-écriture passe par lui


def _insister(action, essais=6):
    """Windows refuse un fichier ouvert ailleurs, parfois juste un instant (antivirus, Excel)."""
    for i in range(essais):
        try:
            return action()
        except PermissionError:
            if i == essais - 1:
                raise JournalOccupe("visites.csv est ouvert dans un autre programme : fermez-le, puis réessayez") from None
            time.sleep(0.25)


def _attente(dossier):
    return Path(dossier) / "visites_en_attente.jsonl"


def _lire_attente(dossier):
    chemin = _attente(dossier)
    if not chemin.exists():
        return []
    lignes = []
    for l in chemin.read_text(encoding="utf-8").splitlines():
        try:
            lignes.append(json.loads(l))
        except ValueError:      # coupure pendant l'écriture : seule cette ligne est perdue
            pass
    return lignes


def _lire_csv(chemin):
    """Lignes de visites.csv. Tolère un enregistrement par Excel (autre encodage) et une ligne coupée
    par une panne : un journal abîmé ne doit jamais empêcher l'application de s'ouvrir."""
    if not chemin.exists():
        return []
    brut = _insister(chemin.read_bytes)
    textes = []
    for ligne in brut.removeprefix(b"\xef\xbb\xbf").splitlines():
        try:
            textes.append(ligne.decode("utf-8"))
        except UnicodeDecodeError:
            textes.append(ligne.decode("cp1252", "replace"))
    lignes = []
    for l in csv.DictReader(textes, delimiter=";"):
        if None in l or None in l.values() or not l.get("date") or not l.get("id_visite"):
            continue
        lignes.append(l)
    return lignes


def assurer_journal(chemin):
    with VERROU_JOURNAL:
        if not chemin.exists():
            ecrire_journal(chemin, [])


def ecrire_journal(chemin, lignes):
    with VERROU_JOURNAL:
        tmp = chemin.with_suffix(".tmp")
        with open(tmp, "w", newline="", encoding="utf-8-sig") as f:     # BOM : accents justes dans Excel
            w = csv.DictWriter(f, fieldnames=COLONNES, delimiter=";", extrasaction="ignore")
            w.writeheader()
            for l in lignes:
                w.writerow({c: (l.get(c) or "") for c in COLONNES})
        _insister(lambda: tmp.replace(chemin))


def lire_journal(dossier):
    """Toutes les visites, y compris celles en attente d'écriture."""
    with VERROU_JOURNAL:
        return _lire_csv(Path(dossier) / "visites.csv") + _lire_attente(dossier)


def modifier_journal(dossier, modification):
    """Applique modification(lignes) au journal, sans laisser une visite s'intercaler entre la
    lecture et l'écriture. Renvoie son résultat. JournalOccupe si le fichier est bloqué."""
    with VERROU_JOURNAL:
        lignes = lire_journal(dossier)
        resultat = modification(lignes)
        ecrire_journal(Path(dossier) / "visites.csv", lignes)
        _attente(dossier).unlink(missing_ok=True)
        return resultat


def ajouter_ligne(dossier, ligne):
    """Ajoute une visite ; si le journal est bloqué, elle attend dans visites_en_attente.jsonl et
    sera écrite à la prochaine occasion. Une visite n'est jamais perdue pour un Excel resté ouvert.
    Renvoie False si elle a dû attendre."""
    dossier = Path(dossier)
    chemin = dossier / "visites.csv"
    with VERROU_JOURNAL:
        en_attente = _lire_attente(dossier)
        try:
            assurer_journal(chemin)
            with open(chemin, "a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=COLONNES, delimiter=";", extrasaction="ignore")
                for l in en_attente + [ligne]:
                    w.writerow({c: (l.get(c) or "") for c in COLONNES})
            _attente(dossier).unlink(missing_ok=True)
            return True
        except (PermissionError, JournalOccupe):
            with open(_attente(dossier), "a", encoding="utf-8") as f:
                f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
            return False


def secondes(ligne):
    try:
        return float(ligne.get("duree_s") or 0)
    except ValueError:
        return 0.0


POSITIONS = "positions"
ENTETE_POSITIONS = "id_visite;t_s;x;y;l;h;image_l;image_h\n"


def ecrire_positions(dossier, id_visite, piste):
    """Ajoute le trajet d'une visite à positions/AAAA-MM.csv : une ligne par analyse, le temps en
    secondes depuis l'arrivée, le cadre en pixels. Relié au journal par id_visite : une visite
    corrigée change de tortue sans rien réécrire ici."""
    if not piste.trajet or not piste.taille_image:
        return
    d = Path(dossier) / POSITIONS
    d.mkdir(exist_ok=True)
    chemin = d / f"{piste.arrivee:%Y-%m}.csv"
    nouveau = not chemin.exists()
    il, ih = piste.taille_image
    with open(chemin, "a", encoding="utf-8", newline="") as f:
        if nouveau:
            f.write(ENTETE_POSITIONS)
        for instant, x, y, l, h in piste.trajet:
            f.write(f"{id_visite};{instant - piste.debut:.1f};{x};{y};{l};{h};{il};{ih}\n")


def lire_positions(dossier):
    """{id_visite: [(t_s, x, y, l, h, image_l, image_h)]}, tous mois confondus."""
    res = defaultdict(list)
    d = Path(dossier) / POSITIONS
    for chemin in sorted(d.glob("*.csv")) if d.exists() else []:
        try:
            lignes = chemin.read_text(encoding="utf-8").splitlines()[1:]
        except OSError:
            continue
        for ligne in lignes:
            champs = ligne.split(";")
            try:
                point = (float(champs[1]), *(int(v) for v in champs[2:8]))
            except (IndexError, ValueError):
                continue                    # ligne abîmée (coupure de courant) : on l'ignore
            if len(point) == 7:
                res[champs[0]].append(point)
    return dict(res)


def nettoyer(dossier, jours=60, max_go=20.0, garder=()):
    """Efface les clips et photos de visite plus vieux que `jours`, puis les plus anciens tant que le
    dossier dépasse `max_go`. 0 = pas de limite. Le journal et les galeries sont conservés, ainsi que
    les fichiers de `garder` (clip en cours). Renvoie le nombre de clips effacés."""
    dossier = Path(dossier)
    fichiers = sorted((p for p in dossier.glob("*.*") if p.suffix in (".mp4", ".jpg") and p.name not in garder),
                      key=lambda p: p.name)
    supprimes = 0

    def effacer(p):
        nonlocal supprimes
        try:
            p.unlink()
            supprimes += p.suffix == ".mp4"
        except OSError:
            pass

    if jours:
        limite = (datetime.now() - timedelta(days=jours)).strftime("%Y-%m-%d")
        for p in [f for f in fichiers if f.name[:10] < limite]:
            effacer(p)
        fichiers = [f for f in fichiers if f.exists()]
    if max_go:
        taille = sum(p.stat().st_size for p in fichiers)
        while fichiers and taille > max_go * 1024 ** 3:
            p = fichiers.pop(0)
            taille -= p.stat().st_size
            effacer(p)
    return supprimes


# ------------------------------------------------------------------
#  Registre des tortues : qui est qui
# ------------------------------------------------------------------
class RegistreIllisible(Exception):
    """registre.json et sa sauvegarde sont abîmés : mieux vaut s'arrêter que repartir de zéro."""


class Registre:
    """Tortues connues : individus/registre.json + une galerie de vues par tortue
    (individus/<id>/*.jpg). Les vecteurs sont recalculés seulement pour les nouvelles photos."""

    def __init__(self, dossier, descripteur=None):
        self.dossier = Path(dossier) / "individus"
        self.descripteur = descripteur or vision.Descripteur()
        self.fiches = {}
        self.vecteurs = {}      # id -> (n, d) : un vecteur par photo, dans le sens de la photo
        self.fichiers = {}      # id -> [noms des photos], dans l'ordre des vecteurs
        self.points = {}        # chemin de photo -> points SIFT
        self.rejets = None      # vecteurs des « Pas une tortue »
        self.alias = {}         # fiche fusionnée -> fiche qui l'a absorbée, pour les visites en cours
        self._verrou = threading.RLock()
        self.charger()

    @property
    def chemin(self):
        return self.dossier / "registre.json"

    def charger(self):
        with self._verrou:
            if not self.chemin.exists() and not self.chemin.with_suffix(".bak").exists():
                self.fiches = {}
                return
            for chemin in (self.chemin, self.chemin.with_suffix(".bak")):
                try:
                    self.fiches = json.loads(chemin.read_text(encoding="utf-8"))
                    return
                except (OSError, ValueError):
                    pass
            raise RegistreIllisible(f"Fiches des tortues illisibles : {self.chemin}")

    def _ecrire(self):
        self.dossier.mkdir(parents=True, exist_ok=True)
        if self.chemin.exists():
            shutil.copy2(self.chemin, self.chemin.with_suffix(".bak"))
        tmp = self.chemin.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.fiches, indent=1, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.chemin)

    def copie_fiches(self):
        """Fiches à parcourir depuis un autre fil."""
        with self._verrou:
            return {c: dict(f) for c, f in self.fiches.items()}

    def resoudre(self, cle):
        """Fiche actuelle d'un identifiant, en suivant les fusions ; None si elle n'existe plus."""
        with self._verrou:
            while cle in self.alias:
                cle = self.alias[cle]
            return cle if cle in self.fiches else None

    def preparer(self):
        """Lit les galeries ; à appeler une fois les modèles disponibles (peut prendre du temps)."""
        with self._verrou:
            for cle in list(self.fiches):
                self._lire_galerie(cle)
            self._lire_rejets()

    def _vecteurs_dossier(self, d):
        cache = d / "vecteurs.npz"
        try:
            anciens = dict(np.load(cache)) if cache.exists() else {}
        except (OSError, ValueError, EOFError, KeyError, zipfile.BadZipFile):
            anciens = {}        # cache abîmé : il se recalcule depuis les photos
        gardes = {}
        for p in sorted(d.glob("*.jpg")):
            k = f"{p.name}|{p.stat().st_size}"
            v = anciens.get(k)
            if v is None:
                image = lire_image(p)
                if image is None:
                    continue
                v = self.descripteur.decrire(image)[0]
            gardes[k] = v
        if set(gardes) != set(anciens) and d.exists():
            tmp = d / "vecteurs.tmp.npz"
            np.savez(tmp, **gardes)
            tmp.replace(cache)
        noms = [k.split("|")[0] for k in gardes]
        return noms, (np.stack(list(gardes.values())) if gardes else None)

    def _lire_galerie(self, cle):
        with self._verrou:
            noms, v = self._vecteurs_dossier(self.dossier / cle)
            self.fichiers[cle], self.vecteurs[cle] = noms, v

    def _lire_rejets(self):
        d = self.dossier / "pas_une_tortue"
        self.rejets = self._vecteurs_dossier(d)[1] if d.exists() else None

    # --- gestion
    def creer(self, nom, espece, provisoire=False):
        with self._verrou:
            cle = f"t{int(time.time() * 1000):x}"
            while cle in self.fiches:
                cle += "x"
            self.fiches[cle] = {"nom": nom, "espece": espece, "provisoire": provisoire,
                                "creee": datetime.now().strftime("%Y-%m-%d")}
            (self.dossier / cle).mkdir(parents=True, exist_ok=True)
            self._ecrire()
            self.fichiers[cle], self.vecteurs[cle] = [], None
            return cle

    def nom_provisoire(self, espece):
        court = espece.replace("Tortue ", "").replace("d'", "").capitalize()
        n = 1 + sum(1 for f in self.fiches.values() if f["nom"].startswith(f"{court} n°"))
        while any(f["nom"] == f"{court} n°{n}" for f in self.fiches.values()):
            n += 1
        return f"{court} n°{n}"

    def modifier(self, cle, **champs):
        with self._verrou:
            self.fiches[cle].update(champs)
            self._ecrire()

    def ajouter_exemple(self, cle, tortue, nom=None):
        """Ajoute une tortue isolée à la galerie ; renvoie le nom du fichier. Galerie pleine : la plus
        ancienne vue automatique laisse sa place, car une tortue grandit ; les photos importées restent."""
        with self._verrou:
            if cle not in self.fiches:
                return None
            d = self.dossier / cle
            d.mkdir(parents=True, exist_ok=True)
            photos = sorted(d.glob("*.jpg"))
            if len(photos) >= MAX_EXEMPLES:
                anciennes = [p for p in photos if not p.name.startswith("import_")]
                if not anciennes:
                    return None
                anciennes[0].unlink(missing_ok=True)
                self.points.pop(str(anciennes[0]), None)
            nom = nom or f"{datetime.now():%Y-%m-%d_%H-%M-%S}_{len(photos):03d}.jpg"
            ecrire_image(d / nom, tortue)
            self._lire_galerie(cle)
            return nom

    def retirer_exemples(self, cle, prefixe):
        """Retire les photos d'une visite : [(nom, contenu)]."""
        with self._verrou:
            retires = list((self.dossier / cle).glob(prefixe + "_*.jpg"))
            contenus = [(p.name, p.read_bytes()) for p in retires]
            for p in retires:
                p.unlink(missing_ok=True)
                self.points.pop(str(p), None)
            if retires:
                self._lire_galerie(cle)
            return contenus

    def retirer_vue(self, cle, nom):
        """Retire une vue de la galerie (mauvaise image apprise) ; la reconnaissance l'oublie aussitôt."""
        with self._verrou:
            chemin = self.dossier / cle / Path(nom).name
            chemin.unlink(missing_ok=True)
            self.points.pop(str(chemin), None)
            if self.fiches.get(cle, {}).get("profil") == chemin.name:
                self.fiches[cle].pop("profil")
                self._ecrire()
            if cle in self.fiches:
                self._lire_galerie(cle)

    def deposer_exemples(self, cle, contenus):
        with self._verrou:
            d = self.dossier / cle
            d.mkdir(parents=True, exist_ok=True)
            for nom, octets in contenus:
                (d / nom).write_bytes(octets)
            self._lire_galerie(cle)

    def rejeter(self, contenus):
        """Ces images ne sont pas des tortues : la prochaine fois, ne pas les noter."""
        d = self.dossier / "pas_une_tortue"
        d.mkdir(parents=True, exist_ok=True)
        with self._verrou:
            for nom, octets in contenus:
                (d / nom).write_bytes(octets)
            self._lire_rejets()

    def nombre_rejets(self):
        d = self.dossier / "pas_une_tortue"
        return len(list(d.glob("*.jpg"))) if d.exists() else 0

    def oublier_rejets(self):
        """Annule tous les « Pas une tortue »."""
        with self._verrou:
            shutil.rmtree(self.dossier / "pas_une_tortue", ignore_errors=True)
            self.rejets = None

    def fusionner(self, source, cible):
        """La tortue `source` était en fait `cible` : galerie réunie, `source` disparaît."""
        with self._verrou:
            ds, dc = self.dossier / source, self.dossier / cible
            dc.mkdir(parents=True, exist_ok=True)
            for p in ds.glob("*.jpg"):
                p.replace(dc / p.name)
            if (ds / ALBUM).is_dir():           # l'album suit : rmtree l'effacerait
                (dc / ALBUM).mkdir(exist_ok=True)
                for p in (ds / ALBUM).iterdir():
                    if p.is_file():
                        dest, n = dc / ALBUM / p.name, 1
                        while dest.exists():        # même nom : renommer, jamais perdre une photo
                            n += 1
                            dest = dc / ALBUM / f"{p.stem}_f{n}{p.suffix}"
                        p.replace(dest)
            shutil.rmtree(ds, ignore_errors=True)
            fs, fc = self.fiches[source], self.fiches[cible]
            fc["provisoire"] = False if not fs["provisoire"] else fc["provisoire"]
            for liste in ("pesees", "carnet"):
                tout = fc.get(liste, []) + fs.get(liste, [])
                if tout:
                    fc[liste] = sorted(tout, key=lambda p: p["date"])
            for champ in CHAMPS_IDENTITE:       # la fiche gardée complète ce qui lui manque
                if fs.get(champ) and not fc.get(champ):
                    fc[champ] = fs[champ]
            del self.fiches[source]
            self.alias[source] = cible
            self.vecteurs.pop(source, None)
            self.fichiers.pop(source, None)
            self._ecrire()
            self._lire_galerie(cible)

    # --- pesées : [{"date": "AAAA-MM-JJ", "g": 1234.0, "note": "..."}] par ordre de date
    def ajouter_pesee(self, cle, jour, grammes, note=""):
        """Ajoute une pesée ; une seconde pesée le même jour remplace la première."""
        grammes = float(grammes)
        if not 1 <= grammes <= 200000:
            raise ValueError("poids hors limites (1 g à 200 kg)")
        jour = date.fromisoformat(str(jour)).isoformat()
        with self._verrou:
            pesees = [p for p in self.fiches[cle].get("pesees", []) if p["date"] != jour]
            pesees.append({"date": jour, "g": round(grammes, 1), "note": note.strip()})
            self.fiches[cle]["pesees"] = sorted(pesees, key=lambda p: p["date"])
            self._ecrire()

    def retirer_pesee(self, cle, jour):
        with self._verrou:
            self.fiches[cle]["pesees"] = [p for p in self.fiches[cle].get("pesees", []) if p["date"] != jour]
            self._ecrire()

    def pesees(self, cle):
        with self._verrou:
            return [dict(p) for p in self.fiches.get(cle, {}).get("pesees", [])]

    # --- carnet : [{"date", "type", "texte"}] par ordre de date (soins, vétérinaire, ponte…)
    def ajouter_note(self, cle, jour, genre, texte):
        texte = texte.strip()
        if not texte:
            raise ValueError("note vide")
        jour = date.fromisoformat(str(jour)).isoformat()
        with self._verrou:
            carnet = self.fiches[cle].get("carnet", []) + [{"date": jour, "type": genre, "texte": texte}]
            self.fiches[cle]["carnet"] = sorted(carnet, key=lambda n: n["date"])
            self._ecrire()

    def retirer_note(self, cle, rang):
        with self._verrou:
            carnet = list(self.fiches[cle].get("carnet", []))
            if 0 <= rang < len(carnet):
                del carnet[rang]
                self.fiches[cle]["carnet"] = carnet
                self._ecrire()

    def carnet(self, cle):
        with self._verrou:
            return [dict(n) for n in self.fiches.get(cle, {}).get("carnet", [])]

    # --- album : photos souvenirs (individus/<id>/album/), hors reconnaissance
    def album(self, cle):
        d = self.dossier / cle / ALBUM
        return sorted((p for p in d.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png")),
                      reverse=True) if d.is_dir() else []

    def ajouter_album(self, cle, chemins):
        """Copie les photos dans l'album, réduites à 2000 px ; renvoie les noms écrits.
        Le nom commence par la date de prise de vue (EXIF) ou du fichier : l'album se trie seul."""
        d = self.dossier / cle / ALBUM
        d.mkdir(parents=True, exist_ok=True)
        ecrits = []
        for chemin in chemins:
            chemin = Path(chemin)
            try:
                with Image.open(chemin) as img:
                    quand = _date_photo(img, chemin)
                    img = ImageOps.exif_transpose(img).convert("RGB")
                    img.thumbnail((2000, 2000))
                    base = f"{quand:%Y-%m-%d_%H-%M-%S}_{nom_fichier(chemin.stem)[:30]}"
                    cible, n = d / f"{base}.jpg", 1
                    while cible.exists():
                        n += 1
                        cible = d / f"{base}_{n}.jpg"
                    img.save(cible, quality=90)
                    ecrits.append(cible.name)
            except (OSError, ValueError):
                continue
        return ecrits

    def retirer_album(self, cle, nom):
        with self._verrou:
            (self.dossier / cle / ALBUM / nom).unlink(missing_ok=True)
            if self.fiches.get(cle, {}).get("profil") == f"{ALBUM}/{nom}":
                self.fiches[cle].pop("profil")
                self._ecrire()

    def photo_profil(self, cle):
        """Photo choisie, sinon la plus récente de l'album, sinon la première vue de la galerie."""
        d = self.dossier / cle
        choisie = self.fiches.get(cle, {}).get("profil")
        if choisie and (d / choisie).is_file():
            return d / choisie
        album = self.album(cle)
        if album:
            return album[0]
        vues = sorted(d.glob("*.jpg")) if d.is_dir() else []
        return vues[0] if vues else None

    def supprimer(self, cle):
        with self._verrou:
            shutil.rmtree(self.dossier / cle, ignore_errors=True)
            self.fiches.pop(cle, None)
            self.vecteurs.pop(cle, None)
            self.fichiers.pop(cle, None)
            self._ecrire()

    # --- reconnaissance
    def est_rejet(self, vecteurs, seuil=0.85):
        return self.rejets is not None and float((vecteurs @ self.rejets.T).max()) >= seuil

    def similarites(self, vecteurs, sift=None, candidats=3):
        """[(id, score)] du plus au moins probable. Score : photo de la galerie la plus ressemblante
        (cosinus) : une tortue ne ressemble qu'à ses vues prises du même côté. Le dessin des écailles
        (SIFT) départage les meilleures candidates."""
        with self._verrou:
            scores = []
            for cle, g in self.vecteurs.items():
                if g is None or cle not in self.fiches:
                    continue
                sims = (vecteurs @ g.T).max(axis=0)
                scores.append((float(sims.max()), cle, sims))
            scores.sort(key=lambda s: -s[0])
            sortie, absentes = [], set()
            for rang, (s, cle, sims) in enumerate(scores):
                if sift is not None and rang < candidats:
                    s += BONUS_SIFT * min(self._sift_max(cle, sims, sift, absentes), PLAFOND_SIFT)
                sortie.append((cle, s))
            for cle in absentes:            # photo retirée à la main de la galerie
                self._lire_galerie(cle)
            return sorted(sortie, key=lambda x: -x[1])

    def _sift_max(self, cle, sims, sift, absentes):
        meilleur = 0
        for i in np.argsort(-sims)[:4]:
            p = self.dossier / cle / self.fichiers[cle][i]
            pts = self.points.get(str(p))
            if pts is None:
                image = lire_image(p)
                if image is None:
                    absentes.add(cle)
                    continue
                pts = self.points[str(p)] = vision.points_sift(image)
            meilleur = max(meilleur, vision.appariement_sift(sift, pts))
        return meilleur


# réglés sur le banc d'essai (tests/evaluer_galerie_pleine.py) : contre des galeries de 60 photos, le pire
# cas, une tortue inconnue passe le seuil de 0,60 sur 13 % des images de radiata, celui de 0,70 sur 5 %
BONUS_SIFT = 0.01               # score ajouté par point d'écaille cohérent
PLAFOND_SIFT = 40
SEUIL_INDIVIDU = 0.70           # score minimal d'une image pour compter comme une reconnaissance sûre
MARGE_INDIVIDU = 0.03           # écart minimal avec la deuxième tortue la plus proche
SEUIL_PROPOSITION = 0.38        # en dessous, une tortue ne ressemble pas assez pour être proposée
IMAGES_SURES = 2                # images sûres qu'il faut dans une visite pour nommer la tortue
ECART_IMAGES_SURES = 8.0        # secondes entre elles : deux images du même instant ne valent qu'une preuve
SUPPLEMENT_FICHE_UNIQUE = 0.15  # une seule fiche : sans deuxième candidate, la marge ne protège de rien
GALERIE_MIN = 10                # photos de galerie qu'il faut pour aider le filtre « tortue ou pas »
GALERIE_BAS, GALERIE_HAUT = 0.64, 0.74   # ressemblance (5 meilleures) : objets ≤ 0,63, tortues ≥ 0,75
FIGEE_S = 60.0                  # direct : sans aucun changement pendant 1 min, l'image est figée
SEUIL_FIGEE = 4                 # écart de gris, sur une image de 96 px de large, compté comme un changement


# ------------------------------------------------------------------
#  Suivi d'une tortue pendant sa visite
# ------------------------------------------------------------------
def nettete(image):
    return float(cv2.Laplacian(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())


class Piste:
    """Une tortue suivie d'une analyse à l'autre."""
    numero = 0

    def __init__(self, boite, instant):
        Piste.numero += 1
        self.numero = Piste.numero
        self.boite, self.debut, self.vue = boite, instant, instant
        self.arrivee = datetime.now()
        self.analyses = 0
        self.p_tortue = []
        self.especes = defaultdict(float)
        self.individus = defaultdict(list)      # images sûres par tortue : [(instant, score)]
        self.proposition = defaultdict(float)   # tortue arrivée en tête, même sans certitude
        self.exemples = []          # voir ajouter_exemple
        self.etiquette = ""
        self.rejets = 0
        self.clip = None            # nom du clip qui la montre ; "" si aucun n'a pu s'ouvrir
        self.nommee = None          # fiche choisie par l'utilisateur sur la vidéo, ou PAS_UNE_TORTUE
        self.trajet = []            # [(instant, x, y, l, h)] à chaque analyse, en pixels
        self.taille_image = None    # (largeur, hauteur) de l'image analysée

    def ajouter_exemple(self, q, tortue, vecteurs, image, cle=None, score=0.0, isolee=True):
        """Garde les vues les plus nettes : (netteté, tortue isolée, vecteurs, image entière,
        tortue arrivée en tête sur cette vue, son score, pas de voisine tout près)."""
        self.exemples.append((q, tortue, vecteurs, image, cle, score, isolee))
        self.exemples.sort(key=lambda e: -e[0])
        del self.exemples[6:]

    def espece(self):
        return max(self.especes, key=self.especes.get) if self.especes else INCONNUE

    def confirmee(self):
        """Assez vue pour y croire : une pierre ou un « Pas une tortue » n'ouvre aucun clip.
        Nommée par l'utilisateur, elle est confirmée d'office (ou écartée si « Pas une tortue »)."""
        if self.nommee is not None:
            return self.nommee != PAS_UNE_TORTUE
        return self.analyses >= 2 and float(np.mean(self.p_tortue)) >= 0.5 and self.rejets <= self.analyses / 2

    def verdict(self):
        """(id, score) si la visite nomme une tortue avec certitude : assez d'images sûres, espacées,
        et presque toutes pour la même tortue. Sinon (None, 0)."""
        if not self.individus:
            return None, 0.0
        meilleure = max(self.individus, key=lambda c: len(self.individus[c]))
        sures = self.individus[meilleure]
        if len(sures) < IMAGES_SURES or len(sures) < 0.75 * sum(len(v) for v in self.individus.values()):
            return None, 0.0
        if sures[-1][0] - sures[0][0] < ECART_IMAGES_SURES:
            return None, 0.0
        return meilleure, float(np.mean([s for _t, s in sures]))

    def probable(self):
        return max(self.proposition, key=self.proposition.get) if self.proposition else None


def ressemblance_galerie(classeur, galerie, image, boite):
    """Probabilité « tortue » d'après la ressemblance aux photos de galerie : moyenne des 5
    photos les plus proches, tortue isolée sur fond gris comme dans la galerie. 0 sous
    GALERIE_BAS, 1 au-dessus de GALERIE_HAUT."""
    tortue = vision.isoler_tortue(image, boite)
    if tortue is None:
        return 0.0
    s = galerie @ classeur.vecteur(tortue)
    proche = float(np.sort(s)[-5:].mean())
    return float(np.clip((proche - GALERIE_BAS) / (GALERIE_HAUT - GALERIE_BAS), 0.0, 1.0))


def ecart(a, b):
    """Distance entre deux boîtes, en largeurs de boîte."""
    return np.hypot(a[0] + a[2] / 2 - b[0] - b[2] / 2, a[1] + a[3] / 2 - b[1] - b[3] / 2) / max(a[2], a[3], 1)


def associer(pistes, detections):
    """Détections -> pistes par proximité ; renvoie (paires, détections restantes).
    Une tortue bouge peu entre deux analyses : pas besoin de modèle de mouvement."""
    paires, libres = [], list(range(len(detections)))
    for piste in sorted(pistes, key=lambda p: -p.vue):
        if not libres:
            break
        i = min(libres, key=lambda k: ecart(piste.boite, detections[k][1]))
        if ecart(piste.boite, detections[i][1]) < 0.8:
            paires.append((piste, i))
            libres.remove(i)
    return paires, libres


# ------------------------------------------------------------------
#  Lecture de la source en direct
# ------------------------------------------------------------------
class LecteurCamera(threading.Thread):
    """Lit la source dans son propre fil : une caméra débranchée ou un flux Internet qui se fige
    bloquent read() sans limite, et la surveillance doit rester libre de réagir ou de s'arrêter.
    Mesure aussi les vraies images par seconde : ce qu'annonce une caméra est souvent faux."""

    def __init__(self, source, sur_message):
        super().__init__(daemon=True)
        self.source, self.sur_message = source, sur_message
        self.file = queue.Queue(maxsize=60)
        self.pret, self.fin = threading.Event(), threading.Event()
        self.echec = False
        self.temps = deque(maxlen=90)
        self.fps_annonce = 15.0
        self.derniere = time.time()
        self.en_lecture = False

    def fps(self):
        if len(self.temps) >= 10 and self.temps[-1] > self.temps[0]:
            return float(np.clip((len(self.temps) - 1) / (self.temps[-1] - self.temps[0]), 1, 60))
        return self.fps_annonce

    def _deposer(self, image):
        maintenant = time.time()
        self.derniere = maintenant
        self.temps.append(maintenant)
        try:
            self.file.put_nowait((image, maintenant))
        except queue.Full:              # la surveillance a pris du retard : on perd l'image la plus vieille
            try:
                self.file.get_nowait()
            except queue.Empty:
                pass
            self.file.put_nowait((image, maintenant))

    def run(self):
        premiere = True
        while not self.fin.is_set():
            camera, image = ouvrir_source(self.source)
            if camera is None:
                if premiere:
                    self.echec = True
                    self.pret.set()
                    return
                self.fin.wait(5)
                continue
            try:
                annonce = camera.get(cv2.CAP_PROP_FPS)
                self.fps_annonce = annonce if 1 < annonce < 120 else 15.0
                self._deposer(image)
                premiere = False
                self.pret.set()
                while not self.fin.is_set():
                    self.en_lecture = True
                    ok, image = camera.read()
                    self.en_lecture = False
                    if not ok or image is None:
                        break
                    self._deposer(image)
            finally:
                self.en_lecture = False
                camera.release()
            if not self.fin.is_set():
                self.sur_message("Source interrompue, nouvelle tentative…")
                self.fin.wait(2)


# ------------------------------------------------------------------
#  Moteur
# ------------------------------------------------------------------
class Surveillance:
    """Boucle source -> présence -> enregistrement -> espèce et individu.

    Trois fils : la boucle lit et enregistre sans jamais attendre, l'analyse travaille sur la dernière
    image, et les fins de visite (photos, galerie, journal) passent par une file à part.
    seuil, marge et reconnaissance_active peuvent être modifiés pendant l'exécution. Rappels (depuis
    ces fils) : sur_image(vue_bgr, etat), sur_visite(ligne), sur_message(texte)
    zone : (x0, y0, x1, y1) en fractions de l'image, pour ne garder qu'une partie d'une fenêtre.
    """
    SILENCE_MAX = 20            # secondes sans image avant de relancer une source figée

    def __init__(self, source, dossier, registre=None, detecteur=None, classeur=None,
                 seuil=SEUIL_INDIVIDU, marge=MARGE_INDIVIDU, surface=0.01, avant=3, apres=20, clip_max=120,
                 analyse_toutes=None, veille_toutes=None, reconnaissance=True, creer_nouvelles=False, zone=None,
                 sur_image=None, sur_visite=None, sur_message=None, temps_reel=False, menage_jours=60, menage_go=20.0,
                 sur_figee=None):
        self.source = source_depuis_texte(source)
        self.dossier = Path(dossier)
        self.registre = registre or Registre(self.dossier)
        self.detecteur = detecteur or vision.DetecteurTortues()
        self.classeur = classeur or vision.ClasseurEspeces()
        self.seuil, self.marge, self.surface = seuil, marge, surface
        self.avant, self.apres, self.clip_max = avant, apres, clip_max
        self.presence_min = 5
        # sur processeur une analyse dure plusieurs secondes : on l'espace
        gpu = vision.appareil() == "cuda"
        self.analyse_toutes = analyse_toutes or (1.0 if gpu else 5.0)
        self.veille_toutes = veille_toutes or (5.0 if gpu else 15.0)
        self.reconnaissance_active = reconnaissance
        self.creer_nouvelles = creer_nouvelles
        self.zone = zone
        self.menage_jours, self.menage_go = menage_jours, menage_go
        self.sur_image = sur_image or (lambda vue, etat: None)
        self.sur_visite = sur_visite or (lambda ligne: None)
        self.sur_message = sur_message or print
        self.sur_figee = sur_figee or (lambda figee: None)
        self.figee_s = FIGEE_S
        self._galerie_cache, self._galerie_matrice, self._galerie_vue = None, None, 0.0
        self.temps_reel = temps_reel
        self.arret = threading.Event()
        self.pistes = []
        self._verrou = threading.Lock()
        self.fichier = est_fichier(self.source)
        self.video, self.chemin_clip, self.nb_clip, self.debut_clip = None, None, 0, 0.0
        self.duree_analyse = 0.0
        self._taches = queue.Queue()

    def arreter(self):
        self.arret.set()

    def _executer_tache(self, fonction, *args):
        try:
            fonction(*args)
        except Exception as e:      # disque plein, photo illisible... la surveillance continue
            self.sur_message(f"Erreur : {type(e).__name__} : {e}")

    def _tache(self, fonction, *args):
        """Travail lent de fin de visite : hors de la boucle, qui ne doit jamais attendre.
        Un fichier vidéo est analysé d'un bloc, sans contrainte de temps : tout s'y fait dans l'ordre."""
        if self.fichier:
            self._executer_tache(fonction, *args)
        else:
            self._taches.put((fonction, args))

    def _fil_taches(self):
        while True:
            travail = self._taches.get()
            if travail is None:
                return
            self._executer_tache(travail[0], *travail[1])

    # --- clip
    def _ouvrir_clip(self, fps, taille, tampon, instant):
        base = self.dossier / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        chemin, n = base.with_suffix(".mp4"), 1
        while chemin.exists():
            n += 1
            chemin = base.with_name(f"{base.name}-{n}.mp4")
        video = cv2.VideoWriter(str(chemin), cv2.VideoWriter_fourcc(*"mp4v"), fps, taille)
        if not video.isOpened():
            self.sur_message(f"Clip impossible à créer dans {self.dossier}")
            return
        self.video, self.chemin_clip, self.nb_clip, self.debut_clip = video, chemin, 0, instant
        for _t, jpeg in tampon:
            self.video.write(cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR))
            self.nb_clip += 1
        tampon.clear()

    def _fermer_clip(self):
        if self.video is not None:
            self.video.release()
            self.video = None
            self._tache(self._nettoyer_clip, self.chemin_clip.name)

    def _nettoyer_clip(self, nom):
        """Fausse alerte : aucune visite ne cite ce clip, et aucune tortue encore là."""
        if not nom or (self.video is not None and self.chemin_clip.name == nom):
            return
        with self._verrou:
            if any(p.clip == nom for p in self.pistes):
                return
        if not any(l["video"] == nom for l in lire_journal(self.dossier)):
            (self.dossier / nom).unlink(missing_ok=True)

    # --- analyse d'une image
    def _analyser(self, image, instant):
        t0 = time.time()
        fiches = []
        galerie = self._galerie_especes()
        for score, boite in self.detecteur.detecter(image):
            p_tortue, classes = self.classeur.classer(vision.recadrer(image, boite))
            if p_tortue < 0.5 and galerie is not None:
                # de loin, une tortue floue passe pour un chien ou un chat auprès du filtre par le
                # texte ; comparée aux photos des tortues de la maison, prises par la même caméra,
                # elle se reconnaît bien mieux (mesuré : tortues 0,75 à 0,78, objets 0,63 au plus)
                p_tortue = max(p_tortue, ressemblance_galerie(self.classeur, galerie, image, boite))
            if p_tortue >= 0.3:
                fiches.append((score, boite, p_tortue, classes))
        with self._verrou:
            paires, libres = associer(self.pistes, fiches)
            for i in libres:
                piste = Piste(fiches[i][1], instant)
                self.pistes.append(piste)
                paires.append((piste, i))
        for piste, i in paires:
            _score, boite, p_tortue, classes = fiches[i]
            piste.boite, piste.vue = boite, instant
            piste.trajet.append((instant, *(int(v) for v in boite)))
            piste.taille_image = (image.shape[1], image.shape[0])
            piste.analyses += 1
            piste.p_tortue.append(p_tortue)
            for nom, p in classes[:3]:
                piste.especes[nom] += p
            isolee = all(ecart(boite, f[1]) > 1.5 for j, f in enumerate(fiches) if j != i)
            self._reconnaitre(piste, image, boite, instant, isolee)
            if not piste.etiquette:
                piste.etiquette = piste.espece()
        self.duree_analyse = time.time() - t0

    def _galerie_especes(self):
        """Vecteurs BioCLIP des photos de galerie (tortues isolées de la maison), revus toutes les
        10 min ; seuls les nouveaux fichiers sont calculés. None s'il y en a moins de GALERIE_MIN."""
        if not hasattr(self.classeur, "vecteur"):
            return None
        if time.time() - self._galerie_vue < 600 and self._galerie_cache is not None:
            return self._galerie_matrice
        self._galerie_vue = time.time()
        cache = self._galerie_cache or {}
        actuel = {}
        for p in sorted(Path(self.registre.dossier).glob("*/*.jpg")):
            if p.parent.name == "pas_une_tortue":
                continue
            cle = (str(p), p.stat().st_size)
            if cle in cache:
                actuel[cle] = cache[cle]
            else:
                img = lire_image(p)
                if img is not None:
                    actuel[cle] = self.classeur.vecteur(img)
        self._galerie_cache = actuel
        self._galerie_matrice = np.stack(list(actuel.values())) if len(actuel) >= GALERIE_MIN else None
        return self._galerie_matrice

    def nommer_piste(self, numero, cle):
        """L'utilisateur nomme sur la vidéo la tortue suivie `numero` : `cle` d'une fiche, ou
        PAS_UNE_TORTUE. La visite sera notée à ce nom (corrigée à la main) et ses vues isolées
        rejoindront la galerie. Renvoie False si la tortue est déjà partie."""
        if cle != PAS_UNE_TORTUE and cle not in self.registre.fiches:
            raise KeyError(cle)
        with self._verrou:
            piste = next((p for p in self.pistes if p.numero == numero), None)
            if piste is None:
                return False
            piste.nommee = cle
            piste.etiquette = PAS_UNE_TORTUE if cle == PAS_UNE_TORTUE else self.registre.fiches[cle]["nom"]
        self.sur_message(f"Tortue nommée sur la vidéo : {piste.etiquette}")
        return True

    def _seuil_image(self):
        unique = sum(g is not None for g in self.registre.vecteurs.values()) <= 1
        return self.seuil + (SUPPLEMENT_FICHE_UNIQUE if unique else 0.0)

    def _reconnaitre(self, piste, image, boite, instant, isolee):
        tortue = vision.isoler_tortue(image, boite)
        if tortue is None:
            return
        if not self.reconnaissance_active:      # la photo de la visite reste utile
            piste.ajouter_exemple(nettete(tortue), tortue, None, image)
            return
        vecteurs = self.registre.descripteur.decrire(tortue)
        if self.registre.est_rejet(vecteurs):
            piste.rejets += 1
            return
        classement = self.registre.similarites(vecteurs, vision.points_sift(tortue))
        cle, score = classement[0] if classement else (None, 0.0)
        piste.ajouter_exemple(nettete(tortue), tortue, vecteurs, image, cle, score, isolee)
        if cle is None:
            return
        deuxieme = classement[1][1] if len(classement) > 1 else 0.0
        if score >= SEUIL_PROPOSITION:
            piste.proposition[cle] += score
        if score >= self._seuil_image() and score - deuxieme >= self.marge:
            piste.individus[cle].append((instant, score))
        if piste.nommee is not None:            # nommée sur la vidéo : son nom ne change plus
            return
        fiches = self.registre.fiches
        sure = piste.verdict()[0]
        if sure in fiches:
            piste.etiquette = fiches[sure]["nom"]
        elif piste.probable() in fiches:
            piste.etiquette = f"{fiches[piste.probable()]['nom']} ?"

    # --- fin de présence
    def _enrichir_galerie(self, piste, cle, nouvelle, base_visite, manuelle=False):
        """Reconnue une fois, une tortue gagne ses autres vues de la visite. Seulement celles où elle
        est aussi arrivée en tête, sans voisine tout près : une vue d'une autre tortue, entrée par un
        échange de pistes, ferait reconnaître cette autre tortue à sa place."""
        r = self.registre
        for i, (_q, tortue, vecteurs, _image, tete, score, isolee) in enumerate(piste.exemples):
            if manuelle:                    # l'utilisateur l'a nommée : ses vues seules sont sûres
                if isolee:
                    r.ajouter_exemple(cle, tortue, f"{base_visite}_{i}.jpg")
                continue
            if vecteurs is None or not (nouvelle or (tete == cle and score >= SEUIL_PROPOSITION and isolee)):
                continue
            g = r.vecteurs.get(cle)
            if g is None or float((vecteurs @ g.T).max()) < EXEMPLE_DIFFERENT:
                r.ajouter_exemple(cle, tortue, f"{base_visite}_{i}.jpg")

    def _terminer_piste(self, piste):
        """Écrit la ligne du journal d'une tortue partie ; renvoie la ligne, ou None si fausse alerte."""
        duree = max(0.0, piste.vue - piste.debut)
        r = self.registre
        if piste.nommee == PAS_UNE_TORTUE:          # désignée sur la vidéo : ignorée la prochaine fois
            base = f"{piste.arrivee:%Y-%m-%d_%H-%M-%S}_{piste.numero}"
            r.rejeter([(f"{base}_{i}.jpg", cv2.imencode(".jpg", e[1])[1].tobytes())
                       for i, e in enumerate(piste.exemples) if e[6]])
        if (duree < self.presence_min and piste.nommee is None) or not piste.confirmee():   # bout de tortue, pierre
            self._nettoyer_clip(piste.clip)
            return None
        espece = piste.espece()
        cle, score = piste.verdict()
        cle = r.resoudre(cle) if cle else None
        source = "image"
        nouvelle = False
        manuelle = piste.nommee is not None and r.resoudre(piste.nommee) is not None
        if manuelle:
            cle, score, source = r.resoudre(piste.nommee), 1.0, "manuel"
        if cle is None and self.reconnaissance_active and self.creer_nouvelles and len(piste.exemples) >= 2:
            cle = r.creer(r.nom_provisoire(espece), espece, provisoire=True)
            score, source, nouvelle = 0.0, "nouvelle", True
            self.sur_message(f"Nouvelle tortue : {r.fiches[cle]['nom']}")
        base_visite = f"{piste.arrivee:%Y-%m-%d_%H-%M-%S}_{piste.numero}"
        if cle:
            self._enrichir_galerie(piste, cle, nouvelle, base_visite, manuelle)
        photo = ""
        if piste.exemples:
            photo = f"{base_visite}_photo.jpg"
            ecrire_image(self.dossier / photo, piste.exemples[0][3])
            ecrire_image(self.dossier / f"{base_visite}_tortue.jpg", piste.exemples[0][1])
        fiche = r.copie_fiches().get(cle) if cle else None
        ligne = {"id_visite": base_visite, "date": f"{piste.arrivee:%Y-%m-%d}", "heure": f"{piste.arrivee:%H:%M:%S}",
                 "duree_s": f"{duree:.0f}", "individu": fiche["nom"] if fiche else INCONNUE,
                 "espece": fiche["espece"] if fiche else espece, "confiance": f"{min(score, 1):.2f}",
                 "video": piste.clip or "", "photo": photo, "source": source, "corrige": "1" if manuelle else "",
                 "id_individu": cle or "",
                 "proposition": "", "id_proposition": ""}
        probable = r.resoudre(piste.probable()) if piste.probable() else None
        if cle is None and probable:
            ligne.update(proposition=r.fiches[probable]["nom"], id_proposition=probable)
        if not ajouter_ligne(self.dossier, ligne):
            self.sur_message("visites.csv est ouvert ailleurs : la visite attend d'y être écrite")
        try:
            ecrire_positions(self.dossier, base_visite, piste)
        except OSError as e:            # positions perdues : la visite, elle, est notée
            self.sur_message(f"Positions non écrites : {e}")
        self.sur_message(f"Fin de visite : {ligne['individu']} ({ligne['espece']}), {duree:.0f} s")
        self.sur_visite(ligne)
        self._nettoyer_clip(piste.clip)
        return ligne

    def _menage(self):
        garder = {self.chemin_clip.name} if self.chemin_clip else set()
        n = nettoyer(self.dossier, self.menage_jours, self.menage_go, garder)
        if n:
            self.sur_message(f"Ménage : anciens clips effacés : {n}")

    def _cadrer(self, image):
        if self.zone is None:
            return image
        h, w = image.shape[:2]
        x0, y0, x1, y1 = self.zone
        cadre = image[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]
        return cadre if cadre.size else image

    def _mouvement(self, fond, image):
        e = 480 / image.shape[1]
        masque = fond.apply(cv2.GaussianBlur(cv2.resize(image, None, fx=e, fy=e), (5, 5), 0))
        return np.count_nonzero(cv2.morphologyEx(masque, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))) > self.surface * masque.size

    # --- boucle
    def _lancer_lecteur(self):
        self.lecteur = LecteurCamera(self.source, self.sur_message)
        self.lecteur.start()

    def _suivante_direct(self):
        """(image, instant) de la source en direct, ou None s'il faut réessayer."""
        try:
            return self.lecteur.file.get(timeout=1)
        except queue.Empty:
            if self.lecteur.en_lecture and time.time() - self.lecteur.derniere > self.SILENCE_MAX:
                self.sur_message("Source figée : reconnexion…")
                self.lecteur.fin.set()      # son fil reste bloqué dans read() : on l'abandonne
                self._lancer_lecteur()
            return None

    def executer(self):
        self.dossier.mkdir(parents=True, exist_ok=True)
        assurer_journal(self.dossier / "visites.csv")
        self._menage()
        self.registre.preparer()
        fil_taches = threading.Thread(target=self._fil_taches, daemon=True)
        fil_taches.start()
        camera = None
        try:
            if self.fichier:
                camera, image = ouvrir_source(self.source)
                ouverte = camera is not None
            else:
                self._lancer_lecteur()
                while not self.lecteur.pret.wait(0.5) and not self.arret.is_set():
                    pass
                ouverte = self.lecteur.pret.is_set() and not self.lecteur.echec
            if not ouverte:
                if not self.arret.is_set():
                    self.sur_message(f"La source vidéo ne renvoie aucune image : {masquer(self.source)} (fenêtre fermée, "
                                     "réduite ou cachée par une autre fenêtre, adresse fausse, caméra prise par une autre application, ou accès refusé "
                                     "dans Paramètres › Confidentialité › Caméra)")
                return False
            self._boucle(camera)
            return True
        finally:
            if not self.fichier and getattr(self, "lecteur", None):
                self.lecteur.fin.set()
                self.lecteur.join(5)    # caméra rendue avant de redémarrer, sauf si son read() est bloqué
            if camera is not None:
                camera.release()
            self._taches.put(None)
            fil_taches.join(60)

    def _boucle(self, camera):
        fps_declare = 15.0
        if self.fichier:
            f = camera.get(cv2.CAP_PROP_FPS)
            fps_declare = f if 1 < f < 120 else 15.0
            camera.set(cv2.CAP_PROP_POS_FRAMES, 0)
        fond = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=32, detectShadows=False)
        # le tampon couvre aussi le temps de confirmer une tortue ; compressé : en 1080p, 10 s brutes
        # à 30 i/s pèseraient 5 Go
        tampon = deque()
        fenetre_tampon = self.avant + 2 * self.analyse_toutes
        derniere_analyse = -1e9
        fil = None
        nb_lues = 0
        taille = None
        t_fps, n_fps, fps_mesure = time.time(), 0, 0.0
        t_debut, t_menage = time.time(), time.time()
        petite_prec, t_change, figee = None, time.time(), False
        try:
            while not self.arret.is_set():
                if self.fichier:
                    ok, image = camera.read()
                    if not ok:
                        break
                    nb_lues += 1
                    instant = nb_lues / fps_declare
                    if self.temps_reel:
                        attente = t_debut + instant - time.time()
                        if attente > 0:
                            time.sleep(attente)
                else:
                    lu = self._suivante_direct()
                    if lu is None:
                        continue
                    image, instant = lu
                image = self._cadrer(image)
                if taille is None:
                    taille = (image.shape[1], image.shape[0])
                elif (image.shape[1], image.shape[0]) != taille:
                    image = ajuster(image, taille)   # autre résolution ou autre cadre : même format de clip

                # image figée : un direct vivant change toujours un peu (bruit de compression, horloge
                # incrustée). Rien ne bouge pendant FIGEE_S : le lecteur a sans doute arrêté le direct.
                if not self.fichier:
                    petite = cv2.cvtColor(cv2.resize(image, (96, max(1, 96 * image.shape[0] // image.shape[1]))),
                                          cv2.COLOR_BGR2GRAY)
                    if petite_prec is None or petite.shape != petite_prec.shape or \
                            int(cv2.absdiff(petite, petite_prec).max()) > SEUIL_FIGEE:
                        t_change = time.time()
                    petite_prec = petite
                    maintenant_figee = time.time() - t_change >= self.figee_s
                    if maintenant_figee != figee:
                        figee = maintenant_figee
                        self.sur_message("Image figée depuis 1 min : le direct est sans doute arrêté" if figee
                                         else "Image revenue : le direct tourne")
                        self.sur_figee(figee)
                mouvement = self._mouvement(fond, image)
                intervalle = self.analyse_toutes if (self.pistes or mouvement) else self.veille_toutes
                if instant - derniere_analyse >= intervalle:
                    if self.fichier:
                        derniere_analyse = instant
                        self._analyser_protege(image, instant)
                    elif fil is None or not fil.is_alive():
                        derniere_analyse = instant
                        fil = threading.Thread(target=self._analyser_protege, args=(image, instant), daemon=True)
                        fil.start()

                with self._verrou:
                    presentes = list(self.pistes)
                confirmees = [p for p in presentes if p.confirmee()]
                # chaque nouvelle tortue a son clip, même si une pierre ou une dormeuse occupe le champ
                nouvelles = [p for p in confirmees if p.clip is None]
                if nouvelles and self.video is None:
                    fps = fps_declare if self.fichier else self.lecteur.fps()
                    self._ouvrir_clip(fps, taille, tampon, instant)
                    if self.video is not None:
                        self.sur_message("Tortue : début d'enregistrement")
                for p in nouvelles:
                    p.clip = self.chemin_clip.name if self.video is not None else ""
                if self.video is not None:
                    self.video.write(image)
                    self.nb_clip += 1
                    if instant - self.debut_clip >= self.clip_max or not confirmees:
                        self._fermer_clip()     # une tortue mange parfois une heure : le clip reste court
                else:
                    tampon.append((instant, cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tobytes()))
                    while tampon and instant - tampon[0][0] > fenetre_tampon:
                        tampon.popleft()

                # sur processeur, une analyse lente ne doit pas couper une visite en deux
                delai = max(self.apres, 3 * self.duree_analyse)
                for piste in [p for p in presentes if instant - p.vue > delai]:
                    with self._verrou:
                        self.pistes.remove(piste)
                    self._tache(self._terminer_piste, piste)

                if time.time() - t_menage > 600:
                    t_menage = time.time()
                    self._tache(self._menage)
                n_fps += 1
                if time.time() - t_fps >= 1:
                    fps_mesure, t_fps, n_fps = n_fps / (time.time() - t_fps), time.time(), 0
                self.sur_image(image, {"tortues": [(p.boite, p.etiquette or "…") for p in confirmees],
                                       "enregistrement": self.video is not None, "fps": fps_mesure,
                                       "duree": instant - self.debut_clip if self.video is not None else 0,
                                       "presence": len(confirmees),
                                       # toutes les pistes, douteuses comprises : un clic sur la vidéo les nomme
                                       # 5e valeur : fiche de la tortue (choisie ou probable), pour ouvrir sa fiche d'un clic
                                       "pistes": [(p.numero, p.boite, p.etiquette or "…", p.confirmee(),
                                                   p.nommee or p.probable())
                                                  for p in presentes if p.nommee != PAS_UNE_TORTUE],
                                       "figee_s": time.time() - t_change if figee else 0})
        finally:
            if fil is not None:
                fil.join(30)
            self._fermer_clip()
            with self._verrou:
                restantes, self.pistes = list(self.pistes), []
            for piste in restantes:
                self._tache(self._terminer_piste, piste)
            self._tache(self._menage)

    def _analyser_protege(self, image, instant):
        try:
            self._analyser(image, instant)
        except Exception as e:      # une analyse ratée ne doit pas arrêter la surveillance
            self.sur_message(f"Analyse impossible : {type(e).__name__} : {e}")


# ------------------------------------------------------------------
#  Corrections (depuis l'application)
# ------------------------------------------------------------------
def corriger_visite(dossier, registre, id_visite, cle):
    """La visite montre la tortue `cle` (ou PAS_UNE_TORTUE) : journal corrigé, puis photos de la visite
    déplacées vers la bonne galerie. Le journal d'abord : s'il est bloqué (JournalOccupe), rien n'a bougé.
    Renvoie la ligne corrigée, avec "sans_image" si le ménage a déjà effacé les images de la visite."""
    dossier = Path(dossier)
    avant = {}

    def corriger(lignes):
        ligne = next((l for l in lignes if l.get("id_visite") == id_visite), None)
        if ligne is None:
            return None
        avant.update(ligne)
        if cle == PAS_UNE_TORTUE:
            lignes.remove(ligne)
            return ligne
        fiche = registre.fiches[cle]
        ligne.update(individu=fiche["nom"], espece=fiche["espece"], corrige="1", source="manuel", id_individu=cle,
                     confiance="1.00", proposition="", id_proposition="")
        return ligne

    ligne = modifier_journal(dossier, corriger)
    if ligne is None:
        return None
    ancienne = avant.get("id_individu")
    contenus = registre.retirer_exemples(ancienne, id_visite) if ancienne in registre.fiches else []
    fichier_tortue = dossier / f"{id_visite}_tortue.jpg"
    if not contenus and fichier_tortue.exists():
        contenus = [(f"{id_visite}_0.jpg", fichier_tortue.read_bytes())]
    resultat = {**ligne, "sans_image": not contenus}
    if cle == PAS_UNE_TORTUE:
        registre.rejeter(contenus)
        for suffixe in ("_photo.jpg", "_tortue.jpg"):
            (dossier / (id_visite + suffixe)).unlink(missing_ok=True)
        if avant.get("video") and not any(l["video"] == avant["video"] for l in lire_journal(dossier)):
            (dossier / avant["video"]).unlink(missing_ok=True)
        resultat["individu"] = PAS_UNE_TORTUE
    else:
        registre.deposer_exemples(cle, contenus)
    if ancienne and ancienne != cle and ancienne in registre.fiches and registre.fiches[ancienne].get("provisoire") \
            and not registre.fichiers.get(ancienne):
        registre.supprimer(ancienne)    # une tortue provisoire dont il ne reste rien
    return resultat


def renommer_dans_journal(dossier, cle, nom=None, espece=None, nouvelle_cle=None):
    """Répercute un renommage, une fusion ou une suppression sur toutes les visites."""
    def renommer(lignes):
        for l in lignes:
            if l.get("id_individu") == cle:
                l["individu"] = nom or l["individu"]
                l["espece"] = espece or l["espece"]
                l["id_individu"] = l["id_individu"] if nouvelle_cle is None else nouvelle_cle
            if l.get("id_proposition") == cle:
                l["proposition"] = (nom or l["proposition"]) if nouvelle_cle != "" else ""
                l["id_proposition"] = l["id_proposition"] if nouvelle_cle is None else nouvelle_cle

    modifier_journal(dossier, renommer)


def inscrire_photos(registre, detecteur, cle, chemins, sur_message=print):
    """Photos importées d'une tortue : chaque photo enrichit sa galerie."""
    n = 0
    for chemin in chemins:
        image = lire_image(chemin)
        if image is None:
            sur_message(f"Illisible : {Path(chemin).name}")
            continue
        d = detecteur.detecter(image)
        if not d:
            sur_message(f"Pas de tortue trouvée : {Path(chemin).name}")
            continue
        tortue = vision.isoler_tortue(image, max(d, key=lambda x: x[0])[1])
        if tortue is not None:
            registre.ajouter_exemple(cle, tortue, f"import_{time.time_ns()}_{nom_fichier(Path(chemin).stem)}.jpg")
            n += 1
    return n


# ------------------------------------------------------------------
#  Ligne de commande
# ------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description="Broutille : surveillance d'une mangeoire à tortues")
    p.add_argument("--source", default="0", help="webcam (0), fenetre:Titre, adresse d'un flux ou fichier vidéo")
    p.add_argument("--dossier", default="visites")
    p.add_argument("--seuil", type=float, default=SEUIL_INDIVIDU)
    p.add_argument("--apres", type=float, default=20, help="secondes sans tortue avant de clore la visite")
    p.add_argument("--analyse-toutes", type=float, default=None)
    a = p.parse_args()
    Surveillance(a.source, a.dossier, seuil=a.seuil, apres=a.apres, analyse_toutes=a.analyse_toutes).executer()


if __name__ == "__main__":
    main()
