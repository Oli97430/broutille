"""
Essais de l'image figée, du clic de relance et de la sauvegarde quotidienne.

    python tests/test_suivi.py
"""

import shutil
import sys
import tempfile
import threading
import time
import tkinter as tk
import zipfile
from datetime import date, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import broutille_cam
import sauvegarde
import sources


class DetecteurVide:
    def detecter(self, _image):
        return []


def essai_figee():
    """Une fenêtre qui bouge, puis s'arrête (direct coupé), puis repart : la surveillance doit
    dire « figée » puis « revenue »."""
    root = tk.Tk()
    root.title("Broutille essai de direct")
    root.geometry("480x320+200+200")
    rng = np.random.default_rng(4)
    fond = rng.integers(40, 200, (300, 460, 3), np.uint8)
    video = tk.Label(root, bd=0)
    video.place(x=10, y=10)
    vivant = [True]

    def image_suivante():
        if vivant[0]:
            bruit = np.clip(fond.astype(np.int16) + rng.integers(-15, 16, fond.shape), 0, 255).astype(np.uint8)
            photo = tk.PhotoImage(data=b"P6 460 300 255 " + bruit[:, :, ::-1].tobytes(), format="PPM")
            video.configure(image=photo)
            video.image = photo

    for _i in range(10):
        image_suivante()
        root.update()
        time.sleep(0.05)
    etats, messages = [], []
    d = Path(tempfile.mkdtemp(prefix="broutille_figee_"))
    s = broutille_cam.Surveillance(sources.PREFIXE_FENETRE + "essai de direct", d, detecteur=DetecteurVide(),
                                   classeur=object(), reconnaissance=False, sur_figee=etats.append,
                                   sur_message=messages.append)
    s.figee_s = 3.0
    fil = threading.Thread(target=s.executer, daemon=True)
    fil.start()
    debut = time.time()
    while time.time() - debut < 30:
        t = time.time() - debut
        vivant[0] = not (10 < t < 18)       # direct coupé de 10 à 18 s
        image_suivante()
        root.update()
        time.sleep(0.08)
    s.arreter()
    while fil.is_alive():
        root.update()
        time.sleep(0.05)
    root.destroy()
    shutil.rmtree(d, ignore_errors=True)
    return [("image figée détectée, puis revenue", etats == [True, False], f"{etats} ; {messages[-3:]}")]


