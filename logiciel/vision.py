"""
Broutille — vision : trouver les tortues dans l'image, dire leur espèce, décrire leur carapace.

  - détection     : Grounding DINO tiny (zero-shot, Apache 2.0) ; COCO n'a pas de classe tortue
  - espèce        : BioCLIP (MIT) comparé à de vraies photos de chaque espèce
  - individu      : MegaDescriptor (ré-identification animale, CC BY-NC 4.0) + SIFT (dessin des écailles)

La webcam filme de loin, en vue large : la tortue est isolée de son décor avant d'être décrite.
"""

import threading
from pathlib import Path

import cv2
import numpy as np

MODELE_DETECTION = "IDEA-Research/grounding-dino-tiny"
MODELE_ESPECES = "hf-hub:imageomics/bioclip"
MODELE_REID = "hf-hub:BVRA/MegaDescriptor-L-384"
TAILLE_TORTUE = 384

REFERENCES = Path(__file__).resolve().parent / "modeles" / "references_especes.npz"

# Espèces reconnues : (nom affiché, nom scientifique, nom anglais) ; chacune a ses photos de référence.
ESPECES_DEFAUT = [
    ("Tortue radiée", "Astrochelys radiata", "Radiated Tortoise"),
    ("Tortue sillonnée", "Centrochelys sulcata", "African Spurred Tortoise"),
    ("Tortue d'Aldabra", "Aldabrachelys gigantea", "Aldabra Giant Tortoise"),
    ("Tortue léopard", "Stigmochelys pardalis", "Leopard Tortoise"),
    ("Tortue charbonnière", "Chelonoidis carbonarius", "Red-footed Tortoise"),
    ("Tortue d'Hermann", "Testudo hermanni", "Hermann's Tortoise"),
    ("Tortue grecque", "Testudo graeca", "Spur-thighed Tortoise"),
    ("Tortue des steppes", "Testudo horsfieldii", "Russian Tortoise"),
    ("Tortue étoilée", "Geochelone elegans", "Indian Star Tortoise"),
]
AUTRES = ["a photo of a human hand.", "a photo of a person.", "a photo of a dog.", "a photo of a cat.",
          "a photo of a chicken.", "a photo of a rat.", "a photo of a lizard.", "a photo of a bird.",
          "a photo of grass and leaves.", "a photo of a rock.", "a photo of vegetables on a tray.",
          "a photo of an empty plastic tray.", "a dark blurry photo."]


def appareil():
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


def egaliser(image_bgr):
    """Contraste local : l'ombre d'une feuille ne doit pas masquer le dessin des écailles."""
    l, a, b = cv2.split(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB))
    l = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)


