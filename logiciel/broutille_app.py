"""
Broutille — la mangeoire qui reconnaît ses tortues (application de bureau).

Vidéo en direct (webcam, fenêtre ouverte ou flux Internet), enregistrement automatique des
visites, espèce et individu de chaque tortue, fiches des tortues (renommer, fusionner, ajouter des photos), corrections dont l'application
apprend aussitôt, temps de repas du jour et historique avec vignettes.
"""

import json
import os
import queue
import threading
import time
import tkinter as tk
import traceback
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import cv2
from PIL import Image, ImageDraw, ImageFont, ImageTk

import sources
import vision
from broutille_cam import (INCONNUE, MARGE_INDIVIDU, PAS_UNE_TORTUE, SEUIL_INDIVIDU, JournalOccupe, Registre,
                           RegistreIllisible, Surveillance, corriger_visite, inscrire_photos, lire_journal,
                           renommer_dans_journal, secondes)

ICI = Path(__file__).resolve().parent
if (ICI / "hf_cache").is_dir():     # version installée : modèles livrés avec l'installateur
    os.environ.setdefault("HF_HOME", str(ICI / "hf_cache"))
CONFIG = Path.home() / ".broutille.json"
DEFAUTS = {
    "source": "0",
    "dossier": str(Path.home() / "Videos" / "Broutille"),
    "seuil": SEUIL_INDIVIDU,
    "reconnaissance": True,
    "creer_nouvelles": False,   # sinon une tortue vue sous un angle nouveau créerait une fausse fiche
    "alerte_jours": 3,          # tortue signalée si elle n'est pas venue depuis ce nombre de jours
    "menage_jours": 60,
    "menage_go": 20,
    "demarrage_auto": False,
    "especes_actives": [e[1] for e in vision.ESPECES_DEFAUT[:2]],   # noms scientifiques
    "zones": {},                # source -> partie de l'image à garder (x0, y0, x1, y1 en fractions)
}

# Thème
FOND, CARTE, BORD = "#10140f", "#1b2119", "#2d3729"
TEXTE, DISCRET = "#e9eee3", "#97a38d"
VERT, ROUGE, BLEU, AMBRE = "#7fb950", "#f85149", "#58a6ff", "#d9a441"
COULEURS = ["#7fb950", "#d9a441", "#58a6ff", "#f778ba", "#a371f7", "#ffa657", "#79c0ff", "#7ee787"]


def police(taille, gras=False):
    for nom in (["seguisb.ttf", "segoeuib.ttf"] if gras else ["segoeui.ttf"]):
        try:
            return ImageFont.truetype(nom, taille)
        except OSError:
            pass
    return ImageFont.load_default()


def libelle_source(source):
    source = str(source)
    if source.isdigit():
        return f"Webcam {source}"
    return f"Fenêtre : {source[len(sources.PREFIXE_FENETRE):]}" if sources.est_fenetre(source) else source


def source_depuis_saisie(saisie):
    saisie = saisie.strip()
    if saisie.startswith("Webcam "):
        return saisie[len("Webcam "):]
    return sources.PREFIXE_FENETRE + saisie[len("Fenêtre : "):] if saisie.startswith("Fenêtre : ") else saisie


def duree_lisible(secondes):
    secondes = int(secondes)
    return f"{secondes} s" if secondes < 60 else f"{secondes // 60} min" if secondes < 3600 else f"{secondes // 3600} h {secondes % 3600 // 60:02d}"


