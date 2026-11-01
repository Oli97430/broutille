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
            gdi32.BitBlt(dc, 0, 0, l, h, ecran, coin.x, coin.y, SRCCOPY)
            image = _lire_bitmap(dc, bitmap, l, h)
        return image
    finally:
        gdi32.SelectObject(dc, ancien)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(dc)
        user32.ReleaseDC(0, ecran)


class CaptureFenetre:
    """Une fenêtre ouverte, vue comme une caméra. Si elle est réduite ou change de taille,
    read() échoue ou l'image est remise à la taille d'origine ; la surveillance réessaie seule."""

    def __init__(self, titre):
        self.titre = titre
        self.hwnd = trouver_fenetre(titre)
        self.suivante = 0.0
        self.taille = None

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