def iou(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    l = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    h = max(0, min(ay + ah, by + bh) - max(ay, by))
    union = aw * ah + bw * bh - l * h
    return l * h / union if union else 0.0


def contenue(petite, grande):
    """Part de la petite boîte qui se trouve dans la grande."""
    ax, ay, aw, ah = petite
    bx, by, bw, bh = grande
    l = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    h = max(0, min(ay + ah, by + bh) - max(ay, by))
    return l * h / max(aw * ah, 1)


def trier_boites(boites):
    """Une boîte par tortue. Le détecteur sort parfois en plus la tête seule (boîte contenue dans une
    autre) ou tout le groupe (boîte qui en contient plusieurs) : ni l'une ni l'autre n'est une tortue."""
    def dedans(g):
        return [p for p in boites if p is not g and p[1][2] * p[1][3] < g[1][2] * g[1][3] and contenue(p[1], g[1]) > 0.7]

    groupes = [g for g in boites if len(dedans(g)) >= 2]
    gardees = [b for b in boites if b not in groupes]
    return [p for p in gardees if not any(p in dedans(g) for g in gardees)]


class DetecteurTortues:
    """Boîtes des tortues de l'image."""

    def __init__(self, seuil=0.3, largeur=800, texte="a tortoise."):
        self.seuil, self.largeur, self.texte = seuil, largeur, texte
        self.modele = None
        self._verrou = threading.Lock()

    def charger(self):
        with self._verrou:
            if self.modele is None:
                from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor
                self.processeur = AutoProcessor.from_pretrained(MODELE_DETECTION)
                self.appareil = appareil()
                self.modele = AutoModelForZeroShotObjectDetection.from_pretrained(MODELE_DETECTION).to(self.appareil).eval()
                # sur processeur la détection pèse 85 % de l'analyse : à 480, elle est 2,6 fois plus rapide
                # sans perdre une tortue sur 120 photos (à 320 aussi, mais une tortue lointaine serait trop petite)
                self.cote = 800 if self.appareil == "cuda" else 480

    def detecter(self, image_bgr):
        """Liste de (score, (x, y, l, h)) en pixels de l'image d'origine, la plus grande d'abord."""
        import torch
        from PIL import Image
        self.charger()
        e = min(1.0, self.largeur / max(image_bgr.shape[:2]))
        petite = cv2.resize(image_bgr, None, fx=e, fy=e, interpolation=cv2.INTER_AREA) if e < 1 else image_bgr
        image = Image.fromarray(cv2.cvtColor(petite, cv2.COLOR_BGR2RGB))
        entrees = self.processeur(images=image, text=self.texte, return_tensors="pt",
                                  size={"shortest_edge": self.cote, "longest_edge": int(self.cote * 1.34)}).to(self.appareil)
        with torch.no_grad():
            sorties = self.modele(**entrees)
        r = self.processeur.post_process_grounded_object_detection(
            sorties, entrees["input_ids"], threshold=self.seuil, text_threshold=self.seuil,
            target_sizes=[image.size[::-1]])[0]
        boites = []
        for s, b in sorted(zip(r["scores"].tolist(), r["boxes"].tolist()), reverse=True):
            x0, y0, x1, y1 = [v / e for v in b]
            boite = (int(x0), int(y0), int(x1 - x0), int(y1 - y0))
            if min(boite[2:]) >= 32 and all(iou(boite, autre[1]) < 0.5 for autre in boites):
                boites.append((float(s), boite))
        return sorted(trier_boites(boites), key=lambda d: d[1][2] * d[1][3], reverse=True)


def recadrer(image, boite, marge=0.08):
    """Recadrage carré autour d'une boîte, sans sortir de l'image."""
    h, w = image.shape[:2]
    x, y, bw, bh = boite
    cote = min(int(max(bw, bh) * (1 + 2 * marge)), w, h)
    x0 = max(0, min(w - cote, x + bw // 2 - cote // 2))
    y0 = max(0, min(h - cote, y + bh // 2 - cote // 2))
    return image[y0:y0 + cote, x0:x0 + cote]


def isoler_tortue(image, boite):
    """Tortue seule sur fond gris (TAILLE_TORTUE²) : l'herbe et la mangeoire changent d'un jour à
    l'autre, ils ne doivent pas compter dans l'identité. La webcam filme de côté, à distance : la
    tortue garde son sens, ses profils et sa face sont des vues différentes de la même galerie.
    Si la découpe GrabCut échoue (forme aberrante), le recadrage simple est gardé."""
    t = 192
    carre = recadrer(image, boite, 0.06)
    if carre.size == 0:
        return None
    cote = carre.shape[0]
    petite = cv2.resize(carre, (t, t), interpolation=cv2.INTER_AREA)
    x0 = max(0, min(image.shape[1] - cote, boite[0] + boite[2] // 2 - cote // 2))
    y0 = max(0, min(image.shape[0] - cote, boite[1] + boite[3] // 2 - cote // 2))
    f = t / cote
    bx0, by0 = max(0, int((boite[0] - x0) * f)), max(0, int((boite[1] - y0) * f))
    bx1, by1 = min(t, int((boite[0] + boite[2] - x0) * f)), min(t, int((boite[1] + boite[3] - y0) * f))
    centre = ((bx0 + bx1) // 2, (by0 + by1) // 2)
    masque = np.full((t, t), cv2.GC_BGD, np.uint8)
    masque[by0:by1, bx0:bx1] = cv2.GC_PR_BGD
    cv2.ellipse(masque, centre, (max(1, (bx1 - bx0) * 2 // 5), max(1, (by1 - by0) * 2 // 5)), 0, 0, 360, cv2.GC_PR_FGD, -1)
    cv2.ellipse(masque, centre, (max(1, (bx1 - bx0) // 5), max(1, (by1 - by0) // 5)), 0, 0, 360, cv2.GC_FGD, -1)
    simple = cv2.resize(carre, (TAILLE_TORTUE, TAILLE_TORTUE), interpolation=cv2.INTER_AREA)
    try:
        cv2.grabCut(petite, masque, None, np.zeros((1, 65)), np.zeros((1, 65)), 3, cv2.GC_INIT_WITH_MASK)
    except cv2.error:
        return simple
    objet = np.isin(masque, (cv2.GC_FGD, cv2.GC_PR_FGD)).astype(np.uint8)
    objet = cv2.morphologyEx(objet, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    contours, _h = cv2.findContours(objet, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours or cv2.contourArea(max(contours, key=cv2.contourArea)) < 0.3 * (bx1 - bx0) * (by1 - by0):
        return simple
    plein = np.zeros((t, t), np.uint8)
    cv2.drawContours(plein, [max(contours, key=cv2.contourArea)], -1, 255, -1)
    plein = cv2.GaussianBlur(cv2.resize(plein, (TAILLE_TORTUE, TAILLE_TORTUE)), (9, 9), 0)[..., None] / 255.0
    return (simple * plein + 128 * (1 - plein)).astype(np.uint8)


class ClasseurEspeces:
    """Tortue ou pas (BioCLIP zero-shot), puis espèce : petit classifieur linéaire appris au
    démarrage sur de vraies photos (modeles/references_especes.npz, voir tests/preparer_especes.py),
    pour les seules espèces présentes chez l'utilisateur : moins il y a de candidates, moins il se trompe."""
    ECHELLE = 30.0

    def __init__(self, especes=None):
        self.especes = especes or ESPECES_DEFAUT[:2]
        self.modele = None
        self.poids = None
        self._verrou = threading.RLock()

    def charger(self):
        with self._verrou:
            if self.modele is not None:
                return
            import open_clip
            import torch
            self.modele, _e, self.pretraitement = open_clip.create_model_and_transforms(MODELE_ESPECES)
            jetons = open_clip.get_tokenizer(MODELE_ESPECES)
            self.appareil = appareil()
            self.modele.to(self.appareil).eval()
            textes = ["a photo of a tortoise.", "a photo of Testudinidae."] + AUTRES
            with torch.no_grad():
                v = self.modele.encode_text(jetons(textes).to(self.appareil)).float()
            self.textes = (v / v.norm(dim=-1, keepdim=True)).cpu().numpy()
            if REFERENCES.exists():
                r = np.load(REFERENCES)
                self.connues = [e for e in self.especes if e[1] in r]
                if len(self.connues) >= 2:
                    self.poids = entrainer_lineaire([r[e[1]] for e in self.connues], self.ECHELLE)

    def vecteur(self, image_bgr):
        import torch
        from PIL import Image
        self.charger()
        with self._verrou, torch.no_grad():
            image = Image.fromarray(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))
            f = self.modele.encode_image(self.pretraitement(image)[None].to(self.appareil)).float()
            return (f / f.norm(dim=-1, keepdim=True)).cpu().numpy()[0]

    def classer(self, image_bgr):
        """(prob. que ce soit une tortue, [(espèce, prob. parmi les espèces)...] triées)."""
        f = self.vecteur(image_bgr)
        logits = 100.0 * self.textes @ f
        p = np.exp(logits - logits.max())
        tortue = float(p[:2].sum() / p.sum())
        if self.poids is None:
            return tortue, [(e[0], 1.0 / len(self.especes)) for e in self.especes]
        s = self.ECHELLE * f @ self.poids[0] + self.poids[1]
        q = np.exp(s - s.max())
        q /= q.sum()
        return tortue, [(self.connues[i][0], float(q[i])) for i in np.argsort(-q)]


def entrainer_lineaire(classes, echelle, regularisation=1e-3):
    """Régression logistique sur des vecteurs par classe : (poids, biais). Moins d'une seconde."""
    import torch
    X = torch.tensor(np.vstack(classes), dtype=torch.float32)
    y = torch.tensor(np.concatenate([[i] * len(c) for i, c in enumerate(classes)]))
    W = torch.zeros(X.shape[1], len(classes), requires_grad=True)
    b = torch.zeros(len(classes), requires_grad=True)
    optimiseur = torch.optim.LBFGS([W, b], max_iter=200, line_search_fn="strong_wolfe")

    def perte():
        optimiseur.zero_grad()
        l = torch.nn.functional.cross_entropy(echelle * X @ W + b, y) + regularisation * (W ** 2).sum()
        l.backward()
        return l

    optimiseur.step(perte)
    return W.detach().numpy(), b.detach().numpy()


class Descripteur:
    """Vecteur d'identité (MegaDescriptor) d'une tortue isolée."""

    def __init__(self):
        self.modele = None
        self._verrou = threading.Lock()

    def charger(self):
        with self._verrou:
            if self.modele is None:
                import timm
                self.appareil = appareil()
                self.modele = timm.create_model(MODELE_REID, num_classes=0, pretrained=True).to(self.appareil).eval()

    def decrire(self, tortue_bgr):
        """Tableau (1, d) : vecteur unitaire."""
        import torch
        self.charger()
        vue = cv2.cvtColor(tortue_bgr, cv2.COLOR_BGR2RGB)[None]
        x = torch.from_numpy(vue).permute(0, 3, 1, 2).float().div(255).sub(0.5).div(0.5).to(self.appareil)
        with torch.no_grad():
            f = self.modele(x)
        f = f / f.norm(dim=-1, keepdim=True)
        return f.cpu().numpy()


_sift = None


def points_sift(tortue_bgr):
    """Points SIFT du dessin de la tortue, racine-SIFT pour un appariement plus stable."""
    global _sift
    if _sift is None:
        _sift = cv2.SIFT_create(nfeatures=800, contrastThreshold=0.03)
    gris = cv2.cvtColor(egaliser(tortue_bgr), cv2.COLOR_BGR2GRAY)
    masque = (cv2.absdiff(tortue_bgr, np.full_like(tortue_bgr, 128)).sum(axis=2) > 6).astype(np.uint8) * 255
    points, desc = _sift.detectAndCompute(gris, masque)
    if desc is None:
        return np.zeros((0, 2), np.float32), np.zeros((0, 128), np.float32)
    desc = np.sqrt(desc / (desc.sum(axis=1, keepdims=True) + 1e-7))
    return np.float32([p.pt for p in points]), desc.astype(np.float32)


def appariement_sift(a, b):
    """Nombre de points cohérents entre deux vues (RANSAC) : un même dessin d'écailles
    se superpose, deux tortues différentes presque jamais."""
    pa, da = a
    pb, db = b
    if len(pa) < 8 or len(pb) < 8:
        return 0
    paires = cv2.BFMatcher(cv2.NORM_L2).knnMatch(da, db, k=2)
    bons = [m for m, n in (p for p in paires if len(p) == 2) if m.distance < 0.8 * n.distance]
    if len(bons) < 6:
        return 0
    src = np.float32([pa[m.queryIdx] for m in bons])
    dst = np.float32([pb[m.trainIdx] for m in bons])
    _m, inliers = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=8.0)
    return int(inliers.sum()) if inliers is not None else 0