class App:
    def __init__(self, root):
        self.root = root
        self.cfg = {**DEFAUTS, **self._lire_config()}
        self.surveillance = None
        self.messages = queue.Queue()
        self.verrou = threading.Lock()
        self.derniere_image = None
        self.image_affichee = None
        self.vignettes = {}
        self.vignettes_tortues = {}
        self.photo_visite = None
        self.modeles_prets = False
        self.fermeture = False
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
        if self.cfg["demarrage_auto"]:
            self.root.after(500, self.demarrer)

    # -------------------------------------------------------------- config
    def _lire_config(self):
        try:
            return json.loads(CONFIG.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _ecrire_config(self):
        try:
            CONFIG.write_text(json.dumps(self.cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    @property
    def dossier(self):
        return Path(self.cfg["dossier"])

    def _precharger(self):
        try:
            self.messages.put(("message", "Chargement des modèles…"))
            self.detecteur.charger()
            self.classeur.charger()
            self.registre.descripteur.charger()
            self.registre.preparer()
            self.modeles_prets = True
            self.messages.put(("tortues", None))
            self.messages.put(("modele", "GPU" if vision.appareil() == "cuda" else "Processeur"))
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
        s.configure(".", background=FOND, foreground=TEXTE, font=("Segoe UI", 10), bordercolor=BORD,
                    lightcolor=CARTE, darkcolor=CARTE, troughcolor=BORD)
        s.configure("Carte.TFrame", background=CARTE)
        s.configure("TLabel", background=FOND, foreground=TEXTE)
        s.configure("Carte.TLabel", background=CARTE)
        s.configure("Discret.TLabel", background=CARTE, foreground=DISCRET)
        s.configure("Titre.TLabel", background=CARTE, foreground=DISCRET, font=("Segoe UI Semibold", 10))
        s.configure("TButton", background=CARTE, foreground=TEXTE, borderwidth=1, focusthickness=0, padding=(14, 8),
                    font=("Segoe UI Semibold", 10))
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
                    font=("Segoe UI", 10))
        s.configure("Treeview.Heading", background=CARTE, foreground=DISCRET, borderwidth=0, font=("Segoe UI Semibold", 9))
        s.map("Treeview", background=[("selected", "#34452c")])
        s.configure("TCheckbutton", background=CARTE, foreground=TEXTE)
        s.map("TCheckbutton", background=[("active", CARTE)])
        s.configure("Horizontal.TScale", background=CARTE, troughcolor=BORD)
        s.configure("Vertical.TScrollbar", background=CARTE, troughcolor=FOND, arrowcolor=DISCRET)
        s.configure("TNotebook", background=CARTE, borderwidth=0, tabmargins=0)
        s.configure("TNotebook.Tab", background=CARTE, foreground=DISCRET, padding=(14, 6),
                    font=("Segoe UI Semibold", 10), borderwidth=0)
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
        tk.Label(titres, text="Broutille", bg=FOND, fg=TEXTE, font=("Segoe UI Semibold", 20)).pack(anchor="w")
        tk.Label(titres, text="la mangeoire qui reconnaît ses tortues", bg=FOND, fg=DISCRET,
                 font=("Segoe UI", 10)).pack(anchor="w")
        self.pastille = tk.Label(tete, text="●  En veille", bg=CARTE, fg=DISCRET, font=("Segoe UI Semibold", 11), padx=14, pady=6)
        self.pastille.pack(side="right")
        self.lbl_modele = tk.Label(tete, text="Modèles : chargement…", bg=FOND, fg=DISCRET, font=("Segoe UI", 10))
        self.lbl_modele.pack(side="right", padx=16)

        barre = tk.Frame(r, bg=FOND)
        barre.grid(row=1, column=0, sticky="ew", padx=20, pady=(4, 10))
        tk.Label(barre, text="Caméra", bg=FOND, fg=DISCRET).pack(side="left")
        self.var_source = tk.StringVar(value=libelle_source(self.cfg["source"]))
        self.cb_source = ttk.Combobox(barre, textvariable=self.var_source, values=[f"Webcam {i}" for i in range(4)], width=30)
        self.cb_source.pack(side="left", padx=(8, 4))
        ttk.Button(barre, text="🪟  Fenêtre", command=self.choisir_fenetre).pack(side="left", padx=(0, 4))
        ttk.Button(barre, text="🎞  Vidéo", command=self._choisir_fichier).pack(side="left", padx=(0, 4))
        ttk.Button(barre, text="⛶  Cadrer", command=self.cadrer).pack(side="left", padx=(0, 12))
        self.btn_demarrer = ttk.Button(barre, text="▶  Démarrer", style="Vert.TButton", command=self.basculer)
        self.btn_demarrer.pack(side="left")
        ttk.Button(barre, text="🐢  Ajouter une tortue", command=self.ajouter_tortue).pack(side="left", padx=(8, 0))
        ttk.Button(barre, text="📁  Dossier", command=lambda: os.startfile(self.dossier) if self.dossier.exists() else None
                   ).pack(side="left", padx=(8, 0))
        ttk.Button(barre, text="📊  Statistiques", command=self.statistiques).pack(side="left", padx=(8, 0))
        ttk.Button(barre, text="⚙  Réglages", command=self.reglages).pack(side="right")

        corps = tk.Frame(r, bg=FOND)
        corps.grid(row=2, column=0, sticky="nsew", padx=20)
        corps.columnconfigure(0, weight=1)
        corps.rowconfigure(0, weight=1)
        cadre_video = tk.Frame(corps, bg="#000000", highlightthickness=1, highlightbackground=BORD)
        cadre_video.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self.video = tk.Label(cadre_video, bg="#070a06")
        self.video.pack(fill="both", expand=True)
        self.video.bind("<Configure>", lambda e: self._afficher_vide() if self.surveillance is None else None)

        droite = tk.Frame(corps, bg=FOND, width=400)
        droite.grid(row=0, column=1, sticky="ns")
        droite.grid_propagate(False)
        droite.columnconfigure(0, weight=1)
        droite.rowconfigure(2, weight=1)

        c = self._carte(droite, "Dernière visite", row=0, column=0, sticky="ew", pady=(0, 12))
        cadre_photo = tk.Frame(c, bg="#0c100a", width=370, height=150)
        cadre_photo.pack(fill="x")
        cadre_photo.pack_propagate(False)
        self.lbl_photo = tk.Label(cadre_photo, bg="#0c100a")
        self.lbl_photo.pack(fill="both", expand=True)
        self.lbl_individu = ttk.Label(c, text="—", style="Carte.TLabel", font=("Segoe UI Semibold", 16))
        self.lbl_individu.pack(anchor="w", pady=(10, 0))
        self.lbl_details = ttk.Label(c, text="Aucune visite pour l'instant", style="Discret.TLabel", wraplength=360)
        self.lbl_details.pack(anchor="w")

        c = self._carte(droite, "Repas d'aujourd'hui", row=1, column=0, sticky="ew", pady=(0, 12))
        self.stats = tk.Canvas(c, bg=CARTE, height=30, highlightthickness=0)
        self.stats.pack(fill="x")

        c = self._carte(droite, None, row=2, column=0, sticky="nsew")
        onglets = ttk.Notebook(c)
        onglets.pack(fill="both", expand=True)
        cadre = ttk.Frame(onglets, style="Carte.TFrame")
        onglets.add(cadre, text="Visites")
        self.arbre = self._arbre(cadre, (("quand", "HEURE", 74), ("individu", "TORTUE", 118), ("duree", "DURÉE", 56)))
        self.arbre.bind("<<TreeviewSelect>>", self._selection)
        self.arbre.bind("<Double-1>", self._ouvrir_video)
        self.arbre.bind("<Button-3>", self._menu_visite)
        self.lignes = {}
        cadre = ttk.Frame(onglets, style="Carte.TFrame")
        onglets.add(cadre, text="Mes tortues")
        self.arbre_t = self._arbre(cadre, (("nom", "NOM", 122), ("visites", "VISITES", 54), ("vue", "VUE", 72)))
        self.arbre_t.tag_configure("provisoire", foreground=AMBRE)
        self.arbre_t.tag_configure("absente", foreground=ROUGE)
        self.arbre_t.bind("<Button-3>", self._menu_tortue)
        self.arbre_t.bind("<Double-1>", self._ouvrir_galerie)
        ttk.Label(c, text="Clic droit : confirmer ou corriger une visite, nommer une tortue", style="Discret.TLabel",
                  font=("Segoe UI", 9)).pack(anchor="w", pady=(6, 0))

        pied = ttk.Frame(r, style="Carte.TFrame", padding=(20, 10))
        pied.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        ttk.Label(pied, text="Exigence pour nommer une tortue", style="Discret.TLabel").pack(side="left")
        self.var_seuil = tk.DoubleVar(value=self.cfg["seuil"] * 100)
        ttk.Scale(pied, from_=40, to=95, variable=self.var_seuil, length=170,
                  command=lambda v: self._maj_reglages()).pack(side="left", padx=(8, 4))
        self.lbl_seuil = ttk.Label(pied, width=5, style="Carte.TLabel")
        self.lbl_seuil.pack(side="left", padx=(0, 24))
        self.var_reco = tk.BooleanVar(value=self.cfg["reconnaissance"])
        ttk.Checkbutton(pied, text="Reconnaître les tortues", variable=self.var_reco,
                        command=self._maj_reglages).pack(side="left", padx=(0, 16))
        self.var_nouvelles = tk.BooleanVar(value=self.cfg["creer_nouvelles"])
        ttk.Checkbutton(pied, text="Créer une fiche pour une tortue inconnue", variable=self.var_nouvelles,
                        command=self._maj_reglages).pack(side="left")
        self.lbl_etat = ttk.Label(pied, text="Prêt", style="Discret.TLabel", width=46, anchor="e")
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

    def _choisir_fichier(self):
        chemin = filedialog.askopenfilename(title="Analyser une vidéo", filetypes=[("Vidéos", "*.mp4 *.avi *.mov *.mkv")])
        if chemin:
            self.var_source.set(chemin)

    def _maj_reglages(self):
        self.cfg["seuil"] = round(self.var_seuil.get() / 100, 2)
        self.cfg["reconnaissance"] = self.var_reco.get()
        self.cfg["creer_nouvelles"] = self.var_nouvelles.get()
        self.lbl_seuil.configure(text=f"{self.cfg['seuil']:.0%}")
        s = self.surveillance
        if s:
            s.seuil, s.reconnaissance_active, s.creer_nouvelles = (self.cfg["seuil"], self.cfg["reconnaissance"],
                                                                   self.cfg["creer_nouvelles"])

    # -------------------------------------------------------------- réglages
    def reglages(self):
        f = tk.Toplevel(self.root, bg=CARTE, padx=20, pady=16)
        f.title("Réglages")
        f.transient(self.root)
        f.columnconfigure(1, weight=1)

        def ligne(rangee, texte, variable, largeur=44):
            ttk.Label(f, text=texte, style="Carte.TLabel").grid(row=rangee, column=0, sticky="w", pady=5, padx=(0, 14))
            e = ttk.Entry(f, textvariable=variable, width=largeur)
            e.grid(row=rangee, column=1, sticky="ew")
            return e

        v_dossier = tk.StringVar(value=self.cfg["dossier"])
        ligne(0, "Dossier des visites", v_dossier)
        ttk.Button(f, text="…", width=3, command=lambda: v_dossier.set(filedialog.askdirectory(parent=f) or v_dossier.get())
                   ).grid(row=0, column=2, padx=(6, 0))
        v_alerte = tk.StringVar(value=str(self.cfg["alerte_jours"]))
        ligne(1, "Signaler une tortue absente depuis (jours)", v_alerte, 8)
        v_jours = tk.StringVar(value=str(self.cfg["menage_jours"]))
        ligne(2, "Effacer les clips après (jours, 0 = jamais)", v_jours, 8)
        v_go = tk.StringVar(value=str(self.cfg["menage_go"]))
        ligne(3, "Taille maximale du dossier (Go, 0 = sans limite)", v_go, 8)
        v_auto = tk.BooleanVar(value=self.cfg["demarrage_auto"])
        ttk.Checkbutton(f, text="Démarrer la surveillance à l'ouverture", variable=v_auto).grid(row=4, column=0, columnspan=2, sticky="w", pady=6)
        ttk.Label(f, text="Espèces présentes à la mangeoire (moins il y en a, moins Broutille se trompe)",
                  style="Discret.TLabel").grid(row=5, column=0, columnspan=3, sticky="w", pady=(10, 4))
        cadre_especes = ttk.Frame(f, style="Carte.TFrame")
        cadre_especes.grid(row=6, column=0, columnspan=3, sticky="w")
        coches = {}
        for i, (nom, sci, _en) in enumerate(vision.ESPECES_DEFAUT):
            coches[sci] = tk.BooleanVar(value=sci in self.cfg["especes_actives"])
            ttk.Checkbutton(cadre_especes, text=nom, variable=coches[sci]).grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 18))

        def enregistrer():
            try:
                alerte, jours, go = int(v_alerte.get()), int(v_jours.get()), float(v_go.get())
            except ValueError:
                messagebox.showerror("Réglages", "Les jours et la taille doivent être des nombres.", parent=f)
                return
            actives = [s for s, c in coches.items() if c.get()]
            if len(actives) < 2:
                messagebox.showerror("Réglages", "Cochez au moins deux espèces.", parent=f)
                return
            nouveau_dossier = v_dossier.get() != self.cfg["dossier"]
            if nouveau_dossier and self.surveillance:
                messagebox.showerror("Réglages", "Arrêtez la surveillance avant de changer de dossier.", parent=f)
                return
            change = actives != self.cfg["especes_actives"]
            self.cfg.update(dossier=v_dossier.get(), alerte_jours=alerte, menage_jours=jours, menage_go=go,
                            demarrage_auto=v_auto.get(), especes_actives=actives)
            self._ecrire_config()
            f.destroy()
            if nouveau_dossier:
                self.registre = Registre(self.dossier, self.registre.descripteur)
                threading.Thread(target=self._precharger, daemon=True).start()
            if change:
                self.lbl_etat.configure(text="Réglage enregistré : relancez Broutille pour l'appliquer")
            self.charger_historique()

        def oublier():
            if messagebox.askyesno("Pas une tortue", "Oublier tous les « Pas une tortue » ?", parent=f):
                self.registre.oublier_rejets()
                btn_rejets.configure(text="Oublier les « Pas une tortue » (0)", state="disabled")

        n_rejets = self.registre.nombre_rejets()
        btn_rejets = ttk.Button(f, text=f"Oublier les « Pas une tortue » ({n_rejets})", command=oublier,
                                state="normal" if n_rejets else "disabled")
        btn_rejets.grid(row=7, column=0, sticky="w", pady=(14, 0))

        ttk.Button(f, text="Enregistrer", style="Vert.TButton", command=enregistrer).grid(row=7, column=1, columnspan=2, sticky="e", pady=(14, 0))

    # -------------------------------------------------------------- surveillance
    def basculer(self):
        self.arreter() if self.surveillance else self.demarrer()

    def demarrer(self):
        source = source_depuis_saisie(self.var_source.get())
        self.cfg["source"] = source
        self._ecrire_config()
        self.surveillance = Surveillance(
            source, self.dossier, registre=self.registre, detecteur=self.detecteur, classeur=self.classeur,
            seuil=self.cfg["seuil"], marge=MARGE_INDIVIDU, reconnaissance=self.cfg["reconnaissance"],
            creer_nouvelles=self.cfg["creer_nouvelles"], menage_jours=self.cfg["menage_jours"],
            menage_go=self.cfg["menage_go"], temps_reel=True, zone=self.cfg["zones"].get(source),
            sur_image=self._sur_image, sur_visite=lambda l: self.messages.put(("visite", l)),
            sur_message=lambda m: self.messages.put(("message", m)))
        self.btn_demarrer.configure(text="■  Arrêter", style="Rouge.TButton")
        threading.Thread(target=self._executer, args=(self.surveillance,), daemon=True).start()

    def _executer(self, surveillance):
        try:
            ok = surveillance.executer()
        except Exception as e:
            self.messages.put(("message", f"Erreur : {type(e).__name__} : {e}"))
            ok = False
        self.messages.put(("fin", ok))

    def arreter(self):
        if self.surveillance:
            self.btn_demarrer.configure(state="disabled", text="Arrêt…")
            self.surveillance.arreter()

    def _sur_image(self, image, etat):
        with self.verrou:
            self.derniere_image = (image, etat)

    def _boucle(self):
        try:
            self._traiter_messages()
            with self.verrou:
                donnees, self.derniere_image = self.derniere_image, None
            if donnees and self.surveillance:
                image, etat = donnees
                self._afficher_image(image, etat)
                n = etat["presence"]
                self.pastille.configure(text=f"●  {n} tortue{'s' if n > 1 else ''} à table" if n else "●  Surveillance",
                                        fg=ROUGE if n else VERT)
        except Exception as e:      # une erreur d'affichage ne doit pas figer l'interface pour la session
            journaliser_erreur(e)
            self.lbl_etat.configure(text=f"Erreur d'affichage : {type(e).__name__}")
        finally:
            if self.root.winfo_exists():
                self.root.after(30, self._boucle)

    def _traiter_messages(self):
        while not self.messages.empty():
            genre, contenu = self.messages.get()
            if genre == "message":
                self.lbl_etat.configure(text=contenu)
            elif genre == "modele":
                self.lbl_modele.configure(text=f"Modèles prêts ({contenu})")
                self.lbl_etat.configure(text="Prêt")
            elif genre == "erreur_modele":
                self.lbl_modele.configure(text="Modèles indisponibles", fg=ROUGE)
                self.lbl_etat.configure(text=contenu)
            elif genre == "tortues":
                self._maj_tortues()
            elif genre == "visite":
                self._ajouter_visite(contenu, True)
                self._afficher_visite(contenu)
                self._maj_stats()
                self._maj_tortues()
            elif genre == "corrige":
                self.charger_historique()
                self.lbl_etat.configure(text=contenu)
            elif genre == "cadrage":
                self._fenetre_cadrage(*contenu)
            elif genre == "fin":
                if self.fermeture:
                    self.root.destroy()
                    return
                if not contenu:
                    messagebox.showerror("Source vidéo", self.lbl_etat.cget("text"))
                self.surveillance, self.derniere_image = None, None
                self.btn_demarrer.configure(text="▶  Démarrer", style="Vert.TButton", state="normal")
                self.pastille.configure(text="●  En veille", fg=DISCRET)
                self._afficher_vide()

    # -------------------------------------------------------------- sources
    def choisir_fenetre(self):
        f = tk.Toplevel(self.root, bg=CARTE, padx=16, pady=14)
        f.title("Filmer une fenêtre ouverte")
        f.transient(self.root)
        ttk.Label(f, text="La fenêtre doit rester ouverte, pas réduite.\nSi l'image est noire, gardez-la visible à l'écran.",
                  style="Discret.TLabel").pack(anchor="w", pady=(0, 8))
        liste = tk.Listbox(f, width=64, height=12, bg=FOND, fg=TEXTE, selectbackground=VERT, relief="flat", font=("Segoe UI", 10))
        liste.pack(fill="both", expand=True)
        titres = sorted({t for t, _h in sources.lister_fenetres() if t not in (self.root.title(), f.title())})
        for titre in titres:
            liste.insert("end", titre)

        def valider(_=None):
            if liste.curselection():
                self.var_source.set(libelle_source(sources.PREFIXE_FENETRE + titres[liste.curselection()[0]]))
                f.destroy()

        liste.bind("<Double-1>", valider)
        ttk.Button(f, text="Choisir", style="Vert.TButton", command=valider).pack(anchor="e", pady=(10, 0))

    def cadrer(self):
        """Une fenêtre comme EZVIZ Studio a des boutons et parfois plusieurs caméras : on garde une zone."""
        if self.surveillance:
            messagebox.showinfo("Cadrer", "Arrêtez d'abord la surveillance.")
            return
        source = sources.source_depuis_texte(source_depuis_saisie(self.var_source.get()))

        def travail():
            camera, image = sources.ouvrir_source(source)
            if camera is not None:
                camera.release()
                self.messages.put(("cadrage", (str(source), image)))
            else:
                self.messages.put(("message", f"Aucune image de : {sources.masquer(source)}"))

        self.lbl_etat.configure(text="Lecture de la source…")
        threading.Thread(target=travail, daemon=True).start()

    def _fenetre_cadrage(self, cle, image):
        h, w = image.shape[:2]
        e = min(1100 / w, 700 / h, 1.0)
        f = tk.Toplevel(self.root, bg=CARTE, padx=12, pady=12)
        f.title("Cadrer : tracez la zone de la mangeoire à la souris")
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
            self.lbl_etat.configure(text="Cadrage enregistré pour cette source")
            f.destroy()

        def valider():
            x0, y0, x1, y1 = c.coords(cadre)
            x0, x1 = sorted((max(0, x0), min(w * e, x1)))
            y0, y1 = sorted((max(0, y0), min(h * e, y1)))
            if x1 - x0 < 64 or y1 - y0 < 64:
                messagebox.showerror("Cadrer", "Zone trop petite.", parent=f)
                return
            retenir([x0 / (w * e), y0 / (h * e), x1 / (w * e), y1 / (h * e)])

        bas = tk.Frame(f, bg=CARTE)
        bas.pack(fill="x", pady=(10, 0))
        ttk.Button(bas, text="Toute l'image", command=lambda: retenir(None)).pack(side="left")
        ttk.Button(bas, text="Valider la zone", style="Vert.TButton", command=valider).pack(side="right")

    def _afficher_image(self, image, etat):
        lw, lh = max(self.video.winfo_width(), 320), max(self.video.winfo_height(), 240)
        h, w = image.shape[:2]
        e = min(lw / w, lh / h)
        nw, nh = int(w * e), int(h * e)
        img = Image.fromarray(cv2.cvtColor(cv2.resize(image, (nw, nh)), cv2.COLOR_BGR2RGB)).convert("RGBA")
        calque = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(calque)
        for boite, texte in etat["tortues"]:
            x, y, bw, bh = (int(v * e) for v in boite)
            d.rounded_rectangle([x, y, x + bw, y + bh], radius=10, outline=(217, 164, 65, 255), width=4)
            tw = d.textlength(texte, font=self.f_tag)
            yt = max(0, y - 40)
            d.rounded_rectangle([x, yt, x + tw + 24, yt + 36], radius=10, fill=(16, 20, 15, 215))
            d.text((x + 12, yt + 4), texte, font=self.f_tag, fill=(233, 238, 227, 255))
        if etat["enregistrement"]:
            d.rounded_rectangle([16, 16, 150, 52], radius=18, fill=(248, 81, 73, 230))
            d.ellipse([28, 28, 40, 40], fill="white")
            d.text((50, 22), f"REC {int(etat['duree']) // 60:02d}:{int(etat['duree']) % 60:02d}", font=self.f_petit, fill="white")
        d.text((nw - 90, 20), f"{etat['fps']:.0f} i/s", font=self.f_petit, fill=(200, 210, 200, 200))
        self.image_affichee = ImageTk.PhotoImage(Image.alpha_composite(img, calque).convert("RGB"))
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
        t = "Cliquez sur « Démarrer » pour surveiller la mangeoire"
        d.text(((lw - d.textlength(t, font=self.f_vide)) / 2, lh / 2 + 10), t, font=self.f_vide, fill=(151, 163, 141))
        self.image_affichee = ImageTk.PhotoImage(img)
        self.video.configure(image=self.image_affichee)

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
        self._maj_stats()
        self._maj_tortues()

    def _vignette(self, chemin, taille):
        try:
            img = Image.open(chemin)
            img.thumbnail(taille)
            return ImageTk.PhotoImage(img)
        except OSError:
            return None

    def _ajouter_visite(self, ligne, en_tete):
        aujourd_hui = datetime.now().strftime("%Y-%m-%d")
        quand = ligne["heure"][:5] if ligne["date"] == aujourd_hui else f"{ligne['date'][8:]}/{ligne['date'][5:7]} {ligne['heure'][:5]}"
        vignette = self._vignette(self.dossier / ligne["photo"], (72, 48)) if ligne.get("photo") else None
        iid = self.arbre.insert("", 0 if en_tete else "end", text="", image=vignette or "",
                                values=(quand, f"{ligne['proposition']} ?" if ligne.get("proposition") else ligne["individu"],
                                        duree_lisible(secondes(ligne))))
        if vignette:
            self.vignettes[iid] = vignette
        self.lignes[iid] = ligne

    def _afficher_visite(self, ligne):
        self.photo_visite = self._vignette(self.dossier / ligne["photo"], (370, 150)) if ligne.get("photo") else None
        self.lbl_photo.configure(image=self.photo_visite or "")
        nom = f"{ligne['proposition']} ?" if ligne.get("proposition") else ligne["individu"]
        self.lbl_individu.configure(text=nom, foreground=DISCRET if ligne["individu"] == INCONNUE else TEXTE)
        quand = f"{ligne['date'][8:]}/{ligne['date'][5:7]} à {ligne['heure'][:5]}"
        origine = {"manuel": "  ·  corrigée à la main", "nouvelle": "  ·  nouvelle tortue"}.get(ligne.get("source"), "")
        self.lbl_details.configure(text=f"{ligne['espece']}  ·  {quand}  ·  {duree_lisible(secondes(ligne))}{origine}")

    def _selection(self, _):
        sel = self.arbre.selection()
        if sel:
            self._afficher_visite(self.lignes[sel[0]])

    def _ouvrir_video(self, _):
        sel = self.arbre.selection()
        if sel:
            chemin = self.dossier / self.lignes[sel[0]]["video"]
            if chemin.exists():
                os.startfile(chemin)

    def _menu_visite(self, evenement):
        iid = self.arbre.identify_row(evenement.y)
        if not iid:
            return
        self.arbre.selection_set(iid)
        ligne = self.lignes[iid]
        menu = tk.Menu(self.root, tearoff=0)
        if ligne.get("id_proposition") in self.registre.fiches:
            menu.add_command(label=f"✔  Oui, c'est {ligne['proposition']}", command=lambda: self._corriger(ligne, ligne["id_proposition"]))
            menu.add_separator()
        menu.add_command(label="Cette visite est de :", state="disabled")
        for cle, fiche in sorted(self.registre.copie_fiches().items(), key=lambda x: x[1]["nom"]):
            if cle != ligne.get("id_individu"):
                menu.add_command(label=fiche["nom"], command=lambda c=cle: self._corriger(ligne, c))
        menu.add_separator()
        menu.add_command(label="Nouvelle tortue…", command=lambda: self._corriger_nouvelle(ligne))
        menu.add_command(label=PAS_UNE_TORTUE, command=lambda: self._pas_une_tortue(ligne))
        menu.tk_popup(evenement.x_root, evenement.y_root)

    def _pas_une_tortue(self, ligne):
        if messagebox.askyesno(PAS_UNE_TORTUE, "Effacer cette visite, son clip et ses photos ?\n"
                                               "Broutille ignorera ce qui lui ressemble ; Réglages permet de l'annuler."):
            self._corriger(ligne, PAS_UNE_TORTUE)

    def _corriger(self, ligne, cle):
        def travail():
            try:
                corrigee = corriger_visite(self.dossier, self.registre, ligne["id_visite"], cle)
                if corrigee is None:
                    self.messages.put(("corrige", "Cette visite n'est plus au journal"))
                elif corrigee["sans_image"]:
                    self.messages.put(("corrige", f"Corrigé : {corrigee['individu']} (images de cette visite déjà effacées)"))
                else:
                    self.messages.put(("corrige", f"Corrigé : {corrigee['individu']} — Broutille retient ces images"))
            except JournalOccupe as e:
                self.messages.put(("corrige", str(e)))
            except Exception as e:
                self.messages.put(("corrige", f"Correction impossible : {type(e).__name__} : {e}"))
        self.lbl_etat.configure(text="Correction en cours…")
        threading.Thread(target=travail, daemon=True).start()

    def _corriger_nouvelle(self, ligne):
        resultat = self._dialogue_tortue("Nouvelle tortue", espece=ligne["espece"])
        if resultat:
            self._corriger(ligne, self.registre.creer(*resultat))

    def _maj_stats(self):
        aujourd_hui = datetime.now().strftime("%Y-%m-%d")
        temps = defaultdict(float)
        for l in self.lignes.values():
            if l["date"] == aujourd_hui:
                temps[l["individu"]] += secondes(l)
        c = self.stats
        c.delete("all")
        largeur = max(c.winfo_width(), 360)
        if not temps:
            c.configure(height=30)
            c.create_text(0, 14, anchor="w", text="Pas encore de repas aujourd'hui", fill=DISCRET, font=("Segoe UI", 10))
            return
        top = sorted(temps.items(), key=lambda x: -x[1])[:5]
        c.configure(height=26 * len(top))
        maxi = top[0][1] or 1
        for i, (nom, s) in enumerate(top):
            y = i * 26 + 4
            barre = max(4, (largeur - 190) * s / maxi)
            c.create_text(0, y + 9, anchor="w", text=nom[:18], fill=TEXTE, font=("Segoe UI", 10))
            c.create_rectangle(120, y + 3, 120 + barre, y + 15, fill=COULEURS[i % len(COULEURS)], width=0)
            c.create_text(128 + barre, y + 9, anchor="w", text=duree_lisible(s), fill=DISCRET, font=("Segoe UI", 9))

    # -------------------------------------------------------------- tortues
    def _maj_tortues(self):
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
        for cle, fiche in sorted(self.registre.copie_fiches().items(), key=lambda x: (x[1].get("provisoire", False), x[1]["nom"])):
            d = self.registre.dossier / cle
            photos = sorted(d.glob("*.jpg")) if d.exists() else []
            vignette = self._vignette(photos[0], (64, 48)) if photos else None
            vue = derniere.get(cle, "")
            tags = ("provisoire",) if fiche.get("provisoire") else ("absente",) if vue and vue < limite else ()
            a.insert("", "end", iid=cle, image=vignette or "", tags=tags,
                     values=(fiche["nom"], visites[cle], f"{vue[8:]}/{vue[5:7]}" if vue else "jamais"))
            if vignette:
                self.vignettes_tortues[cle] = vignette

    def _dialogue_tortue(self, titre, nom="", espece=None):
        """(nom, espèce) saisis, ou None."""
        f = tk.Toplevel(self.root, bg=CARTE, padx=20, pady=16)
        f.title(titre)
        f.transient(self.root)
        f.grab_set()
        resultat = []
        v_nom, v_espece = tk.StringVar(value=nom), tk.StringVar(value=espece or self.classeur.especes[0][0])
        ttk.Label(f, text="Nom", style="Carte.TLabel").grid(row=0, column=0, sticky="w", pady=5, padx=(0, 12))
        e = ttk.Entry(f, textvariable=v_nom, width=30)
        e.grid(row=0, column=1)
        e.focus_set()
        ttk.Label(f, text="Espèce", style="Carte.TLabel").grid(row=1, column=0, sticky="w", pady=5, padx=(0, 12))
        ttk.Combobox(f, textvariable=v_espece, values=[x[0] for x in self.classeur.especes], width=28).grid(row=1, column=1)

        def valider(_=None):
            if v_nom.get().strip():
                resultat.append((v_nom.get().strip(), v_espece.get().strip()))
                f.destroy()

        f.bind("<Return>", valider)
        ttk.Button(f, text="Valider", style="Vert.TButton", command=valider).grid(row=2, column=1, sticky="e", pady=(12, 0))
        self.root.wait_window(f)
        return resultat[0] if resultat else None

    def ajouter_tortue(self):
        resultat = self._dialogue_tortue("Ajouter une tortue")
        if not resultat:
            return
        cle = self.registre.creer(*resultat)
        self._maj_tortues()
        if messagebox.askyesno("Ajouter une tortue", "Ajouter des photos de cette tortue maintenant ?\n"
                                                     "Plusieurs vues aident : face, deux profils, dessus."):
            self._importer_photos(cle)

    def _importer_photos(self, cle):
        chemins = filedialog.askopenfilenames(title="Photos de la tortue", filetypes=[("Photos", "*.jpg *.jpeg *.png")])
        if not chemins:
            return

        def travail():
            try:
                n = inscrire_photos(self.registre, self.detecteur, cle, chemins, lambda m: self.messages.put(("message", m)))
                self.messages.put(("corrige", f"{n} photo(s) ajoutée(s) à {self.registre.fiches[cle]['nom']}"))
            except Exception as e:
                self.messages.put(("corrige", f"Import impossible : {type(e).__name__} : {e}"))
        self.lbl_etat.configure(text="Analyse des photos…")
        threading.Thread(target=travail, daemon=True).start()

    def _menu_tortue(self, evenement):
        cle = self.arbre_t.identify_row(evenement.y)
        if not cle:
            return
        self.arbre_t.selection_set(cle)
        fiche = self.registre.fiches[cle]
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=f"{fiche['nom']} — {fiche['espece']}", state="disabled")
        menu.add_command(label="Nommer / changer l'espèce…", command=lambda: self._modifier_tortue(cle))
        menu.add_command(label="Ajouter des photos…", command=lambda: self._importer_photos(cle))
        fusion = tk.Menu(menu, tearoff=0)
        for autre, f in sorted(self.registre.copie_fiches().items(), key=lambda x: x[1]["nom"]):
            if autre != cle:
                fusion.add_command(label=f["nom"], command=lambda a=autre: self._fusionner(cle, a))
        menu.add_cascade(label="C'est la même tortue que", menu=fusion)
        menu.add_separator()
        menu.add_command(label="Supprimer la fiche…", command=lambda: self._supprimer(cle))
        menu.tk_popup(evenement.x_root, evenement.y_root)

    def _modifier_tortue(self, cle):
        fiche = self.registre.fiches[cle]
        resultat = self._dialogue_tortue("Fiche de la tortue", fiche["nom"], fiche["espece"])
        if resultat:
            nom, espece = resultat
            if self._journal_libre(renommer_dans_journal, self.dossier, cle, nom, espece):
                self.registre.modifier(cle, nom=nom, espece=espece, provisoire=False)
            self.charger_historique()

    def _fusionner(self, source, cible):
        fs, fc = self.registre.fiches[source], self.registre.fiches[cible]
        if messagebox.askyesno("Même tortue", f"« {fs['nom']} » et « {fc['nom']} » sont la même tortue ?\n"
                                              f"Tout est regroupé sous « {fc['nom']} »."):
            if self._journal_libre(renommer_dans_journal, self.dossier, source, fc["nom"], fc["espece"], cible):
                self.registre.fusionner(source, cible)
            self.charger_historique()

    def _supprimer(self, cle):
        fiche = self.registre.fiches[cle]
        if messagebox.askyesno("Supprimer", f"Supprimer la fiche et la galerie de « {fiche['nom']} » ?\n"
                                            "Ses visites restent au journal, sous le nom « Inconnue »."):
            if self._journal_libre(renommer_dans_journal, self.dossier, cle, INCONNUE, None, ""):
                self.registre.supprimer(cle)
            self.charger_historique()

    def _journal_libre(self, fonction, *args):
        """Journal d'abord : s'il est bloqué, les fiches ne bougent pas et rien ne diverge."""
        try:
            fonction(*args)
            return True
        except JournalOccupe as e:
            messagebox.showerror("Journal", str(e))
            return False

    def _ouvrir_galerie(self, evenement):
        cle = self.arbre_t.identify_row(evenement.y)
        if cle and (self.registre.dossier / cle).exists():
            os.startfile(self.registre.dossier / cle)

    # -------------------------------------------------------------- statistiques
    def statistiques(self):
        f = tk.Toplevel(self.root, bg=CARTE, padx=16, pady=14)
        f.title("Statistiques — 30 derniers jours")
        f.transient(self.root)
        debut = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        par = defaultdict(lambda: {"n": 0, "s": 0.0, "jours": set(), "dernier": "", "espece": ""})
        try:
            journal = lire_journal(self.dossier)
        except (JournalOccupe, OSError):
            journal = []
        for l in journal:
            if l["date"] >= debut:
                p = par[l["individu"]]
                p["n"] += 1
                p["s"] += secondes(l)
                p["jours"].add(l["date"])
                p["dernier"] = max(p["dernier"], l["date"])
                p["espece"] = l["espece"]
        colonnes = (("nom", "TORTUE", 170), ("espece", "ESPÈCE", 150), ("n", "VISITES", 70), ("temps", "TEMPS À TABLE", 110),
                    ("moy", "PAR JOUR DE VISITE", 130), ("jours", "JOURS VENUE", 90), ("vue", "DERNIÈRE VISITE", 110))
        ttk.Style(self.root).configure("Stats.Treeview", rowheight=28)
        a = ttk.Treeview(f, columns=[c[0] for c in colonnes], show="headings", style="Stats.Treeview", height=14)
        for col, titre, larg in colonnes:
            a.heading(col, text=titre, anchor="w")
            a.column(col, width=larg, anchor="w")
        a.pack(fill="both", expand=True)
        for nom, p in sorted(par.items(), key=lambda x: -x[1]["s"]):
            a.insert("", "end", values=(nom, p["espece"], p["n"], duree_lisible(p["s"]), duree_lisible(p["s"] / max(len(p["jours"]), 1)),
                                        len(p["jours"]), p["dernier"]))

    def quitter(self):
        self._ecrire_config()
        if not self.surveillance:
            self.root.destroy()
            return
        # la fenêtre attend la fin de la surveillance : sinon le clip en cours serait illisible
        # et la visite perdue. Filet d'une minute si la source ne répond plus.
        self.fermeture = True
        self.root.withdraw()
        self.surveillance.arreter()
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
        messagebox.showerror("Broutille", f"{e}\nRestaurez registre.bak ou contactez le support du projet.")
        return
    except Exception as e:
        journaliser_erreur(e)
        root.withdraw()
        messagebox.showerror("Broutille", f"Démarrage impossible : {type(e).__name__} : {e}\n"
                                          f"Détails dans {Path.home() / '.broutille_erreurs.log'}")
        return
    root.mainloop()


if __name__ == "__main__":
    main()
