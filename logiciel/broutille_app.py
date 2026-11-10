"""
Broutille — la mangeoire qui reconnaît ses tortues (application de bureau).

Vidéo en direct (webcam, fenêtre ouverte ou flux Internet), enregistrement automatique des
visites, espèce et individu de chaque tortue, fiches des tortues (renommer, fusionner, ajouter des photos), corrections dont l'application
apprend aussitôt, temps de repas du jour et historique avec vignettes.
"""

import json
import os
import queue
import secrets
import sys
import threading
import time
import tkinter as tk
import traceback
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import cv2
from PIL import Image, ImageDraw, ImageOps, ImageTk

import alertes
import clips
import cameras
import comportement
import deplacements
import demarrage
import fiches
import i18n
import rapports
import sauvegarde
import sources
import vision
import web
from broutille_cam import (INCONNUE, VERROU_JOURNAL, MARGE_INDIVIDU, PAS_UNE_TORTUE, SEUIL_INDIVIDU, JournalOccupe, Registre,
                           ALBUM, RegistreIllisible, Surveillance, corriger_visite, inscrire_photos, lire_journal,
                           lire_positions, renommer_dans_journal, secondes)
from i18n import nombre, pourcent, t, tn

ICI = Path(__file__).resolve().parent
if (ICI / "hf_cache").is_dir():     # version installée : modèles livrés avec l'installateur
    os.environ.setdefault("HF_HOME", str(ICI / "hf_cache"))
CONFIG = Path.home() / ".broutille.json"
DEFAUTS = {
    "source": "0",              # source de la caméra affichée (copie de cameras[...]["source"])
    "cameras": [],              # [{"id", "nom", "source"}] : une surveillance par caméra
    "camera_courante": "",      # caméra affichée
    "dossier": str(Path.home() / "Videos" / "Broutille"),
    "seuil": SEUIL_INDIVIDU,
    "reconnaissance": True,
    "creer_nouvelles": False,   # sinon une tortue vue sous un angle nouveau créerait une fausse fiche
    "alerte_jours": 3,          # tortue signalée si elle n'est pas venue depuis ce nombre de jours
    "menage_jours": 60,
    "menage_go": 20,
    "demarrage_auto": False,
    "lancer_avant": "",         # programme ouvert avant la surveillance (ex. EZVIZ Studio), au démarrage de Windows
    "sans_admin": False,        # ouvrir ce programme sans droits administrateur : permet la relance du direct
    "relance_auto": False,      # image figée : cliquer sur le bouton du lecteur qui relance le direct
    "relance_point": None,      # ce bouton, en fractions de la fenêtre du lecteur
    "sauvegarde_dossier": "",   # clé USB, OneDrive... ; vide = pas de sauvegarde
    "rappel_pesee_jours": 30,   # tortue en orange si sa dernière pesée est plus ancienne ; 0 = jamais
    "especes_actives": [e[1] for e in vision.ESPECES_DEFAUT[:2]],   # noms scientifiques
    "zones": {},                # source (sans mot de passe) -> partie de l'image à garder (x0, y0, x1, y1 en fractions)
    "camera_ip": "",            # adresse RTSP de la caméra IP : gardée même quand on choisit une autre source
    "web_actif": False,         # accès depuis le téléphone (Wi-Fi de la maison)
    "web_code": "",             # code à 6 chiffres demandé par le téléphone ; créé au premier usage
    "web_port": 0,              # port retenu (0 = premier libre à partir de 8642)
    "ntfy_actif": False,        # alertes sur le téléphone par l'appli ntfy
    "ntfy_sujet": "",           # sujet secret, tiré au hasard au premier usage
    "ntfy_serveur": alertes.SERVEUR,
    "clips_auto": True,         # clip vertical (Shorts / Reels) après la visite d'une tortue reconnue
    "langue": "",               # "" = langue de Windows
}

# Thème
FOND, CARTE, BORD = "#10140f", "#1b2119", "#2d3729"
TEXTE, DISCRET = "#e9eee3", "#97a38d"
VERT, ROUGE, BLEU, AMBRE = "#7fb950", "#f85149", "#58a6ff", "#d9a441"
COULEURS = ["#7fb950", "#d9a441", "#58a6ff", "#f778ba", "#a371f7", "#ffa657", "#79c0ff", "#7ee787"]


def police(taille, gras=False):
    """Police PIL de la langue (Segoe UI ; CJK, thaï… selon la langue)."""
    return i18n.police_pil(taille, gras)


def PT(taille, gras=False):
    """Police Tk de la langue : Segoe UI (Semibold si gras) ou la famille qui a les caractères."""
    famille = i18n.famille_tk()
    if famille == "Segoe UI":
        return ("Segoe UI Semibold", taille) if gras else ("Segoe UI", taille)
    return (famille, taille, "bold") if gras else (famille, taille)


def libelle_source(source):
    source = str(source)
    if source.isdigit():
        return t("Webcam {n}", n=source)
    camera = cameras.lire_adresse(source)
    if camera:                          # caméra IP : jamais le mot de passe à l'écran
        return t("Caméra IP : {adresse}", adresse=camera[0]) + (f" ({camera[3].split('?')[0]})" if camera[3] else "")
    if sources.est_fenetre(source):
        return t("Fenêtre : {titre}", titre=source[len(sources.PREFIXE_FENETRE):])
    return sources.masquer(source)      # flux http avec identifiants : masqués aussi


def _extraire(saisie, modele):
    """Partie variable de saisie selon un modèle « avant\\0après » ; None si saisie ne suit pas le modèle."""
    avant, _sep, apres = modele.partition("\0")
    if (avant or apres) and len(saisie) >= len(avant) + len(apres) and saisie.startswith(avant) and saisie.endswith(apres):
        return saisie[len(avant):len(saisie) - len(apres)]
    return None


def cle_source(source):
    """Clé d'une source dans les réglages (cadrage) : sans son mot de passe, qui peut changer."""
    source = str(source)
    camera = cameras.lire_adresse(source)
    if camera:
        return f"rtsp://{camera[0]}:{camera[4]}/{camera[3]}"
    return sources.masquer(source) if sources.est_flux(source) else source


def source_depuis_saisie(saisie, *connues):
    """Texte de la liste « Caméra » → source. connues : sources enregistrées (actuelle, caméra IP) ;
    leur libellé (mot de passe caché) renvoie à elles."""
    saisie = saisie.strip()
    for connue in connues:
        if connue and saisie == libelle_source(connue):
            return str(connue)
    for modele in (t("Caméra IP : {adresse}", adresse="\0"), "Caméra IP : \0"):
        avant = modele.partition("\0")[0].rstrip()
        if avant and saisie.startswith(avant):  # libellé retouché à la main : la caméra enregistrée, pas du texte
            return next((str(c) for c in connues if c and cameras.lire_adresse(c)), saisie)
    for modele in (t("Webcam {n}", n="\0"), "Webcam \0"):
        reste = _extraire(saisie, modele)
        if reste is not None:
            return reste
    for modele in (t("Fenêtre : {titre}", titre="\0"), "Fenêtre : \0"):
        reste = _extraire(saisie, modele)
        if reste is not None:
            return sources.PREFIXE_FENETRE + reste
    return saisie


