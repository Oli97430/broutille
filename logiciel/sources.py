"""
Broutille — sources vidéo : webcam USB, fenêtre ouverte, flux Internet ou fichier vidéo.

  - webcam           : « 0 », « 1 »...
  - fenêtre ouverte  : « fenetre:EZVIZ Studio » (une partie du titre suffit)
  - flux Internet    : rtsp://..., http(s)://...m3u8, ou page d'une caméra en direct (YouTube, Twitch...)
  - fichier vidéo    : chemin du fichier (analyse a posteriori)

Une source s'utilise comme un cv2.VideoCapture : read(), get(), release().
"""

import ctypes
import ctypes.wintypes as wt
import os
import time
import urllib.parse
from pathlib import Path

import cv2
import numpy as np

PREFIXE_FENETRE = "fenetre:"
IMAGES_PAR_SECONDE_FENETRE = 10
# RTSP en TCP : en UDP, les caméras Wi-Fi perdent des paquets et l'image se déchire
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp|stimeout;10000000")


def source_depuis_texte(texte):
    texte = str(texte).strip()
    return int(texte) if texte.isdigit() else texte


def est_flux(source):
    return isinstance(source, str) and "://" in source


def est_fenetre(source):
    return isinstance(source, str) and source.startswith(PREFIXE_FENETRE)


def est_fichier(source):
    return isinstance(source, str) and not est_flux(source) and not est_fenetre(source) and Path(source).is_file()


def masquer(source):
    """Adresse sans son mot de passe : elle s'affiche à l'écran et dans les messages."""
    if not est_flux(source):
        return str(source)
    u = urllib.parse.urlsplit(source)
    if u.password:
        return source.replace(f":{u.password}@", ":•••@")
    return source


# ------------------------------------------------------------------
#  Flux Internet
# ------------------------------------------------------------------
def resoudre_flux(source):
    """Page web d'une caméra en direct (YouTube, Twitch...) -> adresse du flux, avec yt-dlp.
    À refaire à chaque connexion : ces adresses expirent au bout de quelques heures.
    Un flux direct (.m3u8, rtsp...) ou une page inconnue de yt-dlp est rendu tel quel."""
    if not source.startswith("http"):
        return source
    if Path(urllib.parse.urlparse(source).path).suffix.lower() in (".m3u8", ".mpd", ".mp4", ".ts", ".flv", ".mjpg", ".mjpeg"):
        return source
    try:
        import yt_dlp
        options = {"quiet": True, "no_warnings": True, "noplaylist": True,
                   "format": "bestvideo[height<=1080]/best[height<=1080]/best"}   # le son n'est pas utilisé
        with yt_dlp.YoutubeDL(options) as ydl:
            return ydl.extract_info(source, download=False)["url"]
    except Exception:
        return source


# ------------------------------------------------------------------
#  Fenêtre ouverte (API Windows, sans bibliothèque en plus)
# ------------------------------------------------------------------
user32, gdi32 = (ctypes.WinDLL(n, use_last_error=True) for n in ("user32", "gdi32")) if os.name == "nt" else (None, None)
PW_RENDERFULLCONTENT = 2        # capture aussi le contenu dessiné par la carte graphique (lecteurs vidéo)
SRCCOPY = 0x00CC0020


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


if user32:
    user32.GetDC.restype = wt.HANDLE
    user32.GetDC.argtypes = [wt.HWND]
    user32.ReleaseDC.argtypes = [wt.HWND, wt.HANDLE]
    user32.PrintWindow.argtypes = [wt.HWND, wt.HANDLE, wt.UINT]
    user32.WindowFromPoint.restype = wt.HWND
    user32.WindowFromPoint.argtypes = [wt.POINT]
    user32.GetAncestor.restype = wt.HWND
    user32.GetAncestor.argtypes = [wt.HWND, wt.UINT]
    gdi32.CreateCompatibleDC.restype = wt.HANDLE
    gdi32.CreateCompatibleDC.argtypes = [wt.HANDLE]
    gdi32.CreateCompatibleBitmap.restype = wt.HANDLE
    gdi32.CreateCompatibleBitmap.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_int]
    gdi32.SelectObject.restype = wt.HANDLE
    gdi32.SelectObject.argtypes = [wt.HANDLE, wt.HANDLE]
    gdi32.DeleteObject.argtypes = [wt.HANDLE]
    gdi32.DeleteDC.argtypes = [wt.HANDLE]
    gdi32.BitBlt.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HANDLE, ctypes.c_int,
                             ctypes.c_int, wt.DWORD]
    gdi32.GetDIBits.argtypes = [wt.HANDLE, wt.HANDLE, wt.UINT, wt.UINT, ctypes.c_void_p, ctypes.c_void_p, wt.UINT]


