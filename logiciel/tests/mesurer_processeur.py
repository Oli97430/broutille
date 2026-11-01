"""
Temps et mémoire d'une analyse complète, carte graphique masquée : base de la configuration minimale.

    python tests/mesurer_processeur.py
"""

import ctypes
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vision

vision.appareil = lambda: "cpu"      # tous les modèles passent par là : le GPU reste hors du jeu


class Memoire(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("a", ctypes.c_size_t), ("b", ctypes.c_size_t), ("c", ctypes.c_size_t),
                ("d", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


def pic_memoire():
    m = Memoire(cb=ctypes.sizeof(Memoire))
    k = ctypes.WinDLL("kernel32")
    k.GetCurrentProcess.restype = ctypes.c_void_p
    ctypes.WinDLL("psapi").GetProcessMemoryInfo(ctypes.c_void_p(k.GetCurrentProcess()), ctypes.byref(m), m.cb)
    return m.PeakWorkingSetSize / 1024 ** 3


def main():
    import torch
    print("appareil :", vision.appareil(), "| fils :", torch.get_num_threads(), "| processeur :", os.environ.get("PROCESSOR_IDENTIFIER", "?"))
    t = time.time()
    det, esp, des = vision.DetecteurTortues(), vision.ClasseurEspeces(), vision.Descripteur()
    det.charger(), esp.charger(), des.charger()
    print(f"chargement des modèles : {time.time() - t:.0f} s, mémoire {pic_memoire():.1f} Go")
    p = sorted((Path(__file__).parent / "photos_inat" / "radiata").glob("*.jpg"))[:12]
    images = [cv2.resize(cv2.imdecode(np.fromfile(str(x), np.uint8), 1), (1920, 1080)) for x in p]
    temps = {"détection": [], "espèce": [], "isolement": [], "identité": [], "SIFT": [], "total": []}
    for fils in (torch.get_num_threads(), 4, 2):
        torch.set_num_threads(fils)
        for v in temps.values():
            v.clear()
        for image in images:
            t0 = time.time()
            d = det.detecter(image)
            t1 = time.time()
            if not d:
                continue
            boite = d[0][1]
            esp.classer(vision.recadrer(image, boite))
            t2 = time.time()
            tortue = vision.isoler_tortue(image, boite)
            t3 = time.time()
            des.decrire(tortue)
            t4 = time.time()
            vision.points_sift(tortue)
            t5 = time.time()
            for nom, debut, fin in (("détection", t0, t1), ("espèce", t1, t2), ("isolement", t2, t3), ("identité", t3, t4),
                                    ("SIFT", t4, t5), ("total", t0, t5)):
                temps[nom].append(fin - debut)
        print(f"{fils} fils : " + ", ".join(f"{n} {np.median(v[1:]):.2f} s" for n, v in temps.items()), flush=True)
    print(f"pic de mémoire : {pic_memoire():.1f} Go")
    if torch.cuda.is_available():
        vision.appareil = lambda: "cuda"
        det, esp, des = vision.DetecteurTortues(), vision.ClasseurEspeces(), vision.Descripteur()
        det.charger(), esp.charger(), des.charger()
        for image in images:
            d = det.detecter(image)
            if d:
                esp.classer(vision.recadrer(image, d[0][1]))
                des.decrire(vision.isoler_tortue(image, d[0][1]))
        print(f"mémoire de la carte graphique : {torch.cuda.max_memory_reserved() / 1024 ** 3:.1f} Go")


if __name__ == "__main__":
    main()