def duree_lisible(secondes):
    secondes = int(secondes)
    if secondes < 60:
        return t("{n} s", n=secondes)
    if secondes < 3600:
        return t("{n} min", n=secondes // 60)
    return t("{h} h {min}", h=secondes // 3600, min=f"{secondes % 3600 // 60:02d}")


def date_courte(valeur):
    """"2026-11-10" → jour et mois seuls, dans l'ordre de la langue (« 10/11 », « 11/10 »…)."""
    if not valeur or len(valeur) < 10:
        return valeur or ""
    return t("{jour}/{mois}", jour=valeur[8:10], mois=valeur[5:7])


def date_longue(valeur):
    """"2026-11-10" → « 10/11/2026 » dans l'ordre de la langue."""
    if not valeur or len(valeur) < 10:
        return valeur or ""
    return t("{jour}/{mois}/{annee}", jour=valeur[8:10], mois=valeur[5:7], annee=valeur[:4])


def nom_affiche(nom):
    """Nom d'une tortue au journal ; « Inconnue » (valeur stockée) traduit à l'affichage."""
    return t("Inconnue") if nom == INCONNUE else nom


def especes_affichees(especes):
    """(libellés traduits des espèces, {libellé traduit: nom français stocké}) ; especes : [(nom, …)]."""
    noms = [x[0] for x in especes]
    return [t(n) for n in noms], {t(n): n for n in noms}


class App:
    def __init__(self, root):
        self.root = root
        self.cfg = {**DEFAUTS, **self._lire_config()}
        i18n.choisir(self.cfg.get("langue") or i18n.langue_systeme())
        for cle, maxi in (("alerte_jours", 3650), ("menage_jours", 3650), ("rappel_pesee_jours", 3650), ("menage_go", 100000)):
            try:                            # un réglage hors bornes (fichier retouché) ne doit pas empêcher de démarrer
                self.cfg[cle] = type(DEFAUTS[cle])(min(max(0, self.cfg[cle]), maxi))
            except (TypeError, ValueError):
                self.cfg[cle] = DEFAUTS[cle]
        if not self.cfg.get("camera_ip") and cameras.lire_adresse(self.cfg["source"]):
            self.cfg["camera_ip"] = self.cfg["source"]
        self.cfg["zones"] = {cle_source(k): v for k, v in self.cfg["zones"].items()}
        if not self.cfg["cameras"]:     # réglages d'avant les caméras multiples : la source devient la 1re caméra
            self.cfg["cameras"] = [{"id": "c1", "nom": t("Mangeoire"), "source": str(self.cfg["source"])}]
            if self.cfg.get("camera_ip") and self.cfg["camera_ip"] != self.cfg["source"]:
                self.cfg["cameras"].append({"id": "c2", "nom": t("Caméra IP"), "source": self.cfg["camera_ip"]})
        if not self._camera(self.cfg["camera_courante"]):
            self.cfg["camera_courante"] = self.cfg["cameras"][0]["id"]
        self.cfg["source"] = self._camera()["source"]
        self.surveillances = {}         # caméra -> Surveillance en cours
        self.messages = queue.Queue()
        self.verrou = threading.Lock()
        self.derniere_image = {}        # caméra -> (image, etat) pas encore affichée
        self.presence = {}              # caméra -> tortues à table
        self.image_affichee = None
        self.vignettes = {}
        self.vignettes_tortues = {}
        self.cache_vignettes = {}       # (chemin, taille, date du fichier) -> PhotoImage
        self.verrou_corrections = threading.Lock()
        self.jour_stats = datetime.now().date()
        self.fenetres_fiche = {}        # clé -> fenêtre de fiche ouverte
        self.diffusion = None           # fenêtre plein écran pour le stream (YouTube…)
        self.repas_du_jour = []         # [(nom, secondes)] des repas d'aujourd'hui, les plus longs d'abord
        self.image_web = {}             # caméra -> dernière image, pour le téléphone
        self.serveur_web = None
        self.alertes = None
        self.file_clips = queue.Queue()
        self.dernier_clip = {}          # clé -> instant du dernier clip automatique
        self.photo_visite = None
        self.modeles_prets = False
        self.fermeture = False
        self.figee = {}                 # caméra -> image figée
        self.relance_serie = {}         # caméra -> numéro de la série d'essais de relance en cours
        self.sauvegarde_en_cours = False
        self.detecteur = vision.DetecteurTortues()
        self.classeur = vision.ClasseurEspeces([e for e in vision.ESPECES_DEFAUT if e[1] in self.cfg["especes_actives"]])
        self.registre = Registre(self.dossier)
        self.f_tag, self.f_petit, self.f_vide = police(20, True), police(15), police(20)
        self._style()
        self._construire()
        self.charger_historique()
        threading.Thread(target=self._precharger, daemon=True).start()
        self.root.protocol("WM_DELETE_WINDOW", self.quitter)
        self.root.after(30, self._boucle)
        if "--demarrage" in sys.argv:            # lancé par le raccourci du dossier Démarrage
            self.root.after(500, self._demarrage_windows)
        elif self.cfg["demarrage_auto"]:
            self.root.after(500, lambda: self.tout_demarrer(insister=True))
        self.root.after(15000, self._sauvegarde_auto)
        self._maj_alertes()
        threading.Thread(target=self._fil_clips, daemon=True).start()
        if self.cfg["web_actif"]:
            self.root.after(800, lambda: self._web(True, silencieux=True))

    def _demarrage_windows(self):
        """Au démarrage de Windows : ouvre le programme prévu (EZVIZ Studio) si une caméra filme une
        fenêtre, attend chaque fenêtre jusqu'à 2 min, puis lance la surveillance de chaque caméra.
        Une caméra IP ou une webcam démarre tout de suite (et attend elle-même sa caméra)."""
        self._camera()["source"] = self._saisie_source()
        titre = lambda c: c["source"][len(sources.PREFIXE_FENETRE):]
        fenetres = [c for c in self.cfg["cameras"] if sources.est_fenetre(c["source"])]
        programme = self.cfg["lancer_avant"]
        if programme and fenetres and not all(sources.trouver_fenetre(titre(c)) for c in fenetres):
            try:
                demarrage.lancer_programme(programme, self.cfg["sans_admin"])
            except OSError as e:
                self.lbl_etat.configure(text=t("Impossible d'ouvrir {programme} : {erreur}", programme=Path(programme).name, erreur=e))
        fin = time.time() + 120
        restantes = [c["id"] for c in self.cfg["cameras"]]

        def lancer(ident):
            if ident not in self.surveillances:     # l'utilisateur a pu cliquer sur Démarrer entre-temps
                self.demarrer(ident, insister=True)

        def verifier():
            for ident in list(restantes):
                c = self._camera(ident)
                if c is None:
                    restantes.remove(ident)
                elif not sources.est_fenetre(c["source"]) or sources.trouver_fenetre(titre(c)):
                    restantes.remove(ident)
                    # une fenêtre trouvée : quelques secondes de plus, le lecteur doit encore afficher le direct
                    self.root.after(15000 if sources.est_fenetre(c["source"]) else 0, lambda i=ident: lancer(i))
            if restantes and time.time() < fin:
                self.lbl_etat.configure(text=t("En attente de la fenêtre « {titre} »…", titre=titre(self._camera(restantes[0]))))
                self.root.after(2000, verifier)
            elif restantes:
                self.lbl_etat.configure(text=t("Fenêtre introuvable après 2 min : ouvrez-la puis cliquez sur Démarrer"))
            else:
                self.lbl_etat.configure(text=t("Démarrage de la surveillance…"))

        verifier()

    # -------------------------------------------------------------- config
    def _lire_config(self):
        # fichier abîmé (coupure pendant l'écriture) : la copie .bak garde code du téléphone, sujet des alertes…
        for chemin in (CONFIG, CONFIG.with_suffix(".bak")):
            try:
                cfg = json.loads(chemin.read_text(encoding="utf-8"))
                if isinstance(cfg, dict):
                    return cfg
            except (OSError, ValueError):
                pass
        return {}

    def _ecrire_config(self):
        try:
            tmp = CONFIG.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.cfg, indent=2, ensure_ascii=False), encoding="utf-8")
            if CONFIG.exists():
                CONFIG.replace(CONFIG.with_suffix(".bak"))
            tmp.replace(CONFIG)
        except OSError:
            pass

    @property
    def dossier(self):
        return Path(self.cfg["dossier"])

    def _precharger(self):
        try:
            self.messages.put(("message", t("Chargement des modèles…")))
            self.detecteur.charger()
            self.classeur.charger()
            self.registre.descripteur.charger()
            self.registre.preparer()
            self.modeles_prets = True
            self.messages.put(("tortues", None))
            self.messages.put(("modele", "GPU" if vision.appareil() == "cuda" else t("Processeur")))
        except Exception as e:
            self.messages.put(("erreur_modele", f"{type(e).__name__} : {e}"))

    # -------------------------------------------------------------- style
    def _style(self):
        r = self.root
        r.title("Broutille")
        r.configure(bg=FOND)
        r.geometry("1440x900")
        r.minsize(1100, 720)
        try:
            r.state("zoomed")
        except tk.TclError:
            pass
        if (ICI / "broutille.ico").exists():
            try:
                r.iconbitmap(str(ICI / "broutille.ico"))
            except tk.TclError:
                pass
        s = ttk.Style(r)
        s.theme_use("clam")
        s.configure(".", background=FOND, foreground=TEXTE, font=PT(10), bordercolor=BORD,
                    lightcolor=CARTE, darkcolor=CARTE, troughcolor=BORD)
        s.configure("Carte.TFrame", background=CARTE)
        s.configure("TLabel", background=FOND, foreground=TEXTE)
        s.configure("Carte.TLabel", background=CARTE)
        s.configure("Discret.TLabel", background=CARTE, foreground=DISCRET)
        s.configure("Titre.TLabel", background=CARTE, foreground=DISCRET, font=PT(10, True))
        s.configure("TButton", background=CARTE, foreground=TEXTE, borderwidth=1, focusthickness=0, padding=(14, 8),
                    font=PT(10, True))
        s.map("TButton", background=[("active", BORD), ("disabled", CARTE)], foreground=[("disabled", DISCRET)])
        s.configure("Vert.TButton", background=VERT, foreground="#10200a", bordercolor=VERT)
        s.map("Vert.TButton", background=[("active", "#98d268")])
        s.configure("Rouge.TButton", background=ROUGE, foreground="white", bordercolor=ROUGE)
        s.map("Rouge.TButton", background=[("active", "#ff7b72")])
        s.configure("TCombobox", fieldbackground=CARTE, background=CARTE, foreground=TEXTE, arrowcolor=TEXTE, padding=6)
        s.map("TCombobox", fieldbackground=[("readonly", CARTE)], foreground=[("readonly", TEXTE)])
        r.option_add("*TCombobox*Listbox.background", CARTE)
        r.option_add("*TCombobox*Listbox.foreground", TEXTE)
        r.option_add("*TCombobox*Listbox.selectBackground", VERT)
        s.configure("Treeview", background=CARTE, fieldbackground=CARTE, foreground=TEXTE, rowheight=52, borderwidth=0,
                    font=PT(10))
        s.configure("Treeview.Heading", background=CARTE, foreground=DISCRET, borderwidth=0, font=PT(9, True))
        s.map("Treeview", background=[("selected", "#34452c")])
        s.configure("Liste.Treeview", rowheight=28)     # listes sans vignette : pesées, carnet
        s.configure("TCheckbutton", background=CARTE, foreground=TEXTE)
        s.map("TCheckbutton", background=[("active", CARTE)])
        s.configure("Horizontal.TScale", background=CARTE, troughcolor=BORD)
        s.configure("Vertical.TScrollbar", background=CARTE, troughcolor=FOND, arrowcolor=DISCRET)
        s.configure("TNotebook", background=CARTE, borderwidth=0, tabmargins=0)
        s.configure("TNotebook.Tab", background=CARTE, foreground=DISCRET, padding=(14, 6),
                    font=PT(10, True), borderwidth=0)
        s.map("TNotebook.Tab", background=[("selected", BORD)], foreground=[("selected", TEXTE)])
        s.configure("TEntry", fieldbackground=CARTE, foreground=TEXTE, insertcolor=TEXTE)
        s.configure("TSpinbox", fieldbackground=CARTE, foreground=TEXTE, arrowcolor=TEXTE)
        r.option_add("*Menu.background", CARTE)
        r.option_add("*Menu.foreground", TEXTE)
        r.option_add("*Menu.activeBackground", VERT)

    def _carte(self, parent, titre=None, **grid):
        cadre = ttk.Frame(parent, style="Carte.TFrame", padding=14)
        cadre.grid(**grid)
        if titre:
            ttk.Label(cadre, text=titre.upper(), style="Titre.TLabel").pack(anchor="w", pady=(0, 8))
        return cadre

    # -------------------------------------------------------------- interface
    def _construire(self):
        r = self.root
        r.columnconfigure(0, weight=1)
        r.rowconfigure(2, weight=1)

        tete = tk.Frame(r, bg=FOND)
        tete.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 6))
        try:
            self.logo = ImageTk.PhotoImage(Image.open(ICI / "broutille.png").resize((48, 48), Image.LANCZOS))
            tk.Label(tete, image=self.logo, bg=FOND).pack(side="left", padx=(0, 12))
        except OSError:
            pass
        titres = tk.Frame(tete, bg=FOND)
        titres.pack(side="left")
        tk.Label(titres, text="Broutille", bg=FOND, fg=TEXTE, font=PT(20, True)).pack(anchor="w")
        tk.Label(titres, text=t("la mangeoire qui reconnaît ses tortues"), bg=FOND, fg=DISCRET,
                 font=PT(10)).pack(anchor="w")
        self.pastille = tk.Label(tete, text="●  " + t("En veille"), bg=CARTE, fg=DISCRET, font=PT(11, True), padx=14, pady=6)
        self.pastille.pack(side="right")
        self.lbl_modele = tk.Label(tete, text=t("Modèles : chargement…"), bg=FOND, fg=DISCRET, font=PT(10))
        self.lbl_modele.pack(side="right", padx=16)

        cadre_barre = tk.Frame(r, bg=FOND)
        cadre_barre.grid(row=1, column=0, sticky="ew", padx=20, pady=(4, 10))
        self.barre_cameras = tk.Frame(cadre_barre, bg=FOND)
        self.barre_cameras.pack(fill="x", pady=(0, 8))
        barre = tk.Frame(cadre_barre, bg=FOND)
        barre.pack(fill="x")
        tk.Label(barre, text=t("Caméra"), bg=FOND, fg=DISCRET).pack(side="left")
        self.var_source = tk.StringVar(value=libelle_source(self.cfg["source"]))
        self.cb_source = ttk.Combobox(barre, textvariable=self.var_source, width=30)
        self._valeurs_sources()
        self.cb_source.pack(side="left", padx=(8, 4))
        ttk.Button(barre, text="📷  " + t("Caméra IP"), command=self.camera_ip).pack(side="left", padx=(0, 4))
        ttk.Button(barre, text="🪟  " + t("Fenêtre"), command=self.choisir_fenetre).pack(side="left", padx=(0, 4))
        ttk.Button(barre, text="🎞  " + t("Vidéo"), command=self._choisir_fichier).pack(side="left", padx=(0, 4))
        ttk.Button(barre, text="⛶  " + t("Cadrer"), command=self.cadrer).pack(side="left", padx=(0, 12))
        self.btn_demarrer = ttk.Button(barre, text="▶  " + t("Démarrer"), style="Vert.TButton", command=self.basculer)
        self.btn_demarrer.pack(side="left")
        ttk.Button(barre, text="🐢  " + t("Ajouter une tortue"), command=self.ajouter_tortue).pack(side="left", padx=(8, 0))
        ttk.Button(barre, text="📁  " + t("Dossier"), command=lambda: os.startfile(self.dossier) if self.dossier.exists() else None
                   ).pack(side="left", padx=(8, 0))
        ttk.Button(barre, text="⚙  " + t("Réglages"), command=self.reglages).pack(side="right")
        # suivi des tortues : en haut, à côté du titre, où il reste de la place
        suivi = tk.Frame(tete, bg=FOND)
        suivi.pack(side="left", padx=(28, 0))
        ttk.Button(suivi, text="✅  " + t("À confirmer"), style="Vert.TButton", command=self.confirmer_rapide).pack(side="left")
        ttk.Button(suivi, text="📊  " + t("Statistiques"), command=self.statistiques).pack(side="left", padx=(8, 0))
        ttk.Button(suivi, text="🧭  " + t("Comportement"), command=self.comportement).pack(side="left", padx=(8, 0))
        ttk.Button(suivi, text="📺  " + t("Plein écran"), command=self.plein_ecran).pack(side="left", padx=(8, 0))
        ttk.Button(suivi, text="📱  " + t("Téléphone"), command=self.telephone).pack(side="left", padx=(8, 0))
        r.bind("<F11>", lambda _e: self.plein_ecran())

        corps = tk.Frame(r, bg=FOND)
        corps.grid(row=2, column=0, sticky="nsew", padx=20)
        corps.columnconfigure(0, weight=1)
        corps.rowconfigure(0, weight=1)
        cadre_video = tk.Frame(corps, bg="#000000", highlightthickness=1, highlightbackground=BORD)
        cadre_video.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self.video = tk.Label(cadre_video, bg="#070a06")
        self.video.pack(fill="both", expand=True)
        self.video.bind("<Configure>", lambda e: self._afficher_vide() if self.surveillance is None else None)
        self.etat_pastilles = None
        self._maj_cameras()
        self.zones_video = []
        for bouton in ("<Button-1>", "<Button-3>"):
            self.video.bind(bouton, self._menu_video)

        droite = tk.Frame(corps, bg=FOND, width=400)
        droite.grid(row=0, column=1, sticky="ns")
        droite.grid_propagate(False)
        droite.columnconfigure(0, weight=1)
        droite.rowconfigure(2, weight=1)

        c = self._carte(droite, t("Dernière visite"), row=0, column=0, sticky="ew", pady=(0, 12))
        cadre_photo = tk.Frame(c, bg="#0c100a", width=370, height=150)
        cadre_photo.pack(fill="x")
        cadre_photo.pack_propagate(False)
        self.lbl_photo = tk.Label(cadre_photo, bg="#0c100a")
        self.lbl_photo.pack(fill="both", expand=True)
        self.lbl_individu = ttk.Label(c, text="—", style="Carte.TLabel", font=PT(16, True))
        self.lbl_individu.pack(anchor="w", pady=(10, 0))
        self.lbl_details = ttk.Label(c, text=t("Aucune visite pour l'instant"), style="Discret.TLabel", wraplength=360)
        self.lbl_details.pack(anchor="w")
        self.visite_affichee = None
        for w in (self.lbl_photo, self.lbl_individu):       # clic : fiche de la tortue de cette visite
            w.configure(cursor="hand2")
            w.bind("<Button-1>", lambda _e: self._fiche_visite_affichee())

        c = self._carte(droite, t("Repas d'aujourd'hui"), row=1, column=0, sticky="ew", pady=(0, 12))
        self.stats = tk.Canvas(c, bg=CARTE, height=30, highlightthickness=0)
        self.stats.pack(fill="x")

        c = self._carte(droite, None, row=2, column=0, sticky="nsew")
        onglets = ttk.Notebook(c)
        onglets.pack(fill="both", expand=True)
        cadre = ttk.Frame(onglets, style="Carte.TFrame")
        onglets.add(cadre, text=t("Visites"))
        self.arbre = self._arbre(cadre, (("quand", t("HEURE"), 74), ("individu", t("TORTUE"), 118), ("duree", t("DURÉE"), 56)))
        self.arbre.bind("<<TreeviewSelect>>", self._selection)
        self.arbre.bind("<Double-1>", self._ouvrir_video)
        self.arbre.bind("<Button-3>", self._menu_visite)
        self.lignes = {}
        cadre = ttk.Frame(onglets, style="Carte.TFrame")
        onglets.add(cadre, text=t("Mes tortues"))
        self.arbre_t = self._arbre(cadre, (("nom", t("NOM"), 122), ("visites", t("VISITES"), 54), ("vue", t("VUE"), 64),
                                           ("pesee", t("PESÉE"), 70)))
        self.arbre_t.tag_configure("provisoire", foreground=AMBRE)
        self.arbre_t.tag_configure("a_peser", foreground="#ffa657")
        self.arbre_t.tag_configure("absente", foreground=ROUGE)
        self.arbre_t.bind("<Button-3>", self._menu_tortue)
        self.arbre_t.bind("<Double-1>", self._ouvrir_galerie)
        ttk.Label(c, text=t("Clic droit : confirmer ou corriger une visite, nommer une tortue"), style="Discret.TLabel",
                  font=PT(9)).pack(anchor="w", pady=(6, 0))

        pied = ttk.Frame(r, style="Carte.TFrame", padding=(20, 10))
        pied.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        ttk.Label(pied, text=t("Exigence pour nommer une tortue"), style="Discret.TLabel").pack(side="left")
        self.var_seuil = tk.DoubleVar(value=self.cfg["seuil"] * 100)
        ttk.Scale(pied, from_=40, to=95, variable=self.var_seuil, length=170,
                  command=lambda v: self._maj_reglages()).pack(side="left", padx=(8, 4))
        self.lbl_seuil = ttk.Label(pied, width=5, style="Carte.TLabel")
        self.lbl_seuil.pack(side="left", padx=(0, 24))
        self.var_reco = tk.BooleanVar(value=self.cfg["reconnaissance"])
        ttk.Checkbutton(pied, text=t("Reconnaître les tortues"), variable=self.var_reco,
                        command=self._maj_reglages).pack(side="left", padx=(0, 16))
        self.var_nouvelles = tk.BooleanVar(value=self.cfg["creer_nouvelles"])
        ttk.Checkbutton(pied, text=t("Créer une fiche pour une tortue inconnue"), variable=self.var_nouvelles,
                        command=self._maj_reglages).pack(side="left")
        self.lbl_etat = ttk.Label(pied, text=t("Prêt"), style="Discret.TLabel", width=46, anchor="e")
        self.lbl_etat.pack(side="right")
        self._maj_reglages()

    def _arbre(self, parent, colonnes):
        arbre = ttk.Treeview(parent, columns=[c[0] for c in colonnes], show="tree headings", selectmode="browse")
        arbre.heading("#0", text="")
        arbre.column("#0", width=100, stretch=False)
        for col, titre, larg in colonnes:
            arbre.heading(col, text=titre, anchor="w")
            arbre.column(col, width=larg, anchor="w")
        defil = ttk.Scrollbar(parent, orient="vertical", command=arbre.yview)
        arbre.configure(yscrollcommand=defil.set)
        arbre.pack(side="left", fill="both", expand=True)
        defil.pack(side="right", fill="y")
        return arbre

    def _valeurs_sources(self):
        valeurs = [t("Webcam {n}", n=i) for i in range(4)]
        if self.cfg.get("camera_ip"):
            valeurs.insert(0, libelle_source(self.cfg["camera_ip"]))
        self.cb_source.configure(values=valeurs)

    def _saisie_source(self):
        return source_depuis_saisie(self.var_source.get(), self.cfg["source"], self.cfg.get("camera_ip", ""))

    def camera_ip(self):
        """Caméra Mercusys, Tapo ou autre RTSP : cherchée sur le Wi-Fi, testée, puis utilisée directement,
        sans application à laisser ouverte."""
        f = tk.Toplevel(self.root, bg=CARTE, padx=20, pady=16)
        f.title(t("Caméra IP (Mercusys, Tapo…)"))
        f.transient(self.root)
        actuelle = cameras.lire_adresse(self.cfg.get("camera_ip") or self.cfg["source"]) or ("", "", "", "stream1", 554)
        standard = actuelle[3] in ("", "stream1", "stream2") and actuelle[4] == cameras.PORT_RTSP
        # libellé traduit -> marque (clé de cameras.MARQUES) ; seule « Autre caméra RTSP » se traduit
        marques = {(t("Autre caméra RTSP") if m == "Autre caméra RTSP" else m): m for m in cameras.MARQUES}
        v_marque = tk.StringVar(value=next(iter(cameras.MARQUES)) if standard else t("Autre caméra RTSP"))
        v_port = tk.StringVar(value=str(actuelle[4]))
        v_ip, v_id, v_mdp = tk.StringVar(value=actuelle[0]), tk.StringVar(value=actuelle[1]), tk.StringVar(value=actuelle[2])
        v_qualite = tk.StringVar(value=t("Légère (stream2)") if actuelle[3] == "stream2" else t("Haute qualité (stream1)"))
        v_chemin = tk.StringVar(value=actuelle[3] or "stream1")
        ttk.Label(f, style="Discret.TLabel", justify="left", wraplength=560, text=t(
            "Dans l'appli Mercusys, créez d'abord le « compte de la caméra » (différent de votre compte Mercusys) :\n"
            "Accueil → carte de la caméra → Paramètres de l'appareil → Paramètres avancés → Compte de la caméra.\n"
            "Mettez aussi la qualité vidéo sur « Meilleure qualité ». Pour que l'adresse ne change pas, réservez-la "
            "dans votre box (bail DHCP fixe).")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))

        def ligne(rang, texte, widget, apres=None):
            ttk.Label(f, text=texte, style="Carte.TLabel").grid(row=rang, column=0, sticky="w", pady=5, padx=(0, 14))
            widget.grid(row=rang, column=1, sticky="w")
            if apres is not None:
                apres.grid(row=rang, column=2, sticky="w", padx=(8, 0))

        ligne(1, t("Marque"), ttk.Combobox(f, textvariable=v_marque, values=list(marques), state="readonly", width=28))
        trouvees = ttk.Combobox(f, textvariable=v_ip, width=28)
        btn_chercher = ttk.Button(f, text="🔎  " + t("Chercher sur le Wi-Fi"))
        ligne(2, t("Adresse IP de la caméra"), trouvees, btn_chercher)
        ligne(3, t("Identifiant (compte de la caméra)"), ttk.Entry(f, textvariable=v_id, width=30))
        ligne(4, t("Mot de passe"), ttk.Entry(f, textvariable=v_mdp, width=30, show="•"))
        qualite = ttk.Combobox(f, textvariable=v_qualite, values=(t("Haute qualité (stream1)"), t("Légère (stream2)")),
                               state="readonly", width=28)
        chemin = ttk.Entry(f, textvariable=v_chemin, width=30)
        ligne(5, t("Image"), qualite)
        lbl_chemin = ttk.Label(f, text=t("Chemin du flux et port"), style="Carte.TLabel")
        cadre_chemin = tk.Frame(f, bg=CARTE)
        chemin.grid_forget()
        chemin = ttk.Entry(cadre_chemin, textvariable=v_chemin, width=30)
        chemin.pack(side="left")
        ttk.Label(cadre_chemin, text="  " + t("port"), style="Carte.TLabel").pack(side="left")
        ttk.Entry(cadre_chemin, textvariable=v_port, width=6).pack(side="left", padx=(4, 0))
        apercu = tk.Label(f, bg=FOND, width=60, height=12, text=t("Aperçu après « Tester »"), fg=DISCRET)
        apercu.grid(row=7, column=0, columnspan=3, pady=(12, 8))
        statut = ttk.Label(f, style="Discret.TLabel", wraplength=560)
        statut.grid(row=8, column=0, columnspan=3, sticky="w")

        def maj_marque(*_):
            autre = not cameras.MARQUES[marques.get(v_marque.get(), v_marque.get())][0]
            for w in (lbl_chemin, cadre_chemin):
                w.grid_remove() if not autre else None
            if autre:
                lbl_chemin.grid(row=6, column=0, sticky="w", pady=5)
                cadre_chemin.grid(row=6, column=1, sticky="w")
        v_marque.trace_add("write", maj_marque)
        maj_marque()

        def url():
            flux = cameras.MARQUES[marques.get(v_marque.get(), v_marque.get())]
            if flux[0]:
                return cameras.adresse(v_ip.get(), v_id.get().strip(), v_mdp.get(),
                                       flux[1] if "stream2" in v_qualite.get() else flux[0])
            try:
                port = int(v_port.get())
            except ValueError:
                raise ValueError(t("port illisible")) from None
            return cameras.adresse(v_ip.get(), v_id.get().strip(), v_mdp.get(), v_chemin.get(), port)

        arret = threading.Event()               # fenêtre fermée : la recherche s'arrête
        f.bind("<Destroy>", lambda e: arret.set() if e.widget is f else None)

        def chercher():
            btn_chercher.configure(state="disabled")
            statut.configure(text=t("Recherche des caméras sur le réseau (une dizaine de secondes)…"))
            resultat = []

            def travail():
                try:
                    liste = cameras.chercher(arret=arret)
                    resultat.append((liste, cameras.appareils_tp_link({ip for ip, _o in liste})))
                except Exception as e:          # carte réseau étrange : la fenêtre ne reste pas bloquée
                    resultat.append(([], []))
                    journaliser_erreur(e)
            threading.Thread(target=travail, daemon=True).start()

            def attendre():
                if not f.winfo_exists():
                    return
                if not resultat:
                    f.after(300, attendre)
                    return
                btn_chercher.configure(state="normal")
                liste, fermees = resultat[0]
                trouvees.configure(values=[ip for ip, _o in liste] + fermees)
                if fermees and not liste:
                    statut.configure(text=t("Aucune caméra au flux ouvert. Appareil(s) TP-Link sans flux vidéo : "
                                            "{adresses} (la caméra si son « compte de la caméra » n'est pas créé, "
                                            "ou une prise, un répéteur…). Vérifiez l'adresse dans l'appli : Paramètres de "
                                            "l'appareil → Infos de l'appareil.", adresses=", ".join(fermees)))
                elif liste:
                    v_ip.set(liste[0][0])
                    tp = [ip for ip, o in liste if o]
                    statut.configure(text=tn("{n} caméra trouvée", "{n} caméras trouvées", len(liste)) +
                                     (t(" ; Mercusys ou Tapo probable : {adresses}", adresses=", ".join(tp)) if tp else ""))
                else:
                    statut.configure(text=t("Aucune caméra trouvée : vérifiez qu'elle est sur le même Wi-Fi, ou lisez son "
                                            "adresse IP dans l'appli (Paramètres de l'appareil → Infos de l'appareil)."))
            f.after(300, attendre)

        def tester():
            try:
                adresse = url()
            except ValueError as e:
                statut.configure(text=t("Impossible : {erreur}", erreur=e))
                return
            if self.surveillance:
                statut.configure(text=t("Arrêtez d'abord la surveillance : la caméra n'accepte que peu de connexions à la fois."))
                return
            statut.configure(text=t("Connexion à la caméra…"))
            btn_tester.configure(state="disabled")
            resultat = []

            def travail():
                try:
                    ip, ident, mdp, voie, port = cameras.lire_adresse(adresse)
                    if not any(cameras._ouvert(ip, port, 3.0) or time.sleep(1) for _ in range(3)):
                        resultat.append("ferme")
                        return
                    acces = "muet"
                    for _ in range(3):          # la caméra peut être occupée un instant (appli ouverte)
                        acces = cameras.verifier_acces(ip, port, voie, ident, mdp)
                        if acces != "muet":
                            break
                        time.sleep(1)
                    if acces == "introuvable":
                        resultat.append(acces)
                        return
                    camera, image = sources.ouvrir_source(adresse)
                    if camera is not None:
                        camera.release()
                    # « refusé » n'est annoncé que si la vraie connexion échoue aussi
                    resultat.append("refuse" if image is None and acces == "refuse" else image)
                except Exception as e:
                    resultat.append(None)
                    journaliser_erreur(e)
            threading.Thread(target=travail, daemon=True).start()

            def attendre():
                if not f.winfo_exists():
                    return
                if not resultat:
                    f.after(300, attendre)
                    return
                btn_tester.configure(state="normal")
                image = resultat[0]
                if image == "refuse":
                    courriel = "@" in v_id.get()
                    statut.configure(text=(
                        t("La caméra refuse cet identifiant et ce mot de passe. Une adresse e-mail est celle du compte "
                          "Mercusys : il faut le « compte de la caméra », créé à part dans l'appli (Paramètres avancés → "
                          "Compte de la caméra).") if courriel else
                        t("La caméra refuse cet identifiant et ce mot de passe. Utilisez ceux du « compte de la caméra » "
                          "(Paramètres avancés → Compte de la caméra dans l'appli), en respectant majuscules et minuscules.")))
                    return
                if image == "introuvable":
                    statut.configure(text=t("La caméra ne connaît pas ce chemin de flux : choisissez la marque Mercusys, "
                                            "ou vérifiez le chemin (stream1 / stream2)."))
                    return
                if isinstance(image, str):
                    camera = cameras.lire_adresse(adresse)
                    statut.configure(text=t("{adresse} ne répond pas sur le port vidéo ({port}) : le "
                                            "« compte de la caméra » n'est pas encore créé, ou ce n'est pas l'adresse de la "
                                            "caméra (vérifiez-la dans l'appli : Paramètres de l'appareil → Infos de l'appareil).",
                                            adresse=camera[0], port=camera[4]))
                    return
                if image is None:
                    statut.configure(text=t("Pas d'image : vérifiez l'adresse IP et le compte de la caméra (identifiant "
                                            "et mot de passe créés dans l'appli, pas ceux du compte Mercusys)."))
                    return
                h, w = image.shape[:2]
                petite = cv2.resize(image, (480, int(480 * h / w)))
                apercu.image = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(petite, cv2.COLOR_BGR2RGB)))
                apercu.configure(image=apercu.image, width=480, height=petite.shape[0])
                statut.configure(text=t("Image reçue : {largeur}×{hauteur}. Cliquez sur « Utiliser cette caméra ».", largeur=w, hauteur=h))
            f.after(300, attendre)

        def utiliser():
            try:
                adresse = url()
            except ValueError as e:
                messagebox.showerror(t("Caméra IP"), t("Impossible : {erreur}", erreur=e), parent=f)
                return
            if self.surveillance:
                messagebox.showinfo(t("Caméra IP"), t("Arrêtez d'abord la surveillance."), parent=f)
                return
            ancienne = cle_source(self.cfg.get("camera_ip") or "")
            if ancienne in self.cfg["zones"] and cle_source(adresse) not in self.cfg["zones"]:
                self.cfg["zones"][cle_source(adresse)] = self.cfg["zones"][ancienne]   # même caméra, nouveau mot de passe
            self.cfg["source"] = self.cfg["camera_ip"] = self._camera()["source"] = adresse
            self._ecrire_config()
            self._valeurs_sources()
            self.var_source.set(libelle_source(adresse))
            self.lbl_etat.configure(text=t("Caméra choisie : {camera}. Pensez à « Cadrer » si besoin.", camera=libelle_source(adresse)))
            f.destroy()

        btn_chercher.configure(command=chercher)
        bas = tk.Frame(f, bg=CARTE)
        bas.grid(row=9, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        btn_tester = ttk.Button(bas, text=t("Tester"), command=tester)
        btn_tester.pack(side="left")
        ttk.Button(bas, text=t("Utiliser cette caméra"), style="Vert.TButton", command=utiliser).pack(side="right")
        if not actuelle[0]:
            chercher()

    def _choisir_fichier(self):
        chemin = filedialog.askopenfilename(title=t("Analyser une vidéo"), filetypes=[(t("Vidéos"), "*.mp4 *.avi *.mov *.mkv")])
        if chemin:
            self.var_source.set(chemin)

    def _maj_reglages(self):
        self.cfg["seuil"] = round(self.var_seuil.get() / 100, 2)
        self.cfg["reconnaissance"] = self.var_reco.get()
        self.cfg["creer_nouvelles"] = self.var_nouvelles.get()
        self.lbl_seuil.configure(text=pourcent(self.cfg["seuil"]))
        for s in list(getattr(self, "surveillances", {}).values()):
            s.seuil, s.reconnaissance_active, s.creer_nouvelles = (self.cfg["seuil"], self.cfg["reconnaissance"],
                                                                   self.cfg["creer_nouvelles"])

    # -------------------------------------------------------------- réglages
    def reglages(self):
        f = tk.Toplevel(self.root, bg=CARTE, padx=20, pady=16)
        f.title(t("Réglages"))
        f.transient(self.root)
        f.columnconfigure(1, weight=1)
        langues = [("", t("Langue de Windows"))] + list(i18n.LANGUES.items())      # (code, nom affiché)
        langue_avant = self.cfg.get("langue") or ""
        v_langue = tk.StringVar(value=next((nom for code, nom in langues if code == langue_avant), langues[0][1]))

        def ligne(rangee, texte, variable, largeur=44):
            ttk.Label(f, text=texte, style="Carte.TLabel").grid(row=rangee, column=0, sticky="w", pady=5, padx=(0, 14))
            e = ttk.Entry(f, textvariable=variable, width=largeur)
            e.grid(row=rangee, column=1, sticky="ew")
            return e

        v_dossier = tk.StringVar(value=self.cfg["dossier"])
        ligne(0, t("Dossier des visites"), v_dossier)
        ttk.Button(f, text="…", width=3, command=lambda: v_dossier.set(filedialog.askdirectory(parent=f) or v_dossier.get())
                   ).grid(row=0, column=2, padx=(6, 0))
        v_alerte = tk.StringVar(value=str(self.cfg["alerte_jours"]))
        ligne(1, t("Signaler une tortue absente depuis (jours)"), v_alerte, 8)
        v_jours = tk.StringVar(value=str(self.cfg["menage_jours"]))
        ligne(2, t("Effacer les clips après (jours, 0 = jamais)"), v_jours, 8)
        v_go = tk.StringVar(value=str(self.cfg["menage_go"]))
        ligne(3, t("Taille maximale du dossier (Go, 0 = sans limite)"), v_go, 8)
        v_auto = tk.BooleanVar(value=self.cfg["demarrage_auto"])
        ttk.Checkbutton(f, text=t("Démarrer la surveillance à l'ouverture"), variable=v_auto).grid(row=4, column=0, columnspan=2, sticky="w", pady=6)
        v_windows = tk.BooleanVar(value=demarrage.est_active())
        ttk.Checkbutton(f, text=t("Lancer Broutille au démarrage de Windows (la surveillance démarre seule)"),
                        variable=v_windows).grid(row=5, column=0, columnspan=3, sticky="w", pady=6)
        conseille = demarrage.programme_conseille() if sources.est_fenetre(str(self.cfg["source"])) else ""
        v_avant = tk.StringVar(value=self.cfg["lancer_avant"] or conseille)
        ligne(6, t("Ouvrir d'abord ce programme (ex. EZVIZ Studio)"), v_avant)
        ttk.Button(f, text="…", width=3, command=lambda: v_avant.set(
            filedialog.askopenfilename(parent=f, filetypes=[(t("Programme ou raccourci"), "*.exe *.lnk")]) or v_avant.get())
                   ).grid(row=6, column=2, padx=(6, 0))
        ttk.Label(f, text=t("Laissez vide si la source n'est pas une fenêtre. Broutille attend la fenêtre jusqu'à 2 min."),
                  style="Discret.TLabel").grid(row=7, column=0, columnspan=3, sticky="w")
        v_sans_admin = tk.BooleanVar(value=self.cfg["sans_admin"])
        ttk.Checkbutton(f, text=t("L'ouvrir sans droits administrateur (nécessaire pour relancer le direct d'EZVIZ Studio)"),
                        variable=v_sans_admin).grid(row=8, column=0, columnspan=3, sticky="w", pady=(6, 0))
        v_relance = tk.BooleanVar(value=self.cfg["relance_auto"])
        ttk.Checkbutton(f, text=t("Image figée : relancer le direct en cliquant sur ce bouton du lecteur"),
                        variable=v_relance).grid(row=9, column=0, columnspan=2, sticky="w", pady=6)
        point = [self.cfg["relance_point"]]
        lbl_point = ttk.Label(f, style="Discret.TLabel", text=t("bouton appris ({x}, {y})", x=pourcent(point[0][0]), y=pourcent(point[0][1]))
                              if point[0] else t("aucun bouton appris"))
        lbl_point.grid(row=10, column=1, sticky="w")

        def apprendre():
            source = self._saisie_source()
            if not sources.est_fenetre(source):
                messagebox.showinfo(t("Bouton de relance"), t("La source doit être une fenêtre (🪟 Fenêtre)."), parent=f)
                return
            titre = source[len(sources.PREFIXE_FENETRE):]
            messagebox.showinfo(t("Bouton de relance"), t("Après OK : posez la souris sur le bouton de « {titre} » qui relance "
                                                          "le direct (ou sur la caméra dans sa liste), et ne bougez plus 3 secondes.",
                                                          titre=titre), parent=f)
            lbl_point.configure(text=t("En attente : souris immobile 3 s sur le bouton…"))

            resultat = []

            def travail():
                resultat.append(sources.apprendre_point(titre))

            def attendre():                 # interrogé depuis le fil de l'interface : Tk n'aime pas les autres fils
                if not f.winfo_exists():
                    return
                if not resultat:
                    f.after(200, attendre)
                    return
                trouve = resultat[0]
                if trouve:
                    point[0] = trouve
                    lbl_point.configure(text=t("bouton appris ({x}, {y})", x=pourcent(trouve[0]), y=pourcent(trouve[1])))
                    v_relance.set(True)
                else:
                    lbl_point.configure(text=t("pas de bouton appris : recommencez"))
            threading.Thread(target=travail, daemon=True).start()
            f.after(200, attendre)

        ttk.Button(f, text="📍  " + t("Montrer le bouton…"), command=apprendre).grid(row=10, column=0, sticky="w")
        v_sauvegarde = tk.StringVar(value=self.cfg["sauvegarde_dossier"])
        ligne(11, t("Sauvegarde quotidienne dans (clé USB, OneDrive…)"), v_sauvegarde)
        ttk.Button(f, text="…", width=3, command=lambda: v_sauvegarde.set(filedialog.askdirectory(parent=f) or v_sauvegarde.get())
                   ).grid(row=11, column=2, padx=(6, 0))
        v_pesee = tk.StringVar(value=str(self.cfg["rappel_pesee_jours"]))
        ligne(12, t("Rappeler de peser une tortue après (jours, 0 = jamais)"), v_pesee, 8)
        ttk.Label(f, text=t("Espèces présentes à la mangeoire (moins il y en a, moins Broutille se trompe)"),
                  style="Discret.TLabel").grid(row=13, column=0, columnspan=3, sticky="w", pady=(10, 4))
        cadre_especes = ttk.Frame(f, style="Carte.TFrame")
        cadre_especes.grid(row=14, column=0, columnspan=3, sticky="w")
        coches = {}
        for i, (nom, sci, _en) in enumerate(vision.ESPECES_DEFAUT):
            coches[sci] = tk.BooleanVar(value=sci in self.cfg["especes_actives"])
            ttk.Checkbutton(cadre_especes, text=t(nom), variable=coches[sci]).grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 18))
        ttk.Label(f, text=t("Langue"), style="Carte.TLabel").grid(row=15, column=0, sticky="w", pady=(10, 5), padx=(0, 14))
        ttk.Combobox(f, textvariable=v_langue, values=[nom for _code, nom in langues], state="readonly", width=28
                     ).grid(row=15, column=1, sticky="w", pady=(10, 5))

        def enregistrer():
            try:
                alerte, jours, go = int(v_alerte.get()), int(v_jours.get()), float(v_go.get())
                rappel = int(v_pesee.get())
                if not (0 <= alerte <= 3650 and 0 <= jours <= 3650 and 0 <= rappel <= 3650 and 0 <= go <= 100000):
                    raise ValueError
            except ValueError:
                messagebox.showerror(t("Réglages"), t("Jours : de 0 à 3650. Taille : de 0 à 100000 Go (0 = sans limite)."),
                                     parent=f)
                return
            actives = [s for s, c in coches.items() if c.get()]
            if len(actives) < 2:
                messagebox.showerror(t("Réglages"), t("Cochez au moins deux espèces."), parent=f)
                return
            nouveau_dossier = v_dossier.get() != self.cfg["dossier"]
            if nouveau_dossier and self.surveillances:
                messagebox.showerror(t("Réglages"), t("Arrêtez la surveillance avant de changer de dossier."), parent=f)
                return
            if nouveau_dossier:
                for fenetre in list(self.fenetres_fiche.values()):
                    if fenetre.winfo_exists() and hasattr(fenetre, "fermer"):
                        fenetre.fermer()
                        if fenetre.winfo_exists():     # « Annuler » : on reste sur l'ancien dossier
                            return
            change = actives != self.cfg["especes_actives"]
            langue = next((code for code, nom in langues if nom == v_langue.get()), langue_avant)
            if v_relance.get() and not point[0]:
                messagebox.showerror(t("Réglages"), t("Montrez d'abord le bouton de relance (📍)."), parent=f)
                return
            try:
                demarrage.activer() if v_windows.get() else demarrage.desactiver()
            except OSError as e:
                messagebox.showerror(t("Réglages"), t("Démarrage avec Windows impossible : {erreur}", erreur=e), parent=f)
                return
            self.cfg.update(dossier=v_dossier.get(), alerte_jours=alerte, menage_jours=jours, menage_go=go,
                            demarrage_auto=v_auto.get(), especes_actives=actives, lancer_avant=v_avant.get().strip(),
                            sans_admin=v_sans_admin.get(), relance_auto=v_relance.get(), relance_point=point[0],
                            sauvegarde_dossier=v_sauvegarde.get().strip(), rappel_pesee_jours=max(0, rappel), langue=langue)
            self._ecrire_config()
            self._sauvegarde_maintenant()
            f.destroy()
            if langue != langue_avant:
                messagebox.showinfo(t("Réglages"), t("La nouvelle langue s'appliquera au prochain démarrage de Broutille."))
            if nouveau_dossier:
                for cle in list(self.fenetres_fiche):
                    self._fermer_fiche(cle)
                self.registre = Registre(self.dossier, self.registre.descripteur)
                threading.Thread(target=self._precharger, daemon=True).start()
                if self.serveur_web:            # le serveur du téléphone tenait l'ancien registre
                    self._web(True)
                self._maj_alertes()
            if change:
                self.lbl_etat.configure(text=t("Réglage enregistré : relancez Broutille pour l'appliquer"))
            self.charger_historique()

        def oublier():
            if messagebox.askyesno(t("Pas une tortue"), t("Oublier tous les « Pas une tortue » ?"), parent=f):
                self.registre.oublier_rejets()
                btn_rejets.configure(text=t("Oublier les « Pas une tortue » ({n})", n=0), state="disabled")

        n_rejets = self.registre.nombre_rejets()
        btn_rejets = ttk.Button(f, text=t("Oublier les « Pas une tortue » ({n})", n=n_rejets), command=oublier,
                                state="normal" if n_rejets else "disabled")
        btn_rejets.grid(row=16, column=0, sticky="w", pady=(14, 0))

        ttk.Button(f, text=t("Enregistrer"), style="Vert.TButton", command=enregistrer).grid(row=16, column=1, columnspan=2, sticky="e", pady=(14, 0))

    # -------------------------------------------------------------- surveillance
    @property
    def surveillance(self):
        """Surveillance de la caméra affichée (None si elle est arrêtée)."""
        return self.surveillances.get(self.cfg["camera_courante"])

    def _camera(self, ident=None):
        ident = ident or self.cfg["camera_courante"]
        return next((c for c in self.cfg["cameras"] if c["id"] == ident), None)

    def _maj_cameras(self):
        """Pastilles des caméras : vert = surveillée, rouge = tortue à table, ambre = image figée."""
        etat = tuple((c["id"], c["nom"], c["id"] in self.surveillances, self.presence.get(c["id"], 0),
                      bool(self.figee.get(c["id"])), c["id"] == self.cfg["camera_courante"]) for c in self.cfg["cameras"])
        if etat == self.etat_pastilles:
            return
        self.etat_pastilles = etat
        for w in self.barre_cameras.winfo_children():
            w.destroy()
        tk.Label(self.barre_cameras, text=t("Caméras"), bg=FOND, fg=DISCRET).pack(side="left", padx=(0, 10))
        for ident, nom, active, n, figee, courante in etat:
            couleur = AMBRE if figee else ROUGE if n else VERT if active else DISCRET
            texte = f"●  {nom}" + (f"   {n} 🐢" if n else "") + ("   " + t("figée") if figee else "" if active else "   " + t("arrêtée"))
            b = tk.Label(self.barre_cameras, text=texte, bg=BORD if courante else CARTE, fg=couleur,
                         font=PT(10, True), padx=12, pady=5, cursor="hand2")
            b.pack(side="left", padx=(0, 6))
            b.bind("<Button-1>", lambda _e, i=ident: self.choisir_camera(i))
            b.bind("<Button-3>", lambda e, i=ident: self._menu_camera(e, i))
        plus = tk.Label(self.barre_cameras, text="＋  " + t("Caméra"), bg=FOND, fg=VERT, font=PT(10, True),
                        padx=8, pady=5, cursor="hand2")
        plus.pack(side="left")
        plus.bind("<Button-1>", lambda _e: self.ajouter_camera())
        if len(etat) > 1:
            toutes = any(not a for _i, _n, a, *_r in etat)
            lien = tk.Label(self.barre_cameras, text="▶▶  " + t("Démarrer toutes") if toutes else "■  " + t("Arrêter toutes"),
                            bg=FOND, fg=VERT if toutes else ROUGE, font=PT(10, True), padx=12, pady=5, cursor="hand2")
            lien.pack(side="left", padx=(12, 0))
            lien.bind("<Button-1>", lambda _e: self.tout_demarrer() if toutes else self.tout_arreter())
        tk.Label(self.barre_cameras, text=t("clic droit sur une caméra : la renommer ou la retirer"), bg=FOND, fg=DISCRET,
                 font=PT(9)).pack(side="right")
        if hasattr(self, "btn_demarrer"):
            en_cours = self.surveillance is not None
            if str(self.btn_demarrer.cget("state")) != "disabled" or not en_cours:
                self.btn_demarrer.configure(text="■  " + t("Arrêter") if en_cours else "▶  " + t("Démarrer"),
                                            style="Rouge.TButton" if en_cours else "Vert.TButton", state="normal")

    def choisir_camera(self, ident):
        """Affiche une autre caméra ; la source tapée pour l'ancienne (arrêtée) lui reste."""
        if ident == self.cfg["camera_courante"] or not self._camera(ident):
            return
        if self.surveillance is None:
            self._camera()["source"] = self._saisie_source()
        self.cfg["camera_courante"] = ident
        self.cfg["source"] = self._camera()["source"]
        self._ecrire_config()
        self._valeurs_sources()
        self.var_source.set(libelle_source(self.cfg["source"]))
        self.image_affichee = None
        self._maj_cameras()
        if self.surveillance is None:
            self._afficher_vide()
            self.pastille.configure(text="●  " + t("En veille"), fg=DISCRET)

    def ajouter_camera(self):
        nom = self._demander_nom(t("Nouvelle caméra"), t("Caméra {n}", n=len(self.cfg["cameras"]) + 1))
        if not nom:
            return
        ident = f"c{int(time.time() * 1000):x}"
        self.cfg["cameras"].append({"id": ident, "nom": nom, "source": "0"})
        self.choisir_camera(ident)
        self.lbl_etat.configure(text=t("« {nom} » ajoutée : choisissez sa source (📷 Caméra IP, 🪟 Fenêtre…), puis Démarrer", nom=nom))

    def _demander_nom(self, titre, nom=""):
        f = tk.Toplevel(self.root, bg=CARTE, padx=20, pady=16)
        f.title(titre)
        f.transient(self.root)
        f.grab_set()
        v = tk.StringVar(value=nom)
        resultat = []
        ttk.Label(f, text=t("Nom (ex. Mangeoire, Abri, Bassin)"), style="Carte.TLabel").grid(row=0, column=0, sticky="w")
        e = ttk.Entry(f, textvariable=v, width=30)
        e.grid(row=1, column=0, pady=(4, 10))
        e.focus_set()
        e.select_range(0, "end")

        def valider(_=None):
            if v.get().strip():
                resultat.append(v.get().strip()[:40])
                f.destroy()

        f.bind("<Return>", valider)
        ttk.Button(f, text=t("Valider"), style="Vert.TButton", command=valider).grid(row=2, column=0, sticky="e")
        self.root.wait_window(f)
        return resultat[0] if resultat else None

    def _menu_camera(self, ev, ident):
        cam = self._camera(ident)
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=f"{cam['nom']} — {libelle_source(cam['source'])}", state="disabled")
        menu.add_command(label=t("Renommer…"), command=lambda: self._renommer_camera(ident))
        etat = "normal" if len(self.cfg["cameras"]) > 1 and ident not in self.surveillances else "disabled"
        menu.add_command(label=t("Retirer cette caméra…"), command=lambda: self._retirer_camera(ident), state=etat)
        menu.tk_popup(ev.x_root, ev.y_root)

    def _renommer_camera(self, ident):
        cam = self._camera(ident)
        nom = self._demander_nom(t("Renommer la caméra"), cam["nom"])
        if nom:
            cam["nom"] = nom
            if ident in self.surveillances:
                self.surveillances[ident].camera = nom
            self._ecrire_config()
            self._maj_cameras()

    def _retirer_camera(self, ident):
        cam = self._camera(ident)
        if ident in self.surveillances or len(self.cfg["cameras"]) < 2:
            return
        if messagebox.askyesno(t("Caméras"), t("Retirer la caméra « {nom} » ? Ses visites restent au journal.", nom=cam["nom"])):
            self.cfg["cameras"] = [c for c in self.cfg["cameras"] if c["id"] != ident]
            if ident == self.cfg["camera_courante"]:
                self.cfg["camera_courante"] = ""
                self.choisir_camera(self.cfg["cameras"][0]["id"])
            self._ecrire_config()
            self.etat_pastilles = None
            self._maj_cameras()

    def tout_demarrer(self, insister=False):
        if self.surveillance is None:
            self._camera()["source"] = self._saisie_source()
        for c in list(self.cfg["cameras"]):
            if c["id"] not in self.surveillances:
                self.demarrer(c["id"], insister)

    def tout_arreter(self):
        for ident in list(self.surveillances):
            self.arreter(ident)

    def basculer(self):
        self.arreter() if self.surveillance else self.demarrer()

    def demarrer(self, ident=None, insister=False):
        ident = ident or self.cfg["camera_courante"]
        cam = self._camera(ident)
        if cam is None or ident in self.surveillances:
            return
        if ident == self.cfg["camera_courante"]:
            cam["source"] = self._saisie_source()
            self.cfg["source"] = cam["source"]
        source = cam["source"]
        if any(c["source"] == source and c["id"] in self.surveillances for c in self.cfg["cameras"]):
            self.lbl_etat.configure(text=t("Cette source est déjà surveillée par une autre caméra : {source}", source=libelle_source(source)))
            return
        self._ecrire_config()
        s = Surveillance(
            source, self.dossier, registre=self.registre, detecteur=self.detecteur, classeur=self.classeur,
            seuil=self.cfg["seuil"], marge=MARGE_INDIVIDU, reconnaissance=self.cfg["reconnaissance"],
            creer_nouvelles=self.cfg["creer_nouvelles"], menage_jours=self.cfg["menage_jours"],
            menage_go=self.cfg["menage_go"], temps_reel=True, zone=self.cfg["zones"].get(cle_source(source)),
            sur_image=lambda image, etat, i=ident: self._sur_image(i, image, etat),
            sur_visite=lambda l: self.messages.put(("visite", l)),
            sur_message=lambda m, nom=cam["nom"]: self.messages.put(("message", f"{nom} : {m}" if len(self.cfg["cameras"]) > 1 else m)),
            sur_figee=lambda f, i=ident: self.messages.put(("figee", (i, f))))
        s.insister = insister
        s.camera, s.camera_id = cam["nom"], ident
        self.surveillances[ident] = s
        threading.Thread(target=self._executer, args=(s, ident), daemon=True).start()
        self._maj_cameras()

    def _executer(self, surveillance, ident):
        try:
            ok = surveillance.executer()
        except Exception as e:
            self.messages.put(("message", t("Erreur : {type} : {erreur}", type=type(e).__name__, erreur=e)))
            ok = False
        self.messages.put(("fin", (ident, ok)))

    def arreter(self, ident=None):
        ident = ident or self.cfg["camera_courante"]
        s = self.surveillances.get(ident)
        if s:
            if ident == self.cfg["camera_courante"]:
                self.btn_demarrer.configure(state="disabled", text=t("Arrêt…"))
            s.arreter()

    def _sur_image(self, ident, image, etat):
        with self.verrou:
            self.derniere_image[ident] = (image, etat)
            self.image_web[ident] = (image, etat)      # lue par le serveur du téléphone, sans la consommer
            self.presence[ident] = etat["presence"]

    def _image_web(self):
        """Image du téléphone : la caméra affichée si elle tourne, sinon une autre qui tourne."""
        with self.verrou:
            for ident in [self.cfg["camera_courante"]] + list(self.surveillances):
                if ident in self.surveillances and ident in self.image_web:
                    return self.image_web[ident]
        return None

    def _boucle(self):
        if self.fermeture and not self._tk_vivant():
            return
        if self.diffusion is not None and not self.diffusion.winfo_exists():
            self._quitter_diffusion()           # fermée par Alt+F4 : retour à l'affichage normal
        try:
            self._traiter_messages()
            if not self._tk_vivant():       # fenêtre détruite pendant les messages (fin de surveillance en quittant)
                return
            if datetime.now().date() != self.jour_stats:
                self.jour_stats = datetime.now().date()
                self._maj_stats()           # minuit : « aujourd'hui » repart de zéro, au direct aussi
            with self.verrou:
                donnees = self.derniere_image.pop(self.cfg["camera_courante"], None)
                n = sum(v for k, v in self.presence.items() if k in self.surveillances)
            if donnees and self.surveillance:
                image, etat = donnees
                if self.diffusion is not None:      # plein écran : la fenêtre principale est cachée dessous
                    self._afficher_diffusion(image, etat)
                else:
                    self._afficher_image(image, etat)
            if self.surveillances:                  # toutes caméras confondues
                self.pastille.configure(text="●  " + (tn("{n} tortue à table", "{n} tortues à table", n) if n else t("Surveillance")),
                                        fg=ROUGE if n else VERT)
            self._maj_cameras()
        except Exception as e:      # une erreur d'affichage ne doit pas figer l'interface pour la session
            journaliser_erreur(e)
            self.lbl_etat.configure(text=t("Erreur d'affichage : {type}", type=type(e).__name__))
        finally:
            if self._tk_vivant():
                self.root.after(30, self._boucle)

    def _tk_vivant(self):
        try:
            return bool(self.root.winfo_exists())
        except tk.TclError:
            return False

    def _traiter_messages(self):
        while not self.messages.empty():
            genre, contenu = self.messages.get()
            if genre == "message":
                self.lbl_etat.configure(text=contenu)
            elif genre == "modele":
                self.lbl_modele.configure(text=t("Modèles prêts ({appareil})", appareil=contenu))
                self.lbl_etat.configure(text=t("Prêt"))
            elif genre == "erreur_modele":
                self.lbl_modele.configure(text=t("Modèles indisponibles"), fg=ROUGE)
                self.lbl_etat.configure(text=contenu)
            elif genre == "tortues":
                self._maj_tortues()
            elif genre == "figee":
                ident, figee = contenu
                self.figee[ident] = figee
                self.relance_serie[ident] = serie = self.relance_serie.get(ident, 0) + 1   # une série à la fois
                if figee:
                    self.root.bell()
                    self.root.after(3000, lambda i=ident, s_=serie: self._relancer_direct(1, s_, i))
                    # toujours figée 5 min plus tard (relance ratée) : prévenir le téléphone
                    self.root.after(300000, lambda i=ident, s_=serie: self._alerte_figee(s_, i))
            elif genre == "sauvegarde":
                self.lbl_etat.configure(text=contenu)
            elif genre == "visite":
                self._ajouter_visite(contenu, True)
                self._afficher_visite(contenu)
                self._maj_stats()
                self._maj_tortues()
                self._clip_auto(contenu)
            elif genre == "corrige":
                self.charger_historique()
                self.lbl_etat.configure(text=contenu)
            elif genre == "cadrage":
                self._fenetre_cadrage(*contenu)
            elif genre == "fin":
                ident, contenu = contenu
                self.surveillances.pop(ident, None)
                if self.fermeture:
                    if not self.surveillances:  # chaque caméra a fini son clip et sa dernière visite
                        self.root.destroy()
                        return
                    continue
                cam = self._camera(ident) or {"nom": ""}
                if not contenu and self.alertes:
                    self.alertes.en_fond(self.alertes.signaler, f"arret:{ident}:{time.time():.0f}",
                                         t("Surveillance arrêtée : {camera}", camera=cam["nom"]) if len(self.cfg["cameras"]) > 1 else
                                         t("Surveillance arrêtée"),
                                         # texte fixe : le message d'erreur peut contenir chemins et nom d'utilisateur
                                         t("La surveillance s'est arrêtée sur une erreur : voir le PC."), 4,
                                         ("warning", "video_camera"))
                if not contenu and self.diffusion is None:     # pas de boîte d'erreur en plein direct
                    messagebox.showerror(t("Source vidéo"), self.lbl_etat.cget("text"))
                with self.verrou:
                    self.derniere_image.pop(ident, None)
                    self.image_web.pop(ident, None)
                    self.presence.pop(ident, None)
                self.figee[ident] = False        # la prochaine surveillance repart d'une image vivante
                self.relance_serie[ident] = self.relance_serie.get(ident, 0) + 1
                if ident == self.cfg["camera_courante"]:
                    self.btn_demarrer.configure(text="▶  " + t("Démarrer"), style="Vert.TButton", state="normal")
                    self._afficher_vide()
                if not self.surveillances:
                    self.pastille.configure(text="●  " + t("En veille"), fg=DISCRET)
                self._maj_cameras()

    # -------------------------------------------------------------- sources
    def choisir_fenetre(self):
        f = tk.Toplevel(self.root, bg=CARTE, padx=16, pady=14)
        f.title(t("Filmer une fenêtre ouverte"))
        f.transient(self.root)
        ttk.Label(f, text=t("La fenêtre doit rester ouverte, pas réduite.\nElle peut être cachée par d'autres : Broutille y trouve seul la vidéo."),
                  style="Discret.TLabel").pack(anchor="w", pady=(0, 8))
        liste = tk.Listbox(f, width=64, height=12, bg=FOND, fg=TEXTE, selectbackground=VERT, relief="flat", font=PT(10))
        liste.pack(fill="both", expand=True)
        titres = sorted({ti for ti, _h in sources.lister_fenetres() if ti not in (self.root.title(), f.title())})
        for titre in titres:
            liste.insert("end", titre)

        def valider(_=None):
            if liste.curselection():
                self.var_source.set(libelle_source(sources.PREFIXE_FENETRE + titres[liste.curselection()[0]]))
                f.destroy()

        liste.bind("<Double-1>", valider)
        ttk.Button(f, text=t("Choisir"), style="Vert.TButton", command=valider).pack(anchor="e", pady=(10, 0))

    def cadrer(self):
        """Une fenêtre comme EZVIZ Studio a des boutons et parfois plusieurs caméras : on garde une zone."""
        if self.surveillance:
            messagebox.showinfo(t("Cadrer"), t("Arrêtez d'abord la surveillance."))
            return
        source = sources.source_depuis_texte(self._saisie_source())

        def travail():
            camera, image = sources.ouvrir_source(source)
            if camera is not None:
                camera.release()
                self.messages.put(("cadrage", (cle_source(source), image)))
            else:
                self.messages.put(("message", t("Aucune image de : {source}", source=sources.masquer(source))))

        self.lbl_etat.configure(text=t("Lecture de la source…"))
        threading.Thread(target=travail, daemon=True).start()

    def _fenetre_cadrage(self, cle, image):
        h, w = image.shape[:2]
        e = min(1100 / w, 700 / h, 1.0)
        f = tk.Toplevel(self.root, bg=CARTE, padx=12, pady=12)
        f.title(t("Cadrer : tracez la zone de la mangeoire à la souris"))
        f.transient(self.root)
        photo = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(cv2.resize(image, (int(w * e), int(h * e))), cv2.COLOR_BGR2RGB)))
        c = tk.Canvas(f, width=int(w * e), height=int(h * e), highlightthickness=0)
        c.pack()
        c.create_image(0, 0, anchor="nw", image=photo)
        c.image = photo
        zone = self.cfg["zones"].get(cle) or [0, 0, 1, 1]
        cadre = c.create_rectangle(*(v * d for v, d in zip(zone, (w * e, h * e, w * e, h * e))), outline=AMBRE, width=3)
        depart = [0, 0]

        def appui(ev):
            depart[:] = [ev.x, ev.y]

        def glisse(ev):
            c.coords(cadre, depart[0], depart[1], ev.x, ev.y)

        c.bind("<ButtonPress-1>", appui)
        c.bind("<B1-Motion>", glisse)

        def retenir(nouvelle):
            self.cfg["zones"][cle] = nouvelle
            self.cfg["zones"] = {k: v for k, v in self.cfg["zones"].items() if v}
            self._ecrire_config()
            self.lbl_etat.configure(text=t("Cadrage enregistré pour cette source"))
            f.destroy()

        def valider():
            x0, y0, x1, y1 = c.coords(cadre)
            x0, x1 = sorted((max(0, x0), min(w * e, x1)))
            y0, y1 = sorted((max(0, y0), min(h * e, y1)))
            if x1 - x0 < 64 or y1 - y0 < 64:
                messagebox.showerror(t("Cadrer"), t("Zone trop petite."), parent=f)
                return
            retenir([x0 / (w * e), y0 / (h * e), x1 / (w * e), y1 / (h * e)])

        bas = tk.Frame(f, bg=CARTE)
        bas.pack(fill="x", pady=(10, 0))
        ttk.Button(bas, text=t("Toute l'image"), command=lambda: retenir(None)).pack(side="left")
        ttk.Button(bas, text=t("Valider la zone"), style="Vert.TButton", command=valider).pack(side="right")

    def _afficher_image(self, image, etat):
        lw, lh = max(self.video.winfo_width(), 320), max(self.video.winfo_height(), 240)
        h, w = image.shape[:2]
        e = min(lw / w, lh / h)
        nw, nh = int(w * e), int(h * e)
        # dessin direct sur l'image RGB, transparences mélangées par ImageDraw : ni calque ni
        # composition à chaque image (deux copies plein cadre en moins, 30 fois par seconde)
        img = Image.fromarray(cv2.cvtColor(cv2.resize(image, (nw, nh), interpolation=cv2.INTER_LINEAR), cv2.COLOR_BGR2RGB))
        d = ImageDraw.Draw(img, "RGBA")
        # le Label centre l'image : décalage pour retrouver la tortue sous un clic
        ox, oy = (self.video.winfo_width() - nw) // 2, (self.video.winfo_height() - nh) // 2
        self.zones_video = []
        pistes = etat["pistes"] if "pistes" in etat else [(None, b, nm, True, None) for b, nm in etat["tortues"]]
        for numero, boite, texte, sure, *reste in pistes:
            cle = reste[0] if reste else None
            x, y, bw, bh = (int(v * e) for v in boite)
            if sure:
                d.rounded_rectangle([x, y, x + bw, y + bh], radius=10, outline=(217, 164, 65, 255), width=4)
            else:                       # pas encore confirmée : cadre fin, nommable d'un clic
                d.rounded_rectangle([x, y, x + bw, y + bh], radius=10, outline=(151, 163, 141, 200), width=2)
                texte = f"{texte} ?" if not texte.endswith("?") else texte
            tw = d.textlength(texte, font=self.f_tag)
            yt = max(0, y - 40)
            d.rounded_rectangle([x, yt, x + tw + 24, yt + 36], radius=10, fill=(16, 20, 15, 215))
            d.text((x + 12, yt + 4), texte, font=self.f_tag, fill=(233, 238, 227, 255 if sure else 170))
            if numero is not None:      # cadre et étiquette cliquables
                self.zones_video.append((ox + x, oy + yt, ox + max(x + bw, x + tw + 24), oy + y + bh, numero, texte,
                                         cle, sure and not texte.endswith("?")))
        if self.zones_video:
            d.text((16, nh - 30), t("Clic sur une tortue : sa fiche, ou la nommer  ·  clic droit : changer son nom"),
                   font=self.f_petit, fill=(200, 210, 200, 170))
        if etat["enregistrement"]:
            d.rounded_rectangle([16, 16, 150, 52], radius=18, fill=(248, 81, 73, 230))
            d.ellipse([28, 28, 40, 40], fill="white")
            d.text((50, 22), t("REC") + f" {int(etat['duree']) // 60:02d}:{int(etat['duree']) % 60:02d}", font=self.f_petit, fill="white")
        d.text((nw - 90, 20), t("{v} i/s", v=f"{etat['fps']:.0f}"), font=self.f_petit, fill=(200, 210, 200, 200))
        if etat.get("figee_s"):
            texte = t("IMAGE FIGÉE depuis {n} min — relancez le direct dans le lecteur", n=int(etat["figee_s"] // 60))
            tw = d.textlength(texte, font=self.f_petit)
            d.rounded_rectangle([(nw - tw) / 2 - 18, nh - 62, (nw + tw) / 2 + 18, nh - 18], radius=14, fill=(248, 81, 73, 235))
            d.text(((nw - tw) / 2, nh - 54), texte, font=self.f_petit, fill="white")
        if isinstance(self.image_affichee, ImageTk.PhotoImage) and self.image_affichee.width() == nw                 and self.image_affichee.height() == nh and self.video.cget("image") == str(self.image_affichee):
            self.image_affichee.paste(img)      # même taille : on réutilise l'image Tk, sans en recréer une
        else:
            self.image_affichee = ImageTk.PhotoImage(img)
            self.video.configure(image=self.image_affichee)

    def _afficher_vide(self):
        lw, lh = max(self.video.winfo_width(), 320), max(self.video.winfo_height(), 240)
        img = Image.new("RGB", (lw, lh), (7, 10, 6))
        d = ImageDraw.Draw(img)
        try:
            logo = Image.open(ICI / "broutille.png").convert("RGBA").resize((128, 128), Image.LANCZOS)
            img.paste(logo, ((lw - 128) // 2, lh // 2 - 150), logo)
        except OSError:
            pass
        texte = t("Cliquez sur « Démarrer » pour surveiller la mangeoire")
        d.text(((lw - d.textlength(texte, font=self.f_vide)) / 2, lh / 2 + 10), texte, font=self.f_vide, fill=(151, 163, 141))
        self.image_affichee = ImageTk.PhotoImage(img)
        self.video.configure(image=self.image_affichee)

    # -------------------------------------------------------------- téléphone
    def _web(self, actif, silencieux=False):
        """Lance ou arrête le serveur du téléphone ; renvoie True s'il tourne."""
        if self.serveur_web:
            self.serveur_web.arreter()
            self.serveur_web = None
        if actif:
            if not self.cfg["web_code"]:
                self.cfg["web_code"] = web.nouveau_code()
            if not self.cfg.get("web_secret"):
                self.cfg["web_secret"] = secrets.token_hex(32)
            # port retenu d'une fois sur l'autre (l'adresse enregistrée sur le téléphone reste bonne) ;
            # s'il est pris par un autre programme, on essaie les suivants
            prefere = self.cfg.get("web_port") or web.PORT
            for port in [prefere] + [p for p in range(web.PORT, web.PORT + 10) if p != prefere]:
                try:
                    self.serveur_web = web.Serveur(self.registre, lambda: self.dossier,
                                                   self._image_web,
                                                   self.cfg["web_code"], port=port, secret=self.cfg["web_secret"],
                                                   apres_modif=lambda: self.messages.put(("tortues", None))).demarrer()
                    self.cfg["web_port"] = port
                    break
                except OSError:
                    continue
            if self.serveur_web is None:
                if not silencieux:
                    messagebox.showerror(t("Téléphone"), t("Accès impossible : les ports {debut} à {fin} sont pris.", debut=web.PORT, fin=web.PORT + 9))
                self.lbl_etat.configure(text=t("Accès téléphone impossible : ports occupés"))
                if silencieux:              # au démarrage : le réglage reste, on réessaiera au prochain lancement
                    return False
                actif = False
        self.cfg["web_actif"] = actif
        self._ecrire_config()
        return actif

    def telephone(self):
        """Fenêtre du téléphone : marche/arrêt, QR code à scanner, adresse et code."""
        f = tk.Toplevel(self.root, bg=CARTE, padx=22, pady=18)
        f.title(t("Voir Broutille sur le téléphone"))
        f.transient(self.root)
        f.resizable(False, False)
        gauche = tk.Frame(f, bg=CARTE)
        gauche.pack(side="left", anchor="n")
        tk.Frame(f, bg=BORD, width=1).pack(side="left", fill="y", padx=22)
        droite = tk.Frame(f, bg=CARTE)
        droite.pack(side="left", anchor="n")
        v_actif = tk.BooleanVar(value=self.serveur_web is not None)
        ttk.Checkbutton(gauche, text=t("Accès depuis le téléphone (Wi-Fi de la maison)"), variable=v_actif,
                        command=lambda: (self._web(v_actif.get()), montrer())).pack(anchor="w")
        qr = tk.Label(gauche, bg=CARTE)
        qr.pack(pady=(14, 8))
        lbl_url = tk.Label(gauche, bg=CARTE, fg=TEXTE, font=PT(13, True))
        lbl_url.pack()
        lbl_code = tk.Label(gauche, bg=CARTE, fg=AMBRE, font=PT(13, True))
        lbl_code.pack(pady=(4, 0))
        ttk.Label(gauche, style="Discret.TLabel", justify="left", wraplength=420, text=t(
            "Scannez le QR code avec l'appareil photo du téléphone, branché sur le même Wi-Fi que ce PC. "
            "Ensuite, ajoutez la page à l'écran d'accueil.\n\n"
            "Au premier lancement, Windows demande d'autoriser Python : cochez « Réseaux privés ».\n"
            "La page n'est pas visible depuis Internet.")).pack(anchor="w", pady=(12, 0))
        bas = tk.Frame(gauche, bg=CARTE)
        bas.pack(fill="x", pady=(14, 0))

        def nouveau():
            if messagebox.askyesno(t("Téléphone"), t("Changer le code ? Les téléphones déjà connectés devront rescanner."), parent=f):
                self.cfg["web_code"] = web.nouveau_code()
                self._web(True)
                montrer()

        btn_code = ttk.Button(bas, text=t("Nouveau code"), command=nouveau)
        btn_code.pack(side="left")
        ttk.Button(bas, text=t("Fermer"), command=f.destroy).pack(side="right")

        # --- alertes : marchent aussi hors de la maison, par l'appli gratuite ntfy
        v_ntfy = tk.BooleanVar(value=bool(self.alertes))
        v_clips = tk.BooleanVar(value=self.cfg["clips_auto"])

        def basculer_ntfy():
            if v_ntfy.get() and not self.cfg["ntfy_sujet"]:
                self.cfg["ntfy_sujet"] = alertes.nouveau_sujet()
            self.cfg["ntfy_actif"] = v_ntfy.get()
            self._ecrire_config()
            self._maj_alertes()
            montrer_ntfy()

        ttk.Checkbutton(droite, text=t("Alertes sur le téléphone (appli ntfy)"), variable=v_ntfy,
                        command=basculer_ntfy).pack(anchor="w")
        qr_ntfy = tk.Label(droite, bg=CARTE)
        qr_ntfy.pack(pady=(14, 8))
        lbl_sujet = tk.Label(droite, bg=CARTE, fg=AMBRE, font=PT(11, True), wraplength=380)
        lbl_sujet.pack()
        ttk.Label(droite, style="Discret.TLabel", justify="left", wraplength=380, text=t(
            "1. Installez l'appli gratuite « ntfy » (Play Store ou App Store).\n"
            "2. Touchez « + », puis collez le nom du sujet ci-dessus, ou scannez le QR code.\n\n"
            "Vous serez prévenu, même loin de la maison : tortue absente depuis "
            "{n} jours, perte de poids, image figée, surveillance arrêtée.\n"
            "Les alertes passent par le service public ntfy.sh ; le nom du sujet, tiré au hasard, "
            "est la seule clé : ne le partagez pas.", n=self.cfg["alerte_jours"])).pack(anchor="w", pady=(10, 0))
        bas_ntfy = tk.Frame(droite, bg=CARTE)
        bas_ntfy.pack(fill="x", pady=(12, 0))

        def tester():
            a = self.alertes
            if not a:
                return

            def travail():
                try:
                    alertes.envoyer(a.serveur, a.sujet, "Broutille", t("Test : les alertes arrivent bien sur ce téléphone."))
                    self.messages.put(("message", t("Alerte de test envoyée")))
                except OSError as e:
                    self.messages.put(("message", t("Alerte de test impossible : {erreur}", erreur=e)))
            threading.Thread(target=travail, daemon=True).start()

        btn_test = ttk.Button(bas_ntfy, text=t("Envoyer un test"), command=tester)
        btn_test.pack(side="left")
        ttk.Separator(droite).pack(fill="x", pady=14)
        ttk.Checkbutton(droite, text="🎬 " + t("Clip vertical (Shorts, Reels) après chaque visite d'une tortue reconnue"),
                        variable=v_clips, command=lambda: (self.cfg.update(clips_auto=v_clips.get()),
                                                           self._ecrire_config())).pack(anchor="w")
        ttk.Label(droite, style="Discret.TLabel", wraplength=380, text=t(
            "Un clip par tortue toutes les 3 h au plus, dans le dossier « partage / clips » et sur la page du "
            "téléphone. Clic droit sur une visite pour en faire un à la demande.")).pack(anchor="w", pady=(4, 0))

        def montrer_ntfy():
            if not self.alertes:
                qr_ntfy.configure(image="", text=t("Alertes désactivées"), fg=DISCRET, font=PT(11), width=30, height=10)
                lbl_sujet.configure(text="")
                btn_test.configure(state="disabled")
                return
            btn_test.configure(state="normal")
            adresse = alertes.adresse_abonnement(self.cfg["ntfy_serveur"], self.cfg["ntfy_sujet"])
            try:
                import io
                import segno
                tampon = io.BytesIO()
                segno.make(adresse, error="m").save(tampon, kind="png", scale=6, border=2, dark="#10140f", light="#ffffff")
                tampon.seek(0)
                qr_ntfy.image = ImageTk.PhotoImage(Image.open(tampon))
                qr_ntfy.configure(image=qr_ntfy.image, text="", width=0, height=0)
            except ImportError:
                qr_ntfy.configure(image="", text="", width=0, height=0)
            lbl_sujet.configure(text=t("Sujet : {sujet}", sujet=self.cfg["ntfy_sujet"]))

        montrer_ntfy()

        def montrer():
            s = self.serveur_web
            v_actif.set(s is not None)
            if s is None:
                qr.configure(image="", text=t("Accès désactivé"), fg=DISCRET, font=PT(11), width=30, height=10)
                lbl_url.configure(text="")
                lbl_code.configure(text="")
                btn_code.configure(state="disabled")
                return
            btn_code.configure(state="normal")
            try:
                import io
                import segno
                tampon = io.BytesIO()
                segno.make(s.url(), error="m").save(tampon, kind="png", scale=8, border=2, dark="#10140f", light="#ffffff")
                tampon.seek(0)
                qr.image = ImageTk.PhotoImage(Image.open(tampon))
                qr.configure(image=qr.image, text="", width=0, height=0)
            except ImportError:
                qr.configure(image="", text=t("(installez segno pour le QR code)"), fg=DISCRET, width=30, height=4)
            lbl_url.configure(text=s.url(avec_code=False))
            lbl_code.configure(text=t("Code : {code}", code=s.code))

        montrer()

    # -------------------------------------------------------------- plein écran (stream)
    def plein_ecran(self):
        """Vidéo seule, en plein écran, habillée pour être diffusée (YouTube, Twitch…) : noms des
        tortues reconnues, « en direct », heure, repas du jour. Rien de privé ni de technique à
        l'écran (pas de chemins, de réglages, d'i/s, de noms douteux). Échap, F11 ou double-clic
        pour sortir ; P enregistre une photo 1920×1080 à partager (dossier « partage »)."""
        if self.diffusion is not None:
            self._quitter_diffusion()
            return
        f = tk.Toplevel(self.root, bg="black", cursor="none")
        f.title(t("Broutille — en direct"))
        f.protocol("WM_DELETE_WINDOW", self._quitter_diffusion)
        f.attributes("-fullscreen", True)
        f.attributes("-topmost", True)
        ecran = tk.Label(f, bg="black", bd=0)
        ecran.pack(fill="both", expand=True)
        self.diffusion, self.ecran_diffusion, self.image_diffusion = f, ecran, None
        self.derniere_diffusion = None
        if not hasattr(self, "f_diff"):
            self.f_diff = {"titre": police(34, True), "nom": police(30, True), "age": police(20),
                           "bas": police(22), "heure": police(40, True), "direct": police(20, True), "attente": police(36)}
        for touche in ("<Escape>", "<F11>", "<Double-1>"):
            f.bind(touche, lambda _e: self._quitter_diffusion())
        f.bind("<KeyPress-p>", lambda _e: self._photo_diffusion())
        f.bind("<KeyPress-P>", lambda _e: self._photo_diffusion())
        f.focus_force()
        f.after(200, self._diffusion_au_repos)

    def _quitter_diffusion(self):
        if self.diffusion is not None:
            self.diffusion.destroy()
        self.diffusion = self.image_diffusion = self.derniere_diffusion = None
        if self.surveillance is None:
            self._afficher_vide()

    def _diffusion_au_repos(self):
        """Sans surveillance, l'écran du stream reste propre : logo, heure, « de retour bientôt »."""
        if self.diffusion is None or not self.diffusion.winfo_exists():
            return
        if self.surveillance is None:
            lw, lh = self.diffusion.winfo_width(), self.diffusion.winfo_height()
            img = Image.new("RGB", (max(lw, 640), max(lh, 360)), (7, 10, 6))
            d = ImageDraw.Draw(img, "RGBA")
            try:
                logo = Image.open(ICI / "broutille.png").convert("RGBA").resize((200, 200), Image.LANCZOS)
                img.paste(logo, ((img.width - 200) // 2, img.height // 2 - 230), logo)
            except OSError:
                pass
            texte = t("La mangeoire revient dans un instant")
            d.text((img.width / 2, img.height / 2 + 30), texte, font=self.f_diff["attente"], fill=(233, 238, 227), anchor="mt")
            self._habillage(d, img.size, en_direct=False)
            self._montrer_diffusion(img)
        self.diffusion.after(1000, self._diffusion_au_repos)

    def _habillage(self, d, taille, en_direct=True):
        """Bandeau commun : titre et pastille en haut à gauche, heure en haut à droite, repas du jour en bas."""
        lw, lh = taille
        F = self.f_diff
        d.rounded_rectangle([24, 24, 60 + d.textlength("Broutille", font=F["titre"]), 84], radius=16, fill=(16, 20, 15, 190))
        d.text((42, 54), "Broutille", font=F["titre"], fill=(233, 238, 227), anchor="lm")
        if en_direct:
            x = 76 + d.textlength("Broutille", font=F["titre"])
            en_direct_ = t("EN DIRECT")
            larg = d.textlength(en_direct_, font=F["direct"]) + 52
            d.rounded_rectangle([x, 34, x + larg, 74], radius=20, fill=(248, 81, 73, 235))
            d.ellipse([x + 16, 47, x + 30, 61], fill="white")
            d.text((x + 38, 54), en_direct_, font=F["direct"], fill="white", anchor="lm")
        maintenant = datetime.now()
        heure = maintenant.strftime("%H:%M")
        jour = t("{jour} {mois}", jour=maintenant.day, mois=t(fiches.MOIS[maintenant.month - 1]))
        lh_h = d.textlength(heure, font=F["heure"])
        d.rounded_rectangle([lw - lh_h - 70, 24, lw - 24, 120], radius=16, fill=(16, 20, 15, 190))
        d.text((lw - 47, 30), heure, font=F["heure"], fill=(233, 238, 227), anchor="ra")
        d.text((lw - 47, 84), jour, font=F["age"], fill=(151, 163, 141), anchor="ra")
        if self.repas_du_jour:
            texte = t("Aujourd'hui à table :") + "   " + "   ·   ".join(f"{n}  {duree_lisible(s)}" for n, s in self.repas_du_jour[:4])
        else:
            texte = t("Aujourd'hui : pas encore de repas")
        tw = d.textlength(texte, font=F["bas"])
        d.rounded_rectangle([24, lh - 76, 24 + tw + 40, lh - 24], radius=16, fill=(16, 20, 15, 200))
        d.text((44, lh - 50), texte, font=F["bas"], fill=(233, 238, 227), anchor="lm")

    def _afficher_diffusion(self, image, etat):
        f = self.diffusion
        lw, lh = max(f.winfo_width(), 640), max(f.winfo_height(), 360)
        h, w = image.shape[:2]
        e = min(lw / w, lh / h)
        nw, nh = int(w * e), int(h * e)
        video = Image.fromarray(cv2.cvtColor(cv2.resize(image, (nw, nh), interpolation=cv2.INTER_LINEAR), cv2.COLOR_BGR2RGB))
        if (nw, nh) == (lw, lh):
            img = video
        else:                               # autre format que l'écran : bandes noires
            img = Image.new("RGB", (lw, lh))
            img.paste(video, ((lw - nw) // 2, (lh - nh) // 2))
        ox, oy = (lw - nw) // 2, (lh - nh) // 2
        d = ImageDraw.Draw(img, "RGBA")
        F = self.f_diff
        connues = self.registre.fiches
        pistes = etat["pistes"] if "pistes" in etat else [(None, b, nm, True) for b, nm in etat["tortues"]]
        for numero, boite, texte, sure, *reste in pistes:
            if not sure:
                continue                    # douteuse : rien à l'écran tant qu'elle n'est pas confirmée
            cle = reste[0] if reste else None
            fiche = connues.get(cle) if cle and not texte.endswith("?") else None
            nom = fiche["nom"] if fiche else t("Tortue")
            age = fiches.age_lisible(fiche.get("naissance", "")) if fiche else ""
            x, y, bw, bh = (int(v * e) for v in boite)
            x, y = x + ox, y + oy
            d.rounded_rectangle([x, y, x + bw, y + bh], radius=14, outline=(217, 164, 65, 255), width=4)
            tw = max(d.textlength(nom, font=F["nom"]), d.textlength(age, font=F["age"]) if age else 0)
            ht = 76 if age else 50
            yt = max(0, y - ht - 8)
            d.rounded_rectangle([x, yt, x + tw + 32, yt + ht], radius=14, fill=(16, 20, 15, 215))
            d.text((x + 16, yt + 6), nom, font=F["nom"], fill=(233, 238, 227))
            if age:
                d.text((x + 16, yt + 46), age, font=F["age"], fill=(217, 164, 65))
        if etat.get("figee_s"):             # direct coupé côté caméra : message aux spectateurs
            texte = t("Le direct revient dans un instant")
            tw = d.textlength(texte, font=F["attente"])
            d.rounded_rectangle([(lw - tw) / 2 - 30, lh / 2 - 40, (lw + tw) / 2 + 30, lh / 2 + 40], radius=20,
                                fill=(16, 20, 15, 220))
            d.text((lw / 2, lh / 2), texte, font=F["attente"], fill=(233, 238, 227), anchor="mm")
        self._habillage(d, (lw, lh))
        self._montrer_diffusion(img)

    def _montrer_diffusion(self, img):
        self.derniere_diffusion = img
        i = self.image_diffusion
        if i is not None and (i.width(), i.height()) == img.size:
            i.paste(img)
        else:
            self.image_diffusion = ImageTk.PhotoImage(img)
            self.ecran_diffusion.configure(image=self.image_diffusion)

    def _photo_diffusion(self):
        """Image du stream en 1920×1080, prête pour les réseaux sociaux."""
        if self.derniere_diffusion is None:
            return
        d = self.dossier / "partage"
        d.mkdir(parents=True, exist_ok=True)
        img = self.derniere_diffusion.copy()
        img.thumbnail((1920, 1080), Image.LANCZOS)
        fond = Image.new("RGB", (1920, 1080))
        fond.paste(img, ((1920 - img.width) // 2, (1080 - img.height) // 2))
        chemin = d / f"broutille_{datetime.now():%Y-%m-%d_%H-%M-%S}.jpg"
        fond.save(chemin, quality=92)
        self.lbl_etat.configure(text=t("Photo à partager : {fichier} (dossier « partage »)", fichier=chemin.name))
        flash = tk.Frame(self.diffusion, bg="white")       # petit éclair : la photo est prise
        flash.place(relwidth=1, relheight=1)
        self.diffusion.after(80, flash.destroy)

    # -------------------------------------------------------------- visites
    def charger_historique(self):
        self.arbre.delete(*self.arbre.get_children())
        self.lignes.clear()
        self.vignettes.clear()
        try:
            lignes = lire_journal(self.dossier)[-300:]
        except (JournalOccupe, OSError) as e:
            self.lbl_etat.configure(text=str(e))
            lignes = []
        for l in lignes:
            self._ajouter_visite(l, True)
        if lignes:
            self._afficher_visite(lignes[-1])
        else:
            self.visite_affichee = self.photo_visite = None
            self.lbl_photo.configure(image="")
            self.lbl_individu.configure(text="—", foreground=DISCRET)
            self.lbl_details.configure(text=t("Aucune visite pour l'instant"))
        self._maj_stats()
        self._maj_tortues()

    def _vignette(self, chemin, taille):
        """Vignette mise en cache : l'historique et les fiches se redessinent sans relire les photos."""
        try:
            cle = (str(chemin), taille, os.stat(chemin).st_mtime_ns)
            if cle in self.cache_vignettes:
                return self.cache_vignettes[cle]
            with Image.open(chemin) as img:
                img.draft("RGB", (taille[0] * 2, taille[1] * 2))   # JPEG décodé directement en petit
                img = ImageOps.exif_transpose(img)
                img.thumbnail(taille)
                vignette = ImageTk.PhotoImage(img)
        except (OSError, ValueError):
            return None
        if len(self.cache_vignettes) > 1500:
            self.cache_vignettes.clear()
        self.cache_vignettes[cle] = vignette
        return vignette

    def _ajouter_visite(self, ligne, en_tete):
        aujourd_hui = datetime.now().strftime("%Y-%m-%d")
        quand = ligne["heure"][:5] if ligne["date"] == aujourd_hui else f"{date_courte(ligne['date'])} {ligne['heure'][:5]}"
        vignette = self._vignette(self.dossier / ligne["photo"], (72, 48)) if ligne.get("photo") else None
        iid = self.arbre.insert("", 0 if en_tete else "end", text="", image=vignette or "",
                                values=(quand, f"{ligne['proposition']} ?" if ligne.get("proposition") else nom_affiche(ligne["individu"]),
                                        duree_lisible(secondes(ligne))))
        if vignette:
            self.vignettes[iid] = vignette
        self.lignes[iid] = ligne

    def _fiche_visite_affichee(self):
        l = self.visite_affichee or {}
        cle = l.get("id_individu") or l.get("id_proposition")
        if cle in self.registre.fiches:
            self.fiche_tortue(cle)

    def _afficher_visite(self, ligne):
        self.visite_affichee = ligne
        self.photo_visite = self._vignette(self.dossier / ligne["photo"], (370, 150)) if ligne.get("photo") else None
        self.lbl_photo.configure(image=self.photo_visite or "")
        nom = f"{ligne['proposition']} ?" if ligne.get("proposition") else nom_affiche(ligne["individu"])
        self.lbl_individu.configure(text=nom, foreground=DISCRET if ligne["individu"] == INCONNUE else TEXTE)
        quand = t("{date} à {heure}", date=date_courte(ligne["date"]), heure=ligne["heure"][:5])
        origine = {"manuel": "  ·  " + t("corrigée à la main"), "nouvelle": "  ·  " + t("nouvelle tortue")}.get(ligne.get("source"), "")
        fiche = self.registre.fiches.get(ligne.get("id_individu"))
        identite = fiches.resume_identite(fiche) if fiche else t(ligne["espece"])
        if ligne.get("camera") and len(self.cfg["cameras"]) > 1:
            origine += f"  ·  {ligne['camera']}"
        self.lbl_details.configure(text=f"{identite}\n{quand}  ·  {duree_lisible(secondes(ligne))}{origine}"
                                        + ("  ·  " + t("clic : sa fiche") if fiche else ""))

    def _selection(self, _):
        sel = self.arbre.selection()
        if sel:
            self._afficher_visite(self.lignes[sel[0]])

    def _ouvrir_video(self, _):
        sel = self.arbre.selection()
        if sel:
            video = self.lignes[sel[0]].get("video")
            chemin = self.dossier / video if video else None
            if chemin and chemin.is_file():
                os.startfile(chemin)

    def _menu_visite(self, evenement):
        iid = self.arbre.identify_row(evenement.y)
        if not iid:
            return
        self.arbre.selection_set(iid)
        ligne = self.lignes[iid]
        menu = tk.Menu(self.root, tearoff=0)
        if ligne.get("id_individu") in self.registre.fiches:
            menu.add_command(label="🐢  " + t("Fiche de {nom}…", nom=ligne["individu"]), command=lambda: self.fiche_tortue(ligne["id_individu"]))
            menu.add_separator()
        if self.registre.resoudre(ligne.get("id_proposition") or "") in self.registre.fiches:
            menu.add_command(label="✔  " + t("Oui, c'est {nom}", nom=ligne["proposition"]), command=lambda: self._corriger(ligne, ligne["id_proposition"]))
            menu.add_separator()
        menu.add_command(label=t("Cette visite est de :"), state="disabled")
        for cle, fiche in sorted(self.registre.copie_fiches().items(), key=lambda x: x[1]["nom"]):
            if cle != ligne.get("id_individu"):
                menu.add_command(label=fiche["nom"], command=lambda c=cle: self._corriger(ligne, c))
        menu.add_separator()
        menu.add_command(label=t("Nouvelle tortue…"), command=lambda: self._corriger_nouvelle(ligne))
        menu.add_command(label=t("Pas une tortue"), command=lambda: self._pas_une_tortue(ligne))
        if ligne.get("video"):
            menu.add_separator()
            menu.add_command(label="🎬  " + t("Clip vertical pour Shorts / Reels / TikTok"), command=lambda: self._demander_clip(ligne))
        menu.tk_popup(evenement.x_root, evenement.y_root)

    def _menu_video(self, evenement):
        """Clic sur une tortue de la vidéo en direct : tortue reconnue → sa fiche ; douteuse ou
        clic droit → menu pour la nommer (avec sa fiche en tête si on a une idée de qui c'est)."""
        if not self.surveillance:
            return
        zone = next((z for z in reversed(self.zones_video)
                     if z[0] <= evenement.x <= z[2] and z[1] <= evenement.y <= z[3]), None)
        if zone is None:
            return
        numero, texte = zone[4], zone[5]
        cle = zone[6] if len(zone) > 6 and zone[6] in self.registre.fiches else None
        if cle and zone[7] and evenement.num == 1:
            self.fiche_tortue(cle)
            return
        menu = tk.Menu(self.root, tearoff=0)
        if cle:
            menu.add_command(label="🐢  " + t("Fiche de {nom}…", nom=self.registre.fiches[cle]["nom"]), command=lambda: self.fiche_tortue(cle))
            menu.add_separator()
        menu.add_command(label=t("{tortue} — cette tortue est :", tortue=texte), state="disabled")
        connues = sorted(self.registre.copie_fiches().items(), key=lambda x: (x[1].get("provisoire", False), x[1]["nom"]))
        for autre, fiche in connues:
            menu.add_command(label=fiche["nom"], command=lambda c=autre: self._nommer_piste(numero, c))
        menu.add_separator()
        menu.add_command(label=t("Nouvelle tortue…"), command=lambda: self._nommer_piste_nouvelle(numero))
        menu.add_command(label=t("Pas une tortue"), command=lambda: self._nommer_piste(numero, PAS_UNE_TORTUE))
        menu.tk_popup(evenement.x_root, evenement.y_root)

    def _nommer_piste(self, numero, cle):
        surveillance = self.surveillance
        if surveillance is None:
            return
        if not surveillance.nommer_piste(numero, cle):
            self.lbl_etat.configure(text=t("Cette tortue vient de partir : corrigez sa visite dans l'historique (clic droit)"))

    def _nommer_piste_nouvelle(self, numero):
        resultat = self._dialogue_tortue(t("Nouvelle tortue"))
        if resultat:
            cle = self.registre.creer(*resultat)
            self._maj_tortues()
            self._nommer_piste(numero, cle)

    def _pas_une_tortue(self, ligne):
        if messagebox.askyesno(t("Pas une tortue"), t("Effacer cette visite, son clip et ses photos ?\n"
                                                      "Broutille ignorera ce qui lui ressemble ; Réglages permet de l'annuler.")):
            self._corriger(ligne, PAS_UNE_TORTUE)

    def _corriger(self, ligne, cle):
        if cle != PAS_UNE_TORTUE:
            cle = self.registre.resoudre(cle) or cle    # tortue fusionnée entre-temps : celle qui l'a absorbée

        def travail():
            try:
                with self.verrou_corrections:   # une à la fois : deux corrections rapides ne mêlent pas les galeries
                    corrigee = corriger_visite(self.dossier, self.registre, ligne["id_visite"], cle)
                if corrigee is None:
                    self.messages.put(("corrige", t("Cette visite n'est plus au journal")))
                elif corrigee["sans_image"]:
                    self.messages.put(("corrige", t("Corrigé : {nom} (images de cette visite déjà effacées)", nom=nom_affiche(corrigee["individu"]))))
                else:
                    self.messages.put(("corrige", t("Corrigé : {nom} — Broutille retient ces images", nom=nom_affiche(corrigee["individu"]))))
            except JournalOccupe as e:
                self.messages.put(("corrige", str(e)))
            except Exception as e:
                self.messages.put(("corrige", t("Correction impossible : {type} : {erreur}", type=type(e).__name__, erreur=e)))
        self.lbl_etat.configure(text=t("Correction en cours…"))
        threading.Thread(target=travail, daemon=True).start()

    def _corriger_nouvelle(self, ligne):
        resultat = self._dialogue_tortue(t("Nouvelle tortue"), espece=ligne["espece"])
        if resultat:
            self._corriger(ligne, self.registre.creer(*resultat))

    def _maj_stats(self):
        aujourd_hui = datetime.now().strftime("%Y-%m-%d")
        temps, noms = defaultdict(float), {}
        for l in self.lignes.values():
            if l["date"] == aujourd_hui:
                qui = l.get("id_individu") or l["individu"]     # deux tortues du même nom restent deux
                temps[qui] += secondes(l)
                fiche = self.registre.fiches.get(l.get("id_individu"))
                noms[qui] = fiche["nom"] if fiche else nom_affiche(l["individu"])
        c = self.stats
        c.delete("all")
        largeur = max(c.winfo_width(), 360)
        if not temps:
            self.repas_du_jour = []
            c.configure(height=30)
            c.create_text(0, 14, anchor="w", text=t("Pas encore de repas aujourd'hui"), fill=DISCRET, font=PT(10))
            return
        top = [(noms[q], s) for q, s in sorted(temps.items(), key=lambda x: -x[1])[:5]]
        self.repas_du_jour = [(n, s) for n, s in top if n != nom_affiche(INCONNUE)]
        c.configure(height=26 * len(top))
        maxi = top[0][1] or 1
        for i, (nom, s) in enumerate(top):
            y = i * 26 + 4
            barre = max(4, (largeur - 190) * s / maxi)
            c.create_text(0, y + 9, anchor="w", text=nom[:18], fill=TEXTE, font=PT(10))
            c.create_rectangle(120, y + 3, 120 + barre, y + 15, fill=COULEURS[i % len(COULEURS)], width=0)
            c.create_text(128 + barre, y + 9, anchor="w", text=duree_lisible(s), fill=DISCRET, font=PT(9))

    # -------------------------------------------------------------- tortues
    def _fermer_fiche(self, cle):
        f = self.fenetres_fiche.pop(cle, None)
        if f is not None and f.winfo_exists():
            f.destroy()

    def _maj_tortues(self):
        for cle in [c for c in self.fenetres_fiche if c not in self.registre.fiches]:
            self._fermer_fiche(cle)             # tortue fusionnée ou supprimée : sa fiche n'a plus d'objet
        a = self.arbre_t
        a.delete(*a.get_children())
        self.vignettes_tortues.clear()
        visites, derniere = defaultdict(int), {}
        try:
            journal = lire_journal(self.dossier)
        except (JournalOccupe, OSError):
            journal = []
        for l in journal:
            cle = l.get("id_individu")
            visites[cle] += 1
            # une visite à confirmer compte pour l'alerte d'absence : la tortue a sans doute mangé
            for c in (cle, l.get("id_proposition")):
                derniere[c] = max(derniere.get(c, ""), l["date"])
        limite = (datetime.now() - timedelta(days=self.cfg["alerte_jours"])).strftime("%Y-%m-%d")
        limite_pesee = (datetime.now() - timedelta(days=self.cfg["rappel_pesee_jours"])).strftime("%Y-%m-%d")
        for cle, fiche in sorted(self.registre.copie_fiches().items(), key=lambda x: (x[1].get("provisoire", False), x[1]["nom"])):
            portrait = self.registre.photo_profil(cle)
            vignette = self._vignette(portrait, (64, 48)) if portrait else None
            vue = derniere.get(cle, "")
            pesee = max((p["date"] for p in fiche.get("pesees", [])), default="")
            a_peser = bool(self.cfg["rappel_pesee_jours"]) and not fiche.get("provisoire") and pesee < limite_pesee
            tags = ("provisoire",) if fiche.get("provisoire") else ("absente",) if vue and vue < limite else \
                ("a_peser",) if a_peser else ()
            a.insert("", "end", iid=cle, image=vignette or "", tags=tags,
                     values=(fiche["nom"], visites[cle], date_courte(vue) if vue else t("jamais"),
                             (date_courte(pesee) if pesee else t("à faire")) + (" ⚖" if a_peser else "")))
            if vignette:
                self.vignettes_tortues[cle] = vignette

    def _dialogue_tortue(self, titre, nom="", espece=None):
        """(nom, espèce) saisis, ou None."""
        f = tk.Toplevel(self.root, bg=CARTE, padx=20, pady=16)
        f.title(titre)
        f.transient(self.root)
        f.grab_set()
        resultat = []
        libelles, especes = especes_affichees(self.classeur.especes)
        v_nom, v_espece = tk.StringVar(value=nom), tk.StringVar(value=t(espece or self.classeur.especes[0][0]))
        ttk.Label(f, text=t("Nom"), style="Carte.TLabel").grid(row=0, column=0, sticky="w", pady=5, padx=(0, 12))
        e = ttk.Entry(f, textvariable=v_nom, width=30)
        e.grid(row=0, column=1)
        e.focus_set()
        ttk.Label(f, text=t("Espèce"), style="Carte.TLabel").grid(row=1, column=0, sticky="w", pady=5, padx=(0, 12))
        ttk.Combobox(f, textvariable=v_espece, values=libelles, width=28).grid(row=1, column=1)

        def valider(_=None):
            if v_nom.get().strip():
                saisie = v_espece.get().strip()
                resultat.append((v_nom.get().strip(), especes.get(saisie, saisie)))
                f.destroy()

        f.bind("<Return>", valider)
        ttk.Button(f, text=t("Valider"), style="Vert.TButton", command=valider).grid(row=2, column=1, sticky="e", pady=(12, 0))
        self.root.wait_window(f)
        return resultat[0] if resultat else None

    def ajouter_tortue(self):
        resultat = self._dialogue_tortue(t("Ajouter une tortue"))
        if not resultat:
            return
        cle = self.registre.creer(*resultat)
        self._maj_tortues()
        if messagebox.askyesno(t("Ajouter une tortue"), t("Ajouter des photos de cette tortue maintenant ?\n"
                                                           "Plusieurs vues aident : face, deux profils, dessus.")):
            self._importer_photos(cle)

    def _importer_photos(self, cle, chemins=None):
        chemins = chemins or filedialog.askopenfilenames(title=t("Photos de la tortue"),
                                                         filetypes=[(t("Photos"), "*.jpg *.jpeg *.png")])
        if not chemins:
            return

        def travail():
            try:
                n = inscrire_photos(self.registre, self.detecteur, cle, chemins, lambda m: self.messages.put(("message", m)))
                self.messages.put(("corrige", tn("{n} photo ajoutée à {nom}", "{n} photos ajoutées à {nom}", n,
                                                  nom=self.registre.fiches[cle]["nom"])))
            except Exception as e:
                self.messages.put(("corrige", t("Import impossible : {type} : {erreur}", type=type(e).__name__, erreur=e)))
        self.lbl_etat.configure(text=t("Analyse des photos…"))
        threading.Thread(target=travail, daemon=True).start()

    def _menu_tortue(self, evenement):
        cle = self.arbre_t.identify_row(evenement.y)
        if not cle:
            return
        self.arbre_t.selection_set(cle)
        fiche = self.registre.fiches[cle]
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=f"{fiche['nom']} — {t(fiche['espece'])}", state="disabled")
        menu.add_command(label="🐢  " + t("Fiche complète (naissance, sexe, notes)…"), command=lambda: self.fiche_tortue(cle))
        menu.add_command(label="⚖  " + t("Poids…"), command=lambda: self.fiche_tortue(cle, 1))
        menu.add_command(label="🖼  " + t("Photos…"), command=lambda: self.fiche_tortue(cle, 2))
        menu.add_command(label="📒  " + t("Carnet de soins…"), command=lambda: self.fiche_tortue(cle, 3))
        menu.add_command(label=t("Apprendre des photos pour la reconnaissance…"), command=lambda: self._importer_photos(cle))
        menu.add_command(label="📊  " + t("Repas sur 30 jours…"), command=lambda: self.statistiques(cle))
        menu.add_command(label="📄  " + t("Fiche pour le vétérinaire (PDF)…"), command=lambda: self.fiche_veterinaire(cle))
        fusion = tk.Menu(menu, tearoff=0)
        for autre, f in sorted(self.registre.copie_fiches().items(), key=lambda x: x[1]["nom"]):
            if autre != cle:
                fusion.add_command(label=f["nom"], command=lambda a=autre: self._fusionner(cle, a))
        menu.add_cascade(label=t("C'est la même tortue que"), menu=fusion)
        menu.add_separator()
        menu.add_command(label=t("Supprimer la fiche…"), command=lambda: self._supprimer(cle))
        menu.tk_popup(evenement.x_root, evenement.y_root)

    def _fusionner(self, source, cible):
        fs, fc = self.registre.fiches[source], self.registre.fiches[cible]
        if messagebox.askyesno(t("Même tortue"), t("« {source} » et « {cible} » sont la même tortue ?\n"
                                                   "Tout est regroupé sous « {cible} ».", source=fs["nom"], cible=fc["nom"])):
            self._journal_puis(lambda: renommer_dans_journal(self.dossier, source, fc["nom"], fc["espece"], cible),
                               lambda: self.registre.fusionner(source, cible))
            ouverte = self.fenetres_fiche.get(cible)
            if ouverte is not None and ouverte.winfo_exists() and hasattr(ouverte, "remplir"):
                ouverte.remplir()               # sinon « Enregistrer » écraserait ce que la fusion a apporté
            self.charger_historique()

    def _supprimer(self, cle):
        fiche = self.registre.fiches[cle]
        if messagebox.askyesno(t("Supprimer"), t("Supprimer la fiche et la galerie de « {nom} » ?\n"
                                                 "Ses visites restent au journal, sous le nom « Inconnue ».", nom=fiche["nom"])):
            self._journal_puis(lambda: renommer_dans_journal(self.dossier, cle, INCONNUE, None, ""),
                               lambda: self.registre.supprimer(cle))
            self.charger_historique()

    def _journal_puis(self, journal, registre):
        """Journal puis fiches, sous le verrou du journal : une visite que la surveillance termine au
        même moment ne peut pas s'écrire entre les deux avec l'ancien identifiant."""
        erreur = None
        with VERROU_JOURNAL:
            try:
                journal()
                registre()
            except JournalOccupe as e:
                erreur = e
        if erreur:                      # boîte de dialogue hors du verrou : la surveillance continue
            messagebox.showerror(t("Journal"), str(erreur))

    def _journal_libre(self, fonction, *args):
        """Journal d'abord : s'il est bloqué, les fiches ne bougent pas et rien ne diverge."""
        try:
            fonction(*args)
            return True
        except JournalOccupe as e:
            messagebox.showerror(t("Journal"), str(e))
            return False

    def _ouvrir_galerie(self, evenement):
        cle = self.arbre_t.identify_row(evenement.y)
        if cle:
            self.fiche_tortue(cle)

    # -------------------------------------------------------------- statistiques
    def statistiques(self, choisie=None):
        """Tableau des 30 derniers jours ; un clic sur une tortue affiche le graphique de ses
        repas, et le bouton fait sa fiche PDF pour le vétérinaire. choisie : clé à sélectionner."""
        f = tk.Toplevel(self.root, bg=CARTE, padx=16, pady=14)
        f.title(t("Statistiques — 30 derniers jours"))
        f.transient(self.root)
        debut = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        par = defaultdict(lambda: {"nom": "", "n": 0, "s": 0.0, "jours": set(), "dernier": "", "espece": ""})
        try:
            journal = lire_journal(self.dossier)
        except (JournalOccupe, OSError):
            journal = []
        fiches = self.registre.copie_fiches()
        for l in journal:
            if l["date"] >= debut:
                cle = l.get("id_individu") or f"nom:{l['individu']}"   # « Inconnue » n'a pas de fiche
                p = par[cle]
                p["nom"] = fiches[cle]["nom"] if cle in fiches else nom_affiche(l["individu"])
                p["n"] += 1
                p["s"] += secondes(l)
                p["jours"].add(l["date"])
                p["dernier"] = max(p["dernier"], l["date"])
                p["espece"] = l["espece"]
        for cle, fiche in fiches.items():      # une tortue qui n'est pas venue apparaît aussi
            if cle not in par and not fiche.get("provisoire"):
                par[cle].update(nom=fiche["nom"], espece=fiche["espece"])
        colonnes = (("nom", t("TORTUE"), 170), ("espece", t("ESPÈCE"), 150), ("n", t("VISITES"), 70),
                    ("temps", t("TEMPS À TABLE"), 110), ("moy", t("PAR JOUR DE VISITE"), 130), ("jours", t("JOURS VENUE"), 90),
                    ("vue", t("DERNIÈRE VISITE"), 110))
        ttk.Style(self.root).configure("Stats.Treeview", rowheight=28)
        a = ttk.Treeview(f, columns=[c[0] for c in colonnes], show="headings", style="Stats.Treeview", height=8,
                         selectmode="browse")
        for col, titre, larg in colonnes:
            a.heading(col, text=titre, anchor="w")
            a.column(col, width=larg, anchor="w")
        a.pack(fill="both", expand=True)
        for cle, p in sorted(par.items(), key=lambda x: -x[1]["s"]):
            a.insert("", "end", iid=cle, values=(p["nom"], t(p["espece"]) if p["espece"] else "", p["n"], duree_lisible(p["s"]),
                                                 duree_lisible(p["s"] / max(len(p["jours"]), 1)) if p["jours"] else "—",
                                                 len(p["jours"]), p["dernier"] or "—"))

        bas = tk.Frame(f, bg=CARTE)
        bas.pack(fill="x", pady=(12, 0))
        graphe = tk.Label(bas, bg=CARTE, fg=DISCRET, text=t("Cliquez sur une tortue pour voir ses repas jour par jour."),
                          font=PT(10))
        graphe.pack(fill="x")
        boutons = tk.Frame(bas, bg=CARTE)
        boutons.pack(fill="x", pady=(10, 0))
        btn_pdf = ttk.Button(boutons, text="📄  " + t("Fiche pour le vétérinaire (PDF)…"), state="disabled",
                             command=lambda: self.fiche_veterinaire(a.selection()[0]) if a.selection() else None)
        btn_pdf.pack(side="right")

        def montrer(_=None):
            if not a.selection():
                return
            cle = a.selection()[0]
            avec_fiche = cle in fiches
            btn_pdf.configure(state="normal" if avec_fiche else "disabled")
            if not avec_fiche:
                graphe.configure(image="", text=t("Visites non reconnues : confirmez-les pour les compter à une tortue."))
                return
            img = rapports.graphique_repas(rapports.repas_par_jour(journal, cle), t("{nom} — minutes à table par jour", nom=fiches[cle]["nom"]),
                                           (900, 300), fond=(27, 33, 25), encre=(233, 238, 227), discret=(151, 163, 141),
                                           filet=(45, 55, 41), barre=(127, 185, 80), vide=(248, 81, 73))
            graphe.image = ImageTk.PhotoImage(img)
            graphe.configure(image=graphe.image, text="")

        a.bind("<<TreeviewSelect>>", montrer)
        if choisie and a.exists(choisie):
            a.selection_set(choisie)
            a.see(choisie)
            montrer()

    # -------------------------------------------------------------- confirmation rapide
    def confirmer_rapide(self):
        """Les visites non nommées, une par une : Entrée = « Oui, c'est Zoé », 1 à 9 = une tortue,
        Espace = passer. Chaque réponse est une correction ordinaire (galerie, journal)."""
        try:
            journal = lire_journal(self.dossier)
        except (JournalOccupe, OSError) as e:
            messagebox.showerror(t("À confirmer"), t("Journal illisible pour l'instant : {erreur}", erreur=e))
            return
        file = [l for l in sorted(journal, key=lambda l: (l["date"], l["heure"]), reverse=True)
                if not l.get("id_individu")]
        if not file:
            messagebox.showinfo(t("À confirmer"), t("Toutes les visites sont nommées. Bravo !"))
            return
        f = tk.Toplevel(self.root, bg=CARTE, padx=18, pady=14)
        f.title(t("À confirmer"))
        f.transient(self.root)
        etat = {"i": 0, "faites": 0}
        compteur = ttk.Label(f, style="Discret.TLabel")
        compteur.pack(anchor="w")
        images = tk.Frame(f, bg=CARTE)
        images.pack(fill="x", pady=(8, 0))
        lbl_tortue, lbl_scene = tk.Label(images, bg=CARTE), tk.Label(images, bg=CARTE)
        lbl_tortue.pack(side="left")
        lbl_scene.pack(side="left", padx=(14, 0))
        details = ttk.Label(f, style="Carte.TLabel")
        details.pack(anchor="w", pady=(8, 0))
        choix = tk.Frame(f, bg=CARTE)
        choix.pack(fill="x", pady=(10, 0))
        bas = tk.Frame(f, bg=CARTE)
        bas.pack(fill="x", pady=(12, 0))

        def charger(chemin, taille):
            try:
                img = Image.open(chemin)
                img.thumbnail(taille)
                return ImageTk.PhotoImage(img)
            except OSError:
                return None

        def repondre(cle):
            ligne = file[etat["i"]]
            if cle is not None:
                self._corriger(ligne, cle)
                etat["faites"] += 1
            etat["i"] += 1
            montrer()

        def nouvelle():
            ligne = file[etat["i"]]
            resultat = self._dialogue_tortue(t("Nouvelle tortue"), espece=ligne["espece"])
            if resultat:
                repondre(self.registre.creer(*resultat))
                self._maj_tortues()

        def montrer():
            for w in choix.winfo_children() + bas.winfo_children():
                w.destroy()
            for touche in [str(k) for k in range(1, 10)] + ["<Return>", "<space>"]:
                f.unbind(touche)
            if etat["i"] >= len(file):
                compteur.configure(text=tn("Terminé : {n} visite nommée.", "Terminé : {n} visites nommées.", etat["faites"]))
                for lbl in (lbl_tortue, lbl_scene):
                    lbl.configure(image="")
                details.configure(text=t("Merci ! Broutille retient ces images pour mieux reconnaître vos tortues."))
                ttk.Button(bas, text=t("Fermer"), style="Vert.TButton", command=f.destroy).pack(side="right")
                return
            ligne = file[etat["i"]]
            compteur.configure(text=t("Visite {i} sur {total}", i=etat["i"] + 1, total=len(file)) + "  ·  " +
                               tn("{n} nommée", "{n} nommées", etat["faites"]))
            base = self.dossier / ligne["id_visite"]
            lbl_tortue.image = charger(f"{base}_tortue.jpg", (300, 300))
            lbl_scene.image = charger(f"{base}_photo.jpg", (420, 300))
            lbl_tortue.configure(image=lbl_tortue.image or "", text="" if lbl_tortue.image else t("photo effacée par le ménage"),
                                 fg=DISCRET)
            lbl_scene.configure(image=lbl_scene.image or "")
            details.configure(text=t("{date} à {heure}", date=date_courte(ligne["date"]), heure=ligne["heure"][:5]) +
                              f"  ·  {duree_lisible(secondes(ligne))}  ·  {t(ligne['espece'])}")
            fiches = sorted(self.registre.copie_fiches().items(), key=lambda x: (x[1].get("provisoire", False), x[1]["nom"]))
            proposee = self.registre.resoudre(ligne.get("id_proposition") or "")
            if proposee:
                ttk.Button(choix, text="✔  " + t("Oui, c'est {nom}", nom=self.registre.fiches[proposee]["nom"]) + "   (" + t("Entrée") + ")", style="Vert.TButton",
                           command=lambda: repondre(proposee)).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
                f.bind("<Return>", lambda _e: repondre(proposee))
            for k, (cle, fiche) in enumerate(fiches):
                raccourci = f"   ({k + 1})" if k < 9 else ""
                ttk.Button(choix, text=fiche["nom"] + raccourci, command=lambda c=cle: repondre(c)
                           ).grid(row=1 + k // 3, column=k % 3, sticky="we", padx=(0, 6), pady=2)
                if k < 9:
                    f.bind(str(k + 1), lambda _e, c=cle: repondre(c))
            ttk.Button(bas, text=t("Nouvelle tortue…"), command=nouvelle).pack(side="left")
            ttk.Button(bas, text=t("Pas une tortue (efface la visite)"), command=lambda: repondre(PAS_UNE_TORTUE)
                       ).pack(side="left", padx=8)
            if ligne.get("video") and (self.dossier / ligne["video"]).exists():
                ttk.Button(bas, text="▶  " + t("Clip"), command=lambda: os.startfile(self.dossier / ligne["video"])).pack(side="left")
            ttk.Button(bas, text=t("Passer") + "   (" + t("Espace") + ")", command=lambda: repondre(None)).pack(side="right")
            f.bind("<space>", lambda _e: repondre(None))

        f.focus_set()
        montrer()

    # -------------------------------------------------------------- comportement
    def comportement(self):
        """Rythme, réseau social, dominance et santé, tirés du journal des visites."""
        f = tk.Toplevel(self.root, bg=CARTE, padx=16, pady=14)
        f.title(t("Comportement des tortues"))
        f.transient(self.root)
        try:
            journal = lire_journal(self.dossier)
        except (JournalOccupe, OSError):
            journal = []
        noms = comportement.noms(journal)
        noms.update({c: fi["nom"] for c, fi in self.registre.copie_fiches().items()})
        nom = lambda c: nom_affiche(noms.get(c, c))
        couleurs = dict(fond=(27, 33, 25), encre=(233, 238, 227), discret=(151, 163, 141))

        haut = tk.Frame(f, bg=CARTE)
        haut.pack(fill="x")
        ttk.Label(haut, text=t("Période :"), style="Carte.TLabel").pack(side="left")
        periodes = {t("30 jours"): 30, t("90 jours"): 90, t("1 an"): 365, t("Tout"): None}     # libellé affiché -> jours
        v_periode = tk.StringVar(value=t("30 jours"))
        ttk.Combobox(haut, textvariable=v_periode, values=list(periodes), state="readonly", width=10).pack(side="left", padx=8)
        info = ttk.Label(haut, style="Discret.TLabel")
        info.pack(side="left", padx=8)
        onglets = ttk.Notebook(f)
        onglets.pack(fill="both", expand=True, pady=(10, 0))
        pages = {}
        positions = lire_positions(self.dossier)
        photos = sorted(self.dossier.glob("*_photo.jpg"))
        try:
            fond_zones = None
            if photos:
                with Image.open(photos[-1]) as img:     # copiée en mémoire : le fichier reste libre
                    fond_zones = img.copy()
        except OSError:
            fond_zones = None
        for titre, libelle in (("Rythme", t("Rythme")), ("Réseau social", t("Réseau social")), ("Dominance", t("Dominance")),
                               ("Déplacements", t("Déplacements")), ("Santé", t("Santé"))):
            pages[titre] = tk.Frame(onglets, bg=CARTE, padx=8, pady=8)
            onglets.add(pages[titre], text=libelle)

        def tableau(parent, colonnes, lignes, rouges=()):
            a = ttk.Treeview(parent, columns=[c[0] for c in colonnes], show="headings", height=min(10, max(3, len(lignes))))
            for col, titre, larg in colonnes:
                a.heading(col, text=titre, anchor="w")
                a.column(col, width=larg, anchor="w")
            a.tag_configure("rouge", foreground=ROUGE)
            for i, valeurs in enumerate(lignes):
                a.insert("", "end", values=valeurs, tags=("rouge",) if i in rouges else ())
            a.pack(fill="x", pady=(8, 0))

        def image(parent, img):
            lbl = tk.Label(parent, bg=CARTE)
            lbl.image = ImageTk.PhotoImage(img)
            lbl.configure(image=lbl.image)
            lbl.pack(anchor="w")

        def remplir(_=None):
            for page in pages.values():
                for w in page.winfo_children():
                    w.destroy()
            s = comportement.sejours(journal, periodes[v_periode.get()])
            jours = len({d.date() for _c, d, _f in s})
            info.configure(text=tn("{n} visite nommée", "{n} visites nommées", len(s)) + " " +
                                tn("sur {n} jour", "sur {n} jours", jours)
                                + ("  —  " + t("encore peu de données : tendances à confirmer") if jours < 14 else ""))
            if not s:
                for page in pages.values():
                    ttk.Label(page, text=t("Pas encore de visite nommée sur cette période."), style="Carte.TLabel").pack()
                return
            # rythme
            r = comportement.rythme(s)
            image(pages["Rythme"], comportement.image_rythme(r, noms, chaud=(127, 185, 80), **couleurs))
            reg = comportement.regularite(s)
            tableau(pages["Rythme"], (("nom", t("TORTUE"), 170), ("arrivee", t("ARRIVÉE MOYENNE"), 140),
                                      ("ecart", t("RÉGULARITÉ (± min)"), 150), ("jours", t("JOURS VENUE"), 100)),
                    [(nom(c), comportement.heure_lisible(v["arrivee_moy"]), f"± {v['ecart_min']:.0f}", v["jours"])
                     for c, v in sorted(reg.items(), key=lambda x: x[1]["arrivee_moy"])])
            # réseau social
            reseau = comportement.reseau_social(s)
            totaux = {c: sum(v) for c, v in r.items()}
            image(pages["Réseau social"], comportement.image_reseau(reseau, totaux, noms, trait=(127, 185, 80),
                                                                    filet=(70, 84, 64), **couleurs))
            tableau(pages["Réseau social"], (("a", t("TORTUE"), 150), ("b", t("AVEC"), 150), ("fois", t("REPAS PARTAGÉS"), 120),
                                             ("temps", t("ENSEMBLE"), 100), ("aff", t("AFFINITÉ"), 90)),
                    [(nom(a), nom(b), v["fois"], duree_lisible(v["ensemble_s"]),
                      pourcent(v["affinite"]) if v["affinite"] >= 0.005 else "< " + pourcent(0.01))
                     for (a, b), v in sorted(reseau.items(), key=lambda x: -x[1]["affinite"])])
            ttk.Label(pages["Réseau social"], style="Discret.TLabel", text=t("Affinité : part du temps à table où les deux "
                      "sont là ensemble. Trait épais : elles mangent souvent ensemble.")).pack(anchor="w", pady=(6, 0))
            # dominance
            comptes, classement = comportement.dominance(s)
            ttk.Label(pages["Dominance"], style="Carte.TLabel", text=t("Une tortue arrive, l'autre part dans la minute : "
                      "elle l'a sans doute fait partir.")).pack(anchor="w")
            tableau(pages["Dominance"], (("rang", t("RANG"), 50), ("nom", t("TORTUE"), 170), ("g", t("FAIT PARTIR"), 100),
                                         ("p", t("PARTIE"), 80), ("score", t("DOMINANCE"), 100)),
                    [(i + 1, nom(c), g, p, pourcent(sc)) for i, (c, g, p, sc) in enumerate(classement)])
            tableau(pages["Dominance"], (("g", t("QUI"), 170), ("p", t("FAIT PARTIR QUI"), 170), ("n", t("FOIS"), 80)),
                    [(nom(g), nom(p), n) for (g, p), n in sorted(comptes.items(), key=lambda x: -x[1])])
            ttk.Label(pages["Dominance"], style="Discret.TLabel", text=t("Un indice, pas une preuve : une tortue peut "
                      "aussi partir parce qu'elle a fini. Il devient fiable avec des dizaines de rencontres.")
                      ).pack(anchor="w", pady=(6, 0))
            # déplacements : positions notées à chaque analyse pendant les visites
            page = pages["Déplacements"]
            tr = deplacements.trajets(journal, positions, periodes[v_periode.get()])
            if not tr:
                ttk.Label(page, style="Carte.TLabel", text=t("Pas encore de positions sur cette période.\nBroutille les note "
                          "depuis cette version, à chaque visite nommée : revenez après quelques repas.")).pack(anchor="w")
            else:
                ligne_haut = tk.Frame(page, bg=CARTE)
                ligne_haut.pack(fill="x")
                ttk.Label(ligne_haut, text=t("Zones de"), style="Carte.TLabel").pack(side="left")
                presentes = sorted({c for c, _p in tr}, key=nom)
                choix = {t("toutes les tortues"): None, **{nom(c): c for c in presentes}}
                v_qui = tk.StringVar(value=t("toutes les tortues"))
                ttk.Combobox(ligne_haut, textvariable=v_qui, values=list(choix), state="readonly", width=20
                             ).pack(side="left", padx=8)
                lbl_zones = tk.Label(page, bg=CARTE)
                lbl_zones.pack(anchor="w", pady=(6, 0))

                def zones(*_):
                    carte, rapport = deplacements.carte_zones(tr, choix[v_qui.get()])
                    lbl_zones.image = ImageTk.PhotoImage(deplacements.image_zones(carte, rapport, fond_zones, 560))
                    lbl_zones.configure(image=lbl_zones.image)

                v_qui.trace_add("write", zones)
                zones()
                act = deplacements.activite(tr)
                tableau(page, (("nom", t("TORTUE"), 150), ("vue", t("OBSERVÉE"), 90), ("dist", t("PARCOURU"), 130),
                               ("rythme", t("PAR MINUTE"), 110), ("bouge", t("EN MOUVEMENT"), 110)),
                        [(nom(c), duree_lisible(v["minutes"] * 60), t("{n} carapaces", n=f"{v['distance']:.0f}"),
                          nombre(v["par_minute"], 1), pourcent(v["mouvement"]))
                         for c, v in sorted(act.items(), key=lambda x: -x[1]["par_minute"])])
                inter = deplacements.interactions(tr)
                lignes_i = []
                for (a, b), v in sorted(inter.items(), key=lambda x: -x[1]["contact_s"]):
                    poursuites = ", ".join(t("{qui} suit {autre} ×{n}", qui=nom(q), autre=nom(b if q == a else a), n=n)
                                           for q, n in v["poursuites"].items())
                    lignes_i.append((t("{a} et {b}", a=nom(a), b=nom(b)), duree_lisible(v["contact_s"]), v["chevauchements"],
                                     poursuites or "—"))
                if lignes_i:
                    tableau(page, (("paire", t("ENSEMBLE"), 220), ("contact", t("AU CONTACT"), 100),
                                   ("dessus", t("L'UNE SUR L'AUTRE"), 130), ("pours", t("POURSUITES"), 300)), lignes_i)
                ttk.Label(page, style="Discret.TLabel", text=t("Distances en longueurs de carapace. « L'une sur l'autre » : "
                          "monte, ou coup de bélier ; regardez le clip. Positions toutes les 1 à 5 s : une poursuite "
                          "rapide peut échapper.")).pack(anchor="w", pady=(6, 0))
            # santé : toujours par rapport à aujourd'hui, toutes visites comprises
            sa = comportement.sante(comportement.sejours(journal))
            lignes = sorted(sa.items(), key=lambda x: (not x[1]["alertes"], nom(x[0])))
            tableau(pages["Santé"], (("nom", t("TORTUE"), 160), ("sem", t("7 DERNIERS JOURS"), 130), ("ref", t("HABITUDE"), 100),
                                     ("abs", t("DERNIÈRE VISITE"), 120), ("alerte", t("À SURVEILLER"), 330)),
                    [(nom(c), t("{n} min/j", n=f"{v['semaine_min_j']:.0f}"),
                      t("{n} min/j", n=f"{v['ref_min_j']:.0f}") if v["ref_min_j"] is not None else "—",
                      t("aujourd'hui") if v["absente_j"] == 0 else t("il y a {n} j", n=v["absente_j"]),
                      " · ".join(v["alertes"]) or (t("RAS") if v["ref_min_j"] is not None
                                                   else t("habitudes pas encore connues (1re semaine)"))) for c, v in lignes],
                    rouges={i for i, (_c, v) in enumerate(lignes) if v["alertes"]})
            ttk.Label(pages["Santé"], style="Discret.TLabel", text=t("Habitude : les 30 jours avant la dernière semaine. "
                      "Une baisse peut venir de la météo (froid, pluie) : comparez avec la courbe de poids.")
                      ).pack(anchor="w", pady=(6, 0))

        v_periode.trace_add("write", lambda *_: remplir())
        remplir()

    # -------------------------------------------------------------- relance du direct, sauvegarde
    def _relancer_direct(self, essai, serie, ident):
        """Image figée : clic sur le bouton du lecteur appris dans les Réglages. 5 essais,
        espacés de 90 s, tant que l'image reste figée. Une série s'arrête dès qu'une autre
        commence (nouvel état figé ou revenu, surveillance arrêtée)."""
        cam = self._camera(ident)
        source = str(cam["source"]) if cam else ""
        if not (cam and serie == self.relance_serie.get(ident) and self.figee.get(ident) and ident in self.surveillances
                and self.cfg["relance_auto"] and self.cfg["relance_point"] and sources.est_fenetre(source)):
            return
        try:
            sources.cliquer(source[len(sources.PREFIXE_FENETRE):], self.cfg["relance_point"])
            self.lbl_etat.configure(text=t("Image figée : relance du direct (essai {n} sur 5)", n=essai))
        except sources.DroitsInsuffisants:
            self.lbl_etat.configure(text=t("Relance impossible : le lecteur tourne en administrateur. Réglages › "
                                           "« ouvrir sans droits administrateur », puis rouvrez-le par Broutille."))
            return
        except OSError as e:
            self.lbl_etat.configure(text=t("Relance impossible : {erreur}", erreur=e))
        if essai < 5:
            self.root.after(90000, lambda: self._relancer_direct(essai + 1, serie, ident))

    def _sauvegarde_maintenant(self):
        """Sauvegarde du jour, si elle manque, dans un fil : copier les galeries prend quelques secondes.
        Une seule à la fois : deux fils écriraient la même archive temporaire."""
        destination = self.cfg["sauvegarde_dossier"]
        if destination and not self.sauvegarde_en_cours and sauvegarde.a_faire(destination):
            self.sauvegarde_en_cours = True

            def travail():
                try:
                    r = sauvegarde.sauvegarder(self.dossier, destination)
                    if r:
                        self.messages.put(("sauvegarde", tn("Sauvegarde faite : {nom} ({n} fichier)", "Sauvegarde faite : {nom} ({n} fichiers)",
                                                         r[1], nom=r[0].name)))
                except OSError as e:
                    self.messages.put(("sauvegarde", t("Sauvegarde impossible : {erreur}", erreur=e)))
                finally:
                    self.sauvegarde_en_cours = False
            threading.Thread(target=travail, daemon=True).start()

    # -------------------------------------------------------------- alertes (ntfy)
    def _maj_alertes(self):
        if self.cfg["ntfy_actif"] and self.cfg["ntfy_sujet"]:
            self.alertes = alertes.Alertes(self.dossier, self.cfg["ntfy_serveur"], self.cfg["ntfy_sujet"],
                                           sur_erreur=lambda m: self.messages.put(("message", m)))
        else:
            self.alertes = None

    def _verifier_alertes(self):
        """Absences et pertes de poids : vérifié au démarrage, puis toutes les heures."""
        a = self.alertes
        if not a:
            return

        def travail():
            try:
                journal = lire_journal(self.dossier)
            except (JournalOccupe, OSError):
                return
            envoyees = a.verifier(self.registre.copie_fiches(), journal, self.cfg["alerte_jours"])
            if envoyees:
                self.messages.put(("message", tn("{n} alerte envoyée au téléphone", "{n} alertes envoyées au téléphone",
                                                 len(envoyees))))
        threading.Thread(target=travail, daemon=True).start()

    def _alerte_figee(self, serie, ident):
        if self.alertes and self.figee.get(ident) and serie == self.relance_serie.get(ident) and ident in self.surveillances:
            nom = (self._camera(ident) or {}).get("nom", "")
            self.alertes.en_fond(self.alertes.signaler, f"figee:{ident}:{int(time.time() // 1800)}",
                                 t("Image figée : {camera}", camera=nom) if len(self.cfg["cameras"]) > 1 else t("Image figée"),
                                 t("Le direct ne bouge plus depuis 5 minutes et la relance n'a pas marché. "
                                   "Relancez le lecteur vidéo sur le PC."), 4, ("warning", "video_camera"))

    # -------------------------------------------------------------- clips verticaux
    def _fil_clips(self):
        """Fabrique les clips l'un après l'autre, en tâche de fond. Attend que le clip de la visite
        soit fermé par le moteur (il peut encore filmer une autre tortue)."""
        while True:
            ligne, auto, essais = self.file_clips.get()
            source = self.dossier / ligne["video"]
            en_cours = any(getattr(s, "video", None) is not None and getattr(s, "chemin_clip", None)
                           and Path(s.chemin_clip).name == source.name for s in list(self.surveillances.values()))
            if not source.exists() and not en_cours:          # vidéo effacée : inutile d'attendre
                if auto:
                    self.dernier_clip.pop(ligne.get("id_individu"), None)
                else:
                    self.messages.put(("message", t("Clip impossible : la vidéo de cette visite n'existe plus")))
                continue
            if en_cours and essais < 90:
                threading.Timer(20, self.file_clips.put, ((ligne, auto, essais + 1),)).start()
                continue
            try:
                taille = source.stat().st_size
                time.sleep(2)
                if source.stat().st_size != taille and essais < 90:      # encore en écriture
                    threading.Timer(20, self.file_clips.put, ((ligne, auto, essais + 1),)).start()
                    continue
                fiche = self.registre.copie_fiches().get(ligne.get("id_individu"))
                nom = fiche["nom"] if fiche else ligne["individu"]
                sous_titre = fiches.resume_identite(fiche).split("  ·  ", 1)[-1] if fiche else t(ligne.get("espece", ""))
                if fiche and fiche.get("naissance"):
                    sous_titre = f"{t(fiche['espece'])}  ·  {fiches.age_lisible(fiche['naissance'])}"
                dossier_clips = self.dossier / "partage" / "clips"
                sortie = clips.faire_clip(source, dossier_clips / clips.nom_clip(ligne, nom), nom, sous_titre,
                                          lire_positions(self.dossier).get(ligne["id_visite"], []),
                                          date_longue(ligne["date"]),
                                          decale=clips.decalage(ligne))
                clips.menage(dossier_clips)
                if not sortie and auto:
                    self.dernier_clip.pop(ligne.get("id_individu"), None)
                if sortie:
                    self.messages.put(("message", "🎬 " + t("Clip prêt : {fichier} (partage\\clips, et sur le téléphone)", fichier=sortie.name)))
                elif not auto:
                    self.messages.put(("message", t("Clip impossible : visite trop courte ou vidéo illisible")))
            except Exception as e:          # un clip raté ne doit pas arrêter le fil
                journaliser_erreur(e)
                if auto:
                    self.dernier_clip.pop(ligne.get("id_individu"), None)
                else:
                    self.messages.put(("message", t("Clip impossible : {type}", type=type(e).__name__)))

    def _demander_clip(self, ligne):
        self.file_clips.put((ligne, False, 0))
        self.lbl_etat.configure(text="🎬 " + t("Clip vertical en préparation…"))

    def _clip_auto(self, ligne):
        """Un clip par tortue reconnue toutes les 3 h au plus, pour une visite d'au moins 15 s."""
        cle = ligne.get("id_individu")
        fiche = self.registre.fiches.get(cle)
        if not (self.cfg["clips_auto"] and fiche and not fiche.get("provisoire") and ligne.get("video")
                and secondes(ligne) >= 15 and time.time() - self.dernier_clip.get(cle, 0) >= 3 * 3600):
            return
        self.dernier_clip[cle] = time.time()
        self.file_clips.put((ligne, True, 0))

    def _sauvegarde_auto(self):
        self._sauvegarde_maintenant()
        self._verifier_alertes()
        if self.root.winfo_exists():
            self.root.after(3600 * 1000, self._sauvegarde_auto)     # revérifié toutes les heures

    # -------------------------------------------------------------- fiche complète
    def fiche_tortue(self, cle, onglet=0):
        """Tout sur une tortue, modifiable à tout moment : identité (naissance, sexe…), poids,
        album photo et vues de reconnaissance, carnet de soins. Une seule fenêtre par tortue."""
        cle = self.registre.resoudre(cle)
        if not cle:
            return
        ouverte = self.fenetres_fiche.get(cle)
        if ouverte is not None and ouverte.winfo_exists():
            ouverte.deiconify()
            ouverte.lift()
            ouverte.onglets.select(onglet)
            return
        f = tk.Toplevel(self.root, bg=CARTE, padx=18, pady=14)
        self.fenetres_fiche[cle] = f
        f.transient(self.root)
        f.geometry("1000x780")
        f.minsize(880, 660)
        try:
            journal = [l for l in lire_journal(self.dossier) if l.get("id_individu") == cle]
        except (JournalOccupe, OSError):
            journal = []

        # --- bandeau : portrait, nom, identité en une ligne, chiffres clés
        tete = tk.Frame(f, bg=CARTE)
        tete.pack(fill="x", pady=(0, 12))
        cadre_portrait = tk.Frame(tete, bg=FOND, width=150, height=150, cursor="hand2")
        cadre_portrait.pack(side="left")
        cadre_portrait.pack_propagate(False)
        portrait = tk.Label(cadre_portrait, bg=FOND, fg=DISCRET, font=PT(9), cursor="hand2")
        portrait.pack(fill="both", expand=True)
        textes = tk.Frame(tete, bg=CARTE)
        textes.pack(side="left", padx=18, fill="both", expand=True)
        lbl_nom = tk.Label(textes, bg=CARTE, fg=TEXTE, font=PT(24, True))
        lbl_nom.pack(anchor="w")
        lbl_resume = tk.Label(textes, bg=CARTE, fg=AMBRE, font=PT(12, True))
        lbl_resume.pack(anchor="w")
        lbl_chiffres = tk.Label(textes, bg=CARTE, fg=DISCRET, font=PT(10), justify="left")
        lbl_chiffres.pack(anchor="w", pady=(8, 0))
        boutons = tk.Frame(tete, bg=CARTE)
        boutons.pack(side="right", anchor="n")
        ttk.Button(boutons, text="📊  " + t("Repas"), command=lambda: self.statistiques(cle)).pack(fill="x")
        ttk.Button(boutons, text="📄  " + t("PDF vétérinaire"), command=lambda: self.fiche_veterinaire(cle)).pack(fill="x", pady=(6, 0))

        def bandeau():
            fi = self.registre.copie_fiches().get(cle)
            if not fi:
                return
            f.title(t("Fiche de {nom}", nom=fi["nom"]))
            lbl_nom.configure(text=fi["nom"])
            lbl_resume.configure(text=fiches.resume_identite(fi))
            chiffres = [tn("{n} visite au journal", "{n} visites au journal", len(journal))]
            if journal:
                d = max(l["date"] for l in journal)
                chiffres.append(t("dernière le {date}", date=date_longue(d)))
            b = rapports.bilan_poids(fi.get("pesees", []))
            if b:
                chiffres.append(t("dernier poids {poids}", poids=rapports.poids_lisible(b["dernier"]["g"])))
            if fi.get("arrivee"):
                chiffres.append(t("à la maison depuis {date}", date=fiches.date_lisible(fi["arrivee"])))
            lbl_chiffres.configure(text="   ·   ".join(chiffres) + ("\n" + fi["signes"] if fi.get("signes") else ""))
            chemin = self.registre.photo_profil(cle)
            portrait.image = self._vignette(chemin, (150, 150)) if chemin else None
            portrait.configure(image=portrait.image or "", text="" if portrait.image else t("Pas encore\nde photo"))

        onglets = ttk.Notebook(f)
        onglets.pack(fill="both", expand=True)
        f.onglets = onglets
        portrait.bind("<Button-1>", lambda _e: onglets.select(2))

        # --- Identité
        ident = ttk.Frame(onglets, style="Carte.TFrame", padding=16)
        onglets.add(ident, text=t("Identité"))
        v = {c: tk.StringVar() for c in ("nom", "espece", "sexe", "naissance", "arrivee", "origine", "signes")}
        champs = ((t("Nom"), "nom", "entree"), (t("Espèce"), "espece", "especes"), (t("Sexe"), "sexe", "sexe"),
                  (t("Date de naissance"), "naissance", "date"), (t("Arrivée à la maison"), "arrivee", "date"),
                  (t("Origine"), "origine", "entree"), (t("Signes distinctifs"), "signes", "entree"))
        libelles_especes, especes = especes_affichees(self.classeur.especes)
        sexes = {t("Inconnu"): "Inconnu", t("Mâle"): "Mâle", t("Femelle"): "Femelle"}     # libellé -> valeur stockée
        aides = {}
        for rang, (texte, champ, genre) in enumerate(champs):
            ttk.Label(ident, text=texte, style="Carte.TLabel").grid(row=rang, column=0, sticky="w", pady=5, padx=(0, 14))
            if genre == "especes":
                w = ttk.Combobox(ident, textvariable=v[champ], values=libelles_especes, width=34)
            elif genre == "sexe":
                w = ttk.Combobox(ident, textvariable=v[champ], values=list(sexes), state="readonly", width=34)
            else:
                w = ttk.Entry(ident, textvariable=v[champ], width=60 if champ in ("origine", "signes") else 36)
            w.grid(row=rang, column=1, sticky="w", pady=5)
            if genre == "date":
                aides[champ] = ttk.Label(ident, style="Discret.TLabel")
                aides[champ].grid(row=rang, column=2, sticky="w", padx=(12, 0))
        ttk.Label(ident, text=t("Notes"), style="Carte.TLabel").grid(row=len(champs), column=0, sticky="nw", pady=5)
        notes = tk.Text(ident, height=7, width=72, bg=FOND, fg=TEXTE, insertbackground=TEXTE, relief="flat",
                        font=PT(10), wrap="word", padx=8, pady=6)
        notes.grid(row=len(champs), column=1, columnspan=2, sticky="nsew", pady=5)
        ident.columnconfigure(2, weight=1)
        ident.rowconfigure(len(champs), weight=1)
        bas = tk.Frame(ident, bg=CARTE)
        bas.grid(row=len(champs) + 1, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        ttk.Label(bas, text=t("Dates : 15/03/2019, 03/2019 ou simplement 2019 si l'année seule est connue."),
                  style="Discret.TLabel").pack(side="left")
        statut = ttk.Label(bas, style="Carte.TLabel", foreground=VERT)
        btn_enr = ttk.Button(bas, text=t("Enregistrer"), style="Vert.TButton")
        btn_enr.pack(side="right")
        statut.pack(side="right", padx=12)

        def remplir():
            fi = self.registre.copie_fiches()[cle]
            for c in ("nom", "origine", "signes"):
                v[c].set(fi.get(c, ""))
            v["espece"].set(t(fi["espece"]) if fi.get("espece") else "")
            v["sexe"].set(t(fi.get("sexe") or "Inconnu"))
            v["naissance"].set(fiches.date_saisie(fi.get("naissance", "")))
            v["arrivee"].set(fiches.date_saisie(fi.get("arrivee", "")))
            notes.delete("1.0", "end")
            notes.insert("1.0", fi.get("notes", ""))
            notes.edit_modified(False)

        def lire():
            """Valeurs saisies, prêtes à enregistrer ; ValueError si une date est fausse."""
            valeurs = {c: v[c].get().strip() for c in ("nom", "espece", "origine", "signes")}
            valeurs["espece"] = especes.get(valeurs["espece"], valeurs["espece"])
            sexe = sexes.get(v["sexe"].get(), v["sexe"].get())
            valeurs["sexe"] = "" if sexe == "Inconnu" else sexe
            for c, nom in (("naissance", t("naissance")), ("arrivee", t("arrivée"))):
                try:
                    valeurs[c] = fiches.lire_date_partielle(v[c].get())
                except ValueError as e:
                    raise ValueError(t("{champ} : {erreur}", champ=nom, erreur=e)) from None
            valeurs["notes"] = notes.get("1.0", "end").strip()
            return valeurs

        def modifiee():
            try:
                valeurs = lire()
            except ValueError:
                return True
            fi = self.registre.copie_fiches().get(cle, {})
            return any(valeurs[c] != fi.get(c, "") for c in valeurs)

        def aide_dates(*_):
            for c, lbl in aides.items():
                try:
                    valeur = fiches.lire_date_partielle(v[c].get())
                    texte = (fiches.age_lisible(valeur) if c == "naissance" else
                             t("depuis {duree}", duree=fiches.age_lisible(valeur))) if valeur else t("jj/mm/aaaa, mm/aaaa ou aaaa")
                    lbl.configure(text=texte, foreground=AMBRE if valeur else DISCRET)
                except ValueError as e:
                    lbl.configure(text=str(e), foreground=ROUGE)
            statut.configure(text="")

        def enregistrer(_=None):
            try:
                valeurs = lire()
            except ValueError as e:
                messagebox.showerror(t("Fiche"), t("Pas enregistré — {erreur}", erreur=e), parent=f)
                return False
            if not valeurs["nom"]:
                messagebox.showerror(t("Fiche"), t("Le nom ne peut pas être vide."), parent=f)
                return False
            fi = self.registre.copie_fiches().get(cle)
            if fi is None:                      # fusionnée ou supprimée entre-temps
                self._fermer_fiche(cle)
                return False
            renomme = (valeurs["nom"], valeurs["espece"]) != (fi["nom"], fi["espece"])
            if renomme:
                valeurs["provisoire"] = False
                erreur = None
                with VERROU_JOURNAL:            # aucune visite ne s'écrit entre le journal et la fiche
                    try:
                        renommer_dans_journal(self.dossier, cle, valeurs["nom"], valeurs["espece"])
                        self.registre.modifier(cle, **valeurs)
                    except JournalOccupe as e:
                        erreur = e
                if erreur:
                    messagebox.showerror(t("Journal"), str(erreur), parent=f)
                    return False
            else:
                self.registre.modifier(cle, **valeurs)
            notes.edit_modified(False)
            bandeau()
            if renomme:
                self.charger_historique()
            else:
                self._maj_tortues()
            statut.configure(text=t("Enregistré ✓"))
            return True

        btn_enr.configure(command=enregistrer)
        for c in ("naissance", "arrivee"):
            v[c].trace_add("write", aide_dates)
        f.bind("<Control-s>", enregistrer)

        # --- Poids
        cadre_poids = ttk.Frame(onglets, style="Carte.TFrame", padding=12)
        onglets.add(cadre_poids, text=t("Poids"))
        self._panneau_pesees(cadre_poids, cle, taille=(920, 270), apres=lambda: (bandeau(), self._maj_tortues()))

        # --- Photos : album souvenir + vues apprises par la reconnaissance
        cadre_photos = ttk.Frame(onglets, style="Carte.TFrame", padding=12)
        onglets.add(cadre_photos, text=t("Photos"))
        barre = tk.Frame(cadre_photos, bg=CARTE)
        barre.pack(fill="x")
        v_reco = tk.BooleanVar(value=False)
        btn_ajout = ttk.Button(barre, text="➕  " + t("Ajouter des photos…"), style="Vert.TButton")
        btn_ajout.pack(side="left")
        ttk.Checkbutton(barre, text=t("Les apprendre aussi pour la reconnaissance (tortue bien visible)"),
                        variable=v_reco).pack(side="left", padx=12)
        ttk.Button(barre, text="📁  " + t("Dossier"), command=lambda: os.startfile(self.registre.dossier / cle)
                   if (self.registre.dossier / cle).exists() else None).pack(side="right")
        defile = tk.Canvas(cadre_photos, bg=CARTE, highlightthickness=0)
        barre_def = ttk.Scrollbar(cadre_photos, orient="vertical", command=defile.yview)
        defile.configure(yscrollcommand=barre_def.set)
        barre_def.pack(side="right", fill="y", pady=(10, 0))
        defile.pack(fill="both", expand=True, pady=(10, 0))
        grille = tk.Frame(defile, bg=CARTE)
        defile.create_window(0, 0, window=grille, anchor="nw")
        grille.bind("<Configure>", lambda _e: defile.configure(scrollregion=defile.bbox("all")))
        defile.bind("<MouseWheel>", lambda e: defile.yview_scroll(-e.delta // 120, "units"))
        etat_photos = {"tour": 0}

        def menu_photo(ev, chemin, album):
            m = tk.Menu(f, tearoff=0)
            m.add_command(label=t("Ouvrir"), command=lambda: os.startfile(chemin))
            relatif = f"{ALBUM}/{chemin.name}" if album else chemin.name
            m.add_command(label=t("Choisir comme photo de profil"),
                          command=lambda: (self.registre.modifier(cle, profil=relatif), bandeau(), self._maj_tortues()))
            m.add_separator()
            if album:
                m.add_command(label=t("Retirer de l'album…"), command=lambda: retirer(chemin, True))
            else:
                m.add_command(label=t("Retirer de la reconnaissance (mauvaise vue)…"), command=lambda: retirer(chemin, False))
            m.tk_popup(ev.x_root, ev.y_root)

        def retirer(chemin, album):
            question = t("Retirer cette photo de l'album ? Elle est effacée du disque.") if album else \
                t("Retirer cette vue ? Broutille ne s'en servira plus pour reconnaître la tortue.")
            if not messagebox.askyesno(t("Photos"), question, parent=f):
                return
            if album:
                self.registre.retirer_album(cle, chemin.name)
            else:
                self.registre.retirer_vue(cle, chemin.name)
            bandeau()
            photos()
            self._maj_tortues()

        def photos():
            """Reconstruit les deux grilles ; les vignettes arrivent par paquets pour garder la main."""
            etat_photos["tour"] += 1
            tour = etat_photos["tour"]
            for w in grille.winfo_children():
                w.destroy()
            album = self.registre.album(cle)
            d = self.registre.dossier / cle
            vues = sorted(d.glob("*.jpg"), reverse=True) if d.is_dir() else []
            a_charger = []
            rang = 0
            for titre, liste, est_album, vide in (
                    (t("ALBUM") + f"  ({len(album)})", album, True, t("Aucune photo souvenir. « Ajouter des photos… » pour en mettre.")),
                    (t("VUES APPRISES PAR LA RECONNAISSANCE") + f"  ({len(vues)})", vues, False,
                     t("Pas encore de vue : elles s'ajoutent à chaque visite confirmée."))):
                ttk.Label(grille, text=titre, style="Titre.TLabel").grid(row=rang, column=0, columnspan=6, sticky="w",
                                                                          pady=(10 if rang else 0, 6))
                rang += 1
                if not liste:
                    ttk.Label(grille, text=vide, style="Discret.TLabel").grid(row=rang, column=0, columnspan=6, sticky="w")
                    rang += 1
                for k, chemin in enumerate(liste):
                    case = tk.Frame(grille, bg=CARTE)
                    case.grid(row=rang + k // 6, column=k % 6, padx=4, pady=4, sticky="n")
                    img = tk.Label(case, bg=FOND, width=20, height=8, cursor="hand2")
                    img.pack()
                    legende = chemin.name[:10] if chemin.name[:4].isdigit() else ""
                    if legende:
                        legende = date_longue(legende)
                    tk.Label(case, text=legende, bg=CARTE, fg=DISCRET, font=PT(8)).pack()
                    img.bind("<Double-1>", lambda _e, c=chemin: os.startfile(c))
                    img.bind("<Button-3>", lambda e, c=chemin, a=est_album: menu_photo(e, c, a))
                    for w in (case, img):
                        w.bind("<MouseWheel>", lambda e: defile.yview_scroll(-e.delta // 120, "units"))
                    a_charger.append((img, chemin))
                rang += (len(liste) + 5) // 6

            def paquet(debut=0):
                if tour != etat_photos["tour"] or not f.winfo_exists():
                    return
                for img, chemin in a_charger[debut:debut + 6]:
                    vignette = self._vignette(chemin, (140, 105))
                    if vignette and img.winfo_exists():
                        img.configure(image=vignette, width=140, height=105)
                        img.image = vignette
                if debut + 6 < len(a_charger):
                    f.after(1, paquet, debut + 6)
            paquet()

        def ajouter_photos():
            chemins = filedialog.askopenfilenames(parent=f, title=t("Photos de {nom}", nom=self.registre.fiches[cle]["nom"]),
                                                  filetypes=[(t("Photos"), "*.jpg *.jpeg *.png")])
            if not chemins:
                return
            f.configure(cursor="watch")
            f.update_idletasks()
            try:
                ecrits = self.registre.ajouter_album(cle, chemins)
            finally:
                f.configure(cursor="")
            if v_reco.get():
                if self.modeles_prets:
                    self._importer_photos(cle, chemins)
                else:
                    messagebox.showinfo(t("Photos"), t("Les modèles se chargent encore : les photos sont dans l'album, "
                                                       "réessayez la reconnaissance dans un moment."), parent=f)
            if len(ecrits) < len(chemins):
                messagebox.showwarning(t("Photos"), tn("{n} fichier illisible ignoré.", "{n} fichiers illisibles ignorés.",
                                                       len(chemins) - len(ecrits)), parent=f)
            bandeau()
            photos()
            self._maj_tortues()

        btn_ajout.configure(command=ajouter_photos)

        # --- Carnet : soins, vétérinaire, ponte…
        cadre_carnet = ttk.Frame(onglets, style="Carte.TFrame", padding=12)
        onglets.add(cadre_carnet, text=t("Carnet"))
        saisie = tk.Frame(cadre_carnet, bg=CARTE)
        saisie.pack(fill="x")
        v_date = tk.StringVar(value=datetime.now().strftime("%d/%m/%Y"))
        types_carnet = {t(x): x for x in fiches.TYPES_CARNET}      # libellé traduit -> type stocké
        v_type, v_texte = tk.StringVar(value=t(fiches.TYPES_CARNET[0])), tk.StringVar()
        for col, texte in enumerate((t("Date"), t("Type"), t("Ce qui s'est passé"))):
            ttk.Label(saisie, text=texte, style="Carte.TLabel").grid(row=0, column=col, sticky="w", padx=(0, 10))
        e_date = ttk.Entry(saisie, textvariable=v_date, width=12)
        e_date.grid(row=1, column=0, padx=(0, 10))
        ttk.Combobox(saisie, textvariable=v_type, values=list(types_carnet), width=16).grid(row=1, column=1, padx=(0, 10))
        e_texte = ttk.Entry(saisie, textvariable=v_texte, width=60)
        e_texte.grid(row=1, column=2, padx=(0, 10))
        colonnes = (("date", t("DATE"), 100), ("type", t("TYPE"), 130), ("texte", t("NOTE"), 640))
        liste = ttk.Treeview(cadre_carnet, columns=[c[0] for c in colonnes], show="headings", selectmode="browse")
        liste.configure(style="Liste.Treeview")
        for col, titre, larg in colonnes:
            liste.heading(col, text=titre, anchor="w")
            liste.column(col, width=larg, anchor="w", stretch=col == "texte")
        liste.pack(fill="both", expand=True, pady=(12, 0))
        ttk.Label(cadre_carnet, text=t("Vermifuge, visite chez le vétérinaire, hibernation, ponte, blessure… "
                                       "Clic droit sur une ligne pour la retirer."), style="Discret.TLabel").pack(anchor="w", pady=(6, 0))

        notes_affichees = {}                    # ligne -> note montrée (le téléphone peut en ajouter entre-temps)

        def carnet():
            liste.delete(*liste.get_children())
            notes_affichees.clear()
            for rang, n in reversed(list(enumerate(self.registre.carnet(cle)))):
                notes_affichees[str(rang)] = n
                liste.insert("", "end", iid=str(rang), values=(date_longue(n["date"]),
                                                               t(n["type"]) if n.get("type") else "", n["texte"]))

        def noter(_=None):
            try:
                jour = datetime.strptime(v_date.get().strip(), "%d/%m/%Y").date()
                if jour > datetime.now().date():
                    raise ValueError(t("date dans le futur"))
                genre = v_type.get().strip()
                self.registre.ajouter_note(cle, jour.isoformat(), types_carnet.get(genre, genre) or "Note", v_texte.get())
            except KeyError:
                self._fermer_fiche(cle)
                return
            except ValueError as e:
                messagebox.showerror(t("Carnet"), t("Note refusée : {erreur}\nDate au format 08/11/2026.", erreur=e), parent=f)
                return
            v_texte.set("")
            carnet()

        def menu_note(ev):
            rang = liste.identify_row(ev.y)
            if not rang:
                return
            liste.selection_set(rang)
            m = tk.Menu(f, tearoff=0)
            m.add_command(label=t("Retirer cette note"), command=lambda: (self.registre.retirer_note(cle, int(rang), notes_affichees.get(rang)), carnet()))
            m.tk_popup(ev.x_root, ev.y_root)

        ttk.Button(saisie, text=t("Noter"), style="Vert.TButton", command=noter).grid(row=1, column=3)
        for w in (e_date, e_texte):
            w.bind("<Return>", noter)
        liste.bind("<Button-3>", menu_note)

        # --- fermeture : ne pas perdre une identité modifiée
        def fermer():
            if cle in self.registre.fiches and modifiee():
                choix = messagebox.askyesnocancel(t("Fiche"), t("Enregistrer les modifications de l'identité ?"), parent=f)
                if choix is None or (choix and not enregistrer()):
                    return
            commencee = v_texte.get().strip() or getattr(cadre_poids, "v_poids", tk.StringVar()).get().strip()
            if cle in self.registre.fiches and commencee and not messagebox.askyesno(
                    t("Fiche"), t("Une note ou une pesée est tapée mais pas ajoutée. Fermer quand même ?"), parent=f):
                return
            self.fenetres_fiche.pop(cle, None)
            f.destroy()

        f.protocol("WM_DELETE_WINDOW", fermer)
        f.fermer = fermer                       # appelé aussi en quittant Broutille
        f.remplir = lambda: (remplir(), aide_dates(), bandeau(), carnet())
        f.bind("<Escape>", lambda _e: fermer())
        onglets.bind("<<NotebookTabChanged>>",
                     lambda _e: photos() if onglets.index("current") == 2 else None)
        remplir()
        aide_dates()
        bandeau()
        carnet()
        onglets.select(onglet)

    def pesees(self, cle):
        """Pesées d'une tortue : saisie (date, poids en grammes, remarque), liste et courbe."""
        fiche = self.registre.copie_fiches().get(cle)
        if not fiche:
            return
        f = tk.Toplevel(self.root, bg=CARTE, padx=16, pady=14)
        f.title(t("Poids de {nom}", nom=fiche["nom"]))
        f.transient(self.root)
        self._panneau_pesees(f, cle)

    def _panneau_pesees(self, f, cle, taille=(820, 300), apres=None):
        """Saisie, courbe et liste des pesées dans le cadre f. apres() : appelé à chaque changement."""
        saisie = tk.Frame(f, bg=CARTE)
        saisie.pack(fill="x")
        v_date = tk.StringVar(value=datetime.now().strftime("%d/%m/%Y"))
        v_poids, v_note = tk.StringVar(), tk.StringVar()
        f.v_poids = v_poids                     # la fiche vérifie à la fermeture qu'aucune pesée n'est en suspens
        for col, (texte, var, larg) in enumerate(((t("Date"), v_date, 12), (t("Poids (g)"), v_poids, 10), (t("Remarque"), v_note, 30))):
            ttk.Label(saisie, text=texte, style="Carte.TLabel").grid(row=0, column=col, sticky="w", padx=(0, 10))
            e = ttk.Entry(saisie, textvariable=var, width=larg)
            e.grid(row=1, column=col, sticky="w", padx=(0, 10))
            if var is v_poids:
                e.focus_set()
        graphe = tk.Label(f, bg=CARTE)
        graphe.pack(fill="x", pady=(14, 8))
        resume = ttk.Label(f, style="Carte.TLabel")
        resume.pack(anchor="w")
        colonnes = (("date", t("DATE"), 110), ("poids", t("POIDS"), 100), ("ecart", t("ÉCART"), 160), ("note", t("REMARQUE"), 340))
        liste = ttk.Treeview(f, columns=[c[0] for c in colonnes], show="headings", height=7, selectmode="browse",
                             style="Liste.Treeview")
        for col, titre, larg in colonnes:
            liste.heading(col, text=titre, anchor="w")
            liste.column(col, width=larg, anchor="w")
        liste.pack(fill="both", expand=True, pady=(8, 0))
        ttk.Label(f, text=t("Clic droit sur une pesée pour la retirer. Pesez à jeun, de préférence à la même heure."),
                  style="Discret.TLabel").pack(anchor="w", pady=(6, 0))

        def rafraichir():
            pesees = self.registre.pesees(cle)
            img = rapports.graphique_poids(pesees, t("Courbe de poids"), taille, fond=(27, 33, 25), encre=(233, 238, 227),
                                           discret=(151, 163, 141), filet=(45, 55, 41), trait=(127, 185, 80))
            graphe.image = ImageTk.PhotoImage(img)
            graphe.configure(image=graphe.image)
            liste.delete(*liste.get_children())
            precedent = None
            lignes = []
            for p in pesees:
                ecart = rapports.ecart_lisible({"g": p["g"] - precedent, "pct": 100 * (p["g"] - precedent) / precedent}) \
                    if precedent else "—"
                lignes.append((p["date"], (date_longue(p["date"]),
                                           rapports.poids_lisible(p["g"]), ecart, p.get("note", ""))))
                precedent = p["g"]
            for jour, valeurs in reversed(lignes):
                liste.insert("", "end", iid=jour, values=valeurs)
            b = rapports.bilan_poids(pesees)
            if b:
                texte = t("Dernier poids : {poids}   ·   sur 30 jours : {mois}   ·   sur un an : {an}",
                          poids=rapports.poids_lisible(b["dernier"]["g"]), mois=rapports.ecart_lisible(b["mois"]),
                          an=rapports.ecart_lisible(b["an"]))
                resume.configure(text=texte + ("   ·   " + t("PERTE DE 10 % OU PLUS") if b["alerte"] else ""),
                                 foreground=ROUGE if b["alerte"] else TEXTE)
            else:
                resume.configure(text=t("Aucune pesée pour l'instant."), foreground=DISCRET)
            if apres:
                apres()

        def ajouter(_=None):
            try:
                jour = datetime.strptime(v_date.get().strip(), "%d/%m/%Y").date()
                grammes = float(v_poids.get().replace(",", ".").replace(" ", "").lower().removesuffix("g"))
                if jour > datetime.now().date():
                    raise ValueError(t("date dans le futur"))
                self.registre.ajouter_pesee(cle, jour.isoformat(), grammes, v_note.get())
            except KeyError:                    # tortue fusionnée ou supprimée pendant la saisie
                if f.winfo_toplevel() is not self.root:
                    f.winfo_toplevel().destroy()
                return
            except ValueError as e:
                messagebox.showerror(t("Pesée"), t("Pesée refusée : {erreur}\nDate au format 05/11/2026, poids en grammes (ex. 1250).", erreur=e),
                                     parent=f.winfo_toplevel())
                return
            v_poids.set("")
            v_note.set("")
            rafraichir()

        def menu_pesee(ev):
            jour = liste.identify_row(ev.y)
            if not jour:
                return
            liste.selection_set(jour)
            m = tk.Menu(f, tearoff=0)
            m.add_command(label=t("Retirer cette pesée"), command=lambda: (self.registre.retirer_pesee(cle, jour), rafraichir()))
            m.tk_popup(ev.x_root, ev.y_root)

        ttk.Button(saisie, text=t("Ajouter"), style="Vert.TButton", command=ajouter).grid(row=1, column=3, sticky="w")
        for enfant in saisie.winfo_children():
            if isinstance(enfant, ttk.Entry):
                enfant.bind("<Return>", ajouter)
        liste.bind("<Button-3>", menu_pesee)
        rafraichir()

    def fiche_veterinaire(self, cle):
        fiche = self.registre.copie_fiches().get(cle)
        if not fiche:
            return
        chemin = filedialog.asksaveasfilename(title=t("Fiche pour le vétérinaire"), defaultextension=".pdf",
                                              initialdir=self.dossier, initialfile=rapports.nom_fichier_fiche(fiche),
                                              filetypes=[("PDF", "*.pdf")])
        if not chemin:
            return
        try:
            journal = lire_journal(self.dossier)
            rapports.fiche_veterinaire(chemin, self.dossier, fiche, cle, journal, galerie=self.registre.dossier / cle)
        except PermissionError:
            messagebox.showerror(t("Fiche"), t("Le fichier est ouvert dans un autre programme : fermez-le et recommencez."))
            return
        except (JournalOccupe, OSError) as e:
            messagebox.showerror(t("Fiche"), t("Fiche impossible : {erreur}", erreur=e))
            return
        os.startfile(chemin)

    def quitter(self):
        for cle, f in list(self.fenetres_fiche.items()):
            if f.winfo_exists() and hasattr(f, "fermer"):
                f.fermer()
                if f.winfo_exists():            # « Annuler » : on ne quitte pas
                    return
        self._ecrire_config()
        if self.serveur_web:
            self.serveur_web.arreter()
            self.serveur_web = None
        if not self.surveillances:
            self.root.destroy()
            return
        # la fenêtre attend la fin de chaque surveillance : sinon le clip en cours serait illisible
        # et la visite perdue. Filet d'une minute si une source ne répond plus.
        self.fermeture = True
        self.root.withdraw()
        for s in list(self.surveillances.values()):
            s.arreter()
        self.root.after(60000, self.root.destroy)


def journaliser_erreur(e):
    try:
        with open(Path.home() / ".broutille_erreurs.log", "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\n{''.join(traceback.format_exception(e))}\n")
    except OSError:
        pass


def main():
    root = tk.Tk()
    # pythonw n'a pas de console : une erreur au démarrage doit se voir
    root.report_callback_exception = lambda _t, e, _tb: journaliser_erreur(e)
    try:
        App(root)
    except RegistreIllisible as e:
        root.withdraw()
        messagebox.showerror("Broutille", t("{erreur}\nRestaurez registre.bak ou contactez le support du projet.", erreur=e))
        return
    except Exception as e:
        journaliser_erreur(e)
        root.withdraw()
        messagebox.showerror("Broutille", t("Démarrage impossible : {type} : {erreur}\nDétails dans {fichier}",
                                            type=type(e).__name__, erreur=e, fichier=Path.home() / ".broutille_erreurs.log"))
        return
    root.mainloop()


if __name__ == "__main__":
    main()