def lister_fenetres():
    """[(titre, poignée)] des fenêtres ouvertes et visibles."""
    trouvees = []
    rappel = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

    def voir(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                tampon = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, tampon, n + 1)
                r = wt.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(r))
                if r.right - r.left > 100 and r.bottom - r.top > 100 and tampon.value not in ("Program Manager",):
                    trouvees.append((tampon.value, hwnd))
        return True

    user32.EnumWindows(rappel(voir), 0)
    return trouvees


def trouver_fenetre(titre):
    titre = titre.lower()
    for t, hwnd in lister_fenetres():
        if t.lower() == titre:
            return hwnd
    return next((hwnd for t, hwnd in lister_fenetres() if titre in t.lower()), None)


def _lire_bitmap(dc, bitmap, l, h):
    info = BITMAPINFOHEADER(biSize=ctypes.sizeof(BITMAPINFOHEADER), biWidth=l, biHeight=-h, biPlanes=1, biBitCount=32)
    pixels = np.empty((h, l, 4), np.uint8)
    if not gdi32.GetDIBits(dc, bitmap, 0, h, pixels.ctypes.data, ctypes.byref(info), 0):
        return None
    return pixels[:, :, :3].copy()


GA_ROOT = 2


def fenetre_couverte(hwnd, x, y, l, h):
    """Vrai si une autre fenêtre cache une partie de la zone cliente (9 points testés).
    Ne sert que pour la copie d'écran : PrintWindow, lui, ne voit pas les fenêtres du dessus."""
    for fx in (0.1, 0.5, 0.9):
        for fy in (0.1, 0.5, 0.9):
            pt = wt.POINT(int(x + fx * l), int(y + fy * h))
            dessus = user32.WindowFromPoint(pt)
            if dessus and user32.GetAncestor(dessus, GA_ROOT) != hwnd:
                return True
    return False


def capturer_fenetre(hwnd):
    """Image BGR du contenu de la fenêtre, ou None si elle est fermée ou réduite.
    PrintWindow marche même si la fenêtre est cachée par une autre. Certains lecteurs vidéo
    rendent alors une image noire : on copie dans ce cas la zone de l'écran, ce qui demande
    que la fenêtre soit visible."""
    if not user32.IsWindow(hwnd) or user32.IsIconic(hwnd):
        return None
    r = wt.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(r))
    l, h = r.right - r.left, r.bottom - r.top
    if l < 16 or h < 16:
        return None
    ecran = user32.GetDC(0)
    dc = gdi32.CreateCompatibleDC(ecran)
    bitmap = gdi32.CreateCompatibleBitmap(ecran, l, h)
    ancien = gdi32.SelectObject(dc, bitmap)
    try:
        image = None
        if user32.PrintWindow(hwnd, dc, 1 | PW_RENDERFULLCONTENT):    # 1 : zone cliente seulement
            image = _lire_bitmap(dc, bitmap, l, h)
        if image is None or image.mean() < 2:
            coin = wt.POINT(0, 0)
            user32.ClientToScreen(hwnd, ctypes.byref(coin))
            if fenetre_couverte(hwnd, coin.x, coin.y, l, h):
                return None       # sinon on enregistrerait la fenêtre posée par-dessus
            gdi32.BitBlt(dc, 0, 0, l, h, ecran, coin.x, coin.y, SRCCOPY)
            image = _lire_bitmap(dc, bitmap, l, h)
        return image
    finally:
        gdi32.SelectObject(dc, ancien)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(dc)
        user32.ReleaseDC(0, ecran)


ECART_FOND = 14          # écart de couleur au fond uni, sur 255
PART_CONTENU = 0.03      # une ligne ou une colonne est utile si 3 % de ses pixels s'écartent du fond
REVOIR_CADRE_S = 5.0     # le cadre utile est recalculé toutes les 5 s
MARGE_CADRE = 8          # en pixels : en dessous, un nouveau cadre n'est pas pris en compte


def cadre_utile(image):
    """Comme _cadre_une_fois, répété : une bande noire autour d'un fond gris s'enlève en
    deux passes."""
    x, y, x1, y1 = 0, 0, image.shape[1], image.shape[0]
    trouve = False
    for _passe in range(3):
        cadre = _cadre_une_fois(image[y:y1, x:x1])
        if cadre is None:
            break
        trouve = True
        x, y, x1, y1 = x + cadre[0], y + cadre[1], x + cadre[2], y + cadre[3]
    return (x, y, x1, y1) if trouve else None