def essai_clic():
    """Le clic posté par Broutille arrive au bon endroit, sans bouger la souris. La fenêtre
    d'essai est une fenêtre Win32 simple : comme Qt (EZVIZ Studio), elle lit la position et
    le bouton dans le message ; Tk, lui, relit l'état réel de la souris et ignorerait le clic."""
    import ctypes
    import ctypes.wintypes as wt
    u, k = ctypes.windll.user32, ctypes.windll.kernel32
    PROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
    u.DefWindowProcW.restype = ctypes.c_ssize_t
    u.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    clics = []

    def proc(hwnd, msg, wparam, lparam):
        if msg in (0x201, 0x203):
            clics.append((msg, lparam & 0xFFFF, (lparam >> 16) & 0xFFFF, bool(wparam & 1)))
        return u.DefWindowProcW(hwnd, msg, wparam, lparam)

    rappel = PROC(proc)

    class WNDCLASSW(ctypes.Structure):
        _fields_ = [("style", wt.UINT), ("lpfnWndProc", PROC), ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                    ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON), ("hCursor", wt.HANDLE), ("hbrBackground", wt.HBRUSH),
                    ("lpszMenuName", wt.LPCWSTR), ("lpszClassName", wt.LPCWSTR)]

    classe = WNDCLASSW(lpfnWndProc=rappel, hInstance=k.GetModuleHandleW(None), lpszClassName="BroutilleEssaiClic",
                       hbrBackground=wt.HBRUSH(6))
    u.RegisterClassW(ctypes.byref(classe))
    u.CreateWindowExW.restype = wt.HWND
    u.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                  ctypes.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID]
    hwnd = u.CreateWindowExW(0, "BroutilleEssaiClic", "Broutille essai de clic", 0x10CF0000, 260, 260, 420, 340,
                             None, None, classe.hInstance, None)
    msg = wt.MSG()

    def pomper(duree):
        fin = time.time() + duree
        while time.time() < fin:
            while u.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                u.TranslateMessage(ctypes.byref(msg))
                u.DispatchMessageW(ctypes.byref(msg))
            time.sleep(0.01)

    pomper(0.4)
    r = wt.RECT()
    u.GetClientRect(hwnd, ctypes.byref(r))
    erreur = ""
    try:
        sources.cliquer("essai de clic", (0.5, 0.5), double=True)
    except OSError as e:
        erreur = str(e)
    pomper(0.6)
    u.DestroyWindow(hwnd)
    pomper(0.1)
    attendu = (r.right // 2, r.bottom // 2)
    bon = [c[0] for c in clics] == [0x201, 0x201 + 2] and all(abs(c[1] - attendu[0]) <= 1 and abs(c[2] - attendu[1]) <= 1
                                                              and c[3] for c in clics)
    return [("double-clic posté reçu au bon endroit, souris immobile", bon, erreur or f"{clics}, attendu {attendu}")]


def essai_sauvegarde():
    d = Path(tempfile.mkdtemp(prefix="broutille_dossier_"))
    dest = Path(tempfile.mkdtemp(prefix="broutille_sauve_"))
    (d / "visites.csv").write_text("id_visite;date\n1;2026-11-05\n", encoding="utf-8")
    (d / "registre.json").write_text('{"t1": {"nom": "Zoé", "pesees": [{"date": "2026-11-01", "g": 1200}]}}', encoding="utf-8")
    (d / "individus" / "t1").mkdir(parents=True)
    (d / "individus" / "t1" / "vue.jpg").write_bytes(b"jpg")
    (d / "2026-11-05_10-00-00.mp4").write_bytes(b"video lourde")
    jour = date(2026, 11, 5)
    r = sauvegarde.sauvegarder(d, dest, jour)
    noms = set(zipfile.ZipFile(r[0]).namelist())
    res = [("archive du jour : journal, fiches, galerie ; pas les clips",
            noms == {"visites.csv", "registre.json", "individus/t1/vue.jpg"}, str(sorted(noms)))]
    res.append(("pas de seconde archive le même jour", sauvegarde.sauvegarder(d, dest, jour) is None
                and not sauvegarde.a_faire(dest, jour), ""))
    for k in range(1, 10):
        sauvegarde.sauvegarder(d, dest, jour + timedelta(days=k))
    restantes = sorted(p.name for p in dest.glob("Broutille_*.zip"))
    res.append(("7 dernières archives gardées", len(restantes) == 7 and restantes[-1] == "Broutille_2026-11-14.zip",
                f"{len(restantes)} : {restantes[0]} … {restantes[-1]}"))
    autre = Path(tempfile.mkdtemp(prefix="broutille_restaure_"))
    sauvegarde.restaurer(dest / restantes[-1], autre)
    res.append(("restauration : pesées retrouvées", "1200" in (autre / "registre.json").read_text(encoding="utf-8"), ""))
    absente = False
    try:
        sauvegarde.sauvegarder(d, dest / "cle_debranchee", jour)
    except OSError:
        absente = True
    res.append(("clé USB débranchée : erreur claire", absente, ""))
    for x in (d, dest, autre):
        shutil.rmtree(x, ignore_errors=True)
    return res


def main():
    resultats = essai_sauvegarde() + essai_clic() + essai_figee()
    ok = True
    for nom, reussi, detail in resultats:
        print(("OK   " if reussi else "RATÉ ") + nom, "—", detail)
        ok &= bool(reussi)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