def _cadre_une_fois(image):
    """(x0, y0, x1, y1) du contenu d'une fenêtre, sans les bandes unies autour : fond gris
    ou noir d'un lecteur vidéo qui n'affiche la caméra que dans une partie de sa fenêtre
    (EZVIZ Studio montre une caméra verticale dans une tuile étroite). La couleur du fond est
    la plus fréquente sur le bord de l'image. Renvoie None si rien de net ne se dégage."""
    h, l = image.shape[:2]
    bord = np.concatenate([image[0], image[-1], image[:, 0], image[:, -1]]).astype(np.int16)
    couleurs, nombres = np.unique(bord // 4, axis=0, return_counts=True)
    fond = couleurs[nombres.argmax()] * 4 + 2
    if nombres.max() < 0.3 * len(bord):
        return None                          # bord varié : pas de fond uni, on garde tout
    ecart = (np.abs(image.astype(np.int16) - fond).max(axis=2) > ECART_FOND)
    colonnes = np.flatnonzero(ecart.mean(axis=0) > PART_CONTENU)
    lignes = np.flatnonzero(ecart.mean(axis=1) > PART_CONTENU)
    if len(colonnes) == 0 or len(lignes) == 0:
        return None
    x0, x1, y0, y1 = colonnes[0], colonnes[-1] + 1, lignes[0], lignes[-1] + 1
    if (x1 - x0) < 0.15 * l or (y1 - y0) < 0.15 * h or ((x1 - x0) * (y1 - y0)) > 0.95 * l * h:
        return None                          # trop petit pour être la vidéo, ou rien à enlever
    return int(x0), int(y0), int(x1), int(y1)


class CaptureFenetre:
    """Une fenêtre ouverte, vue comme une caméra. Si elle est réduite ou change de taille,
    read() échoue ou l'image est remise à la taille d'origine ; la surveillance réessaie seule.
    recadrer : enlève seul les bandes unies autour de la vidéo (cadre_utile)."""

    def __init__(self, titre, recadrer=True):
        self.titre = titre
        self.hwnd = trouver_fenetre(titre)
        self.suivante = 0.0
        self.taille = None
        self.recadrer = recadrer
        self.cadre = None
        self.cadre_revu = 0.0
        self.candidat = None

    def _revoir_cadre(self, image):
        """Le cadre ne change que si le même nouveau cadre est trouvé deux fois de suite :
        une scène sombre un instant ne fait pas sauter le recadrage."""
        maintenant = time.time()
        if self.cadre is not None and maintenant - self.cadre_revu < REVOIR_CADRE_S:
            return
        self.cadre_revu = maintenant
        nouveau = cadre_utile(image)
        if self.cadre is None:
            self.cadre = nouveau or (0, 0, image.shape[1], image.shape[0])
            return
        if nouveau is None or max(abs(a - b) for a, b in zip(nouveau, self.cadre)) <= MARGE_CADRE:
            self.candidat = None
        elif self.candidat is not None and max(abs(a - b) for a, b in zip(nouveau, self.candidat)) <= MARGE_CADRE:
            self.cadre, self.candidat = nouveau, None
        else:
            self.candidat = nouveau

    def isOpened(self):
        return self.hwnd is not None

    def get(self, _propriete):
        return IMAGES_PAR_SECONDE_FENETRE

    def read(self):
        attente = self.suivante - time.time()
        if attente > 0:
            time.sleep(attente)
        self.suivante = time.time() + 1 / IMAGES_PAR_SECONDE_FENETRE
        image = capturer_fenetre(self.hwnd) if self.hwnd else None
        if image is None:
            return False, None
        if self.recadrer:
            self._revoir_cadre(image)
            x0, y0, x1, y1 = self.cadre
            if x1 <= image.shape[1] and y1 <= image.shape[0]:
                image = image[y0:y1, x0:x1]
        if self.taille is None:
            self.taille = (image.shape[1], image.shape[0])
        elif (image.shape[1], image.shape[0]) != self.taille:
            image = cv2.resize(image, self.taille)
        return True, image

    def release(self):
        self.hwnd = None


# ------------------------------------------------------------------
#  Ouverture
# ------------------------------------------------------------------
def ouvrir_source(source, largeur=1920, hauteur=1080):
    """Ouvre la source et lit une première image : (capture, image) ou (None, None).
    Webcam : 1080p en MJPG (par défaut OpenCV reste en 640x480, trop peu pour les écailles) ;
    Media Foundation d'abord, puis DirectShow (certaines webcams ne renvoient rien sous MSMF)."""
    if est_fenetre(source):
        camera = CaptureFenetre(source[len(PREFIXE_FENETRE):])
        if not camera.isOpened():
            return None, None
    elif isinstance(source, str):
        adresse = resoudre_flux(source) if est_flux(source) else source
        camera = cv2.VideoCapture(adresse, cv2.CAP_FFMPEG) if est_flux(source) else cv2.VideoCapture(adresse)
    else:
        for api in (cv2.CAP_MSMF, cv2.CAP_DSHOW):
            camera = cv2.VideoCapture(source, api)
            if camera.isOpened():
                camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
                camera.set(cv2.CAP_PROP_FRAME_WIDTH, largeur)
                camera.set(cv2.CAP_PROP_FRAME_HEIGHT, hauteur)
                for _i in range(8):     # certaines webcams renvoient quelques images vides au démarrage
                    ok, image = camera.read()
                    if ok:
                        return camera, image
            camera.release()
        return None, None
    ok, image = camera.read()
    if ok:
        return camera, image
    camera.release()
    return None, None
