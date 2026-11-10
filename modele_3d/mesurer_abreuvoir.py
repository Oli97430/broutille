"""Contrôle du STL de l'abreuvoir : dimensions, fond à plat, surplombs, eau et pentes."""

import re
from pathlib import Path

import numpy as np

ICI = Path(__file__).parent
texte = (ICI / "stl" / "broutille_abreuvoir.stl").read_text()
v = np.array(re.findall(r"vertex\s+(\S+)\s+(\S+)\s+(\S+)", texte), float).reshape(-1, 3, 3)
p = v.reshape(-1, 3)
print("dimensions", np.round(p.max(0) - p.min(0), 1), "x", p[:, 0].min().round(1), p[:, 0].max().round(1), "zmin", p[:, 2].min())
n = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
aire = np.linalg.norm(n, axis=1) / 2
n = n / np.maximum(2 * aire[:, None], 1e-9)
hauteur = v[..., 2].mean(1)
vers_bas = (n[:, 2] < -0.01) & (hauteur > 0.02)
angle = np.degrees(np.arccos(np.clip(-n[:, 2], -1, 1)))     # 0 = plafond plat, 90 = paroi verticale
print("surplomb de plus de 45° :", round(aire[vers_bas & (angle < 45)].sum()), "mm²")
print("sous le plateau :", round(aire[(n[:, 2] < -0.99) & (hauteur < 0.02)].sum() / 100), "cm² posés à plat")
print("volume de matière :", round(abs(np.einsum("ij,ij->i", v[:, 0], np.cross(v[:, 1], v[:, 2])).sum() / 6) / 1000), "cm³")

parametres = dict(re.findall(r"^(\w+)\s*=\s*([\d.]+);", (ICI / "abreuvoir.scad").read_text(encoding="utf-8"), re.M))
g = {k: float(x) for k, x in parametres.items()}
niveaux = [(g["a_plat"], g["b_plat"], g["fond"]), (g["a_plat"] + 8, g["b_plat"] + 8, g["fond"] + 4),
           (g["a_bassin"], g["b_bassin"], g["h_rim"])]


def demi_axes(z):
    for (a0, b0, z0), (a1, b1, z1) in zip(niveaux, niveaux[1:]):
        if z <= z1:
            f = (z - z0) / (z1 - z0)
            return a0 + f * (a1 - a0), b0 + f * (b1 - b0)


for profondeur in (8, 10, 12, 14):
    zs = np.linspace(g["fond"], g["fond"] + profondeur, 200)
    aires = [np.pi * demi_axes(z)[0] * demi_axes(z)[1] for z in zs]
    print(f"eau à {profondeur} mm : {np.trapezoid(aires, zs) / 1000:.0f} ml")
rampe = np.degrees(np.arctan((g["h_rim"] - 1.2) / (g["a_base"] - g["a_rim"])))
print(f"pente de la rampe : {rampe:.0f}° ; pente de la cuvette : "
      f"{np.degrees(np.arctan((g['h_rim'] - g['fond'] - 4) / (g['a_bassin'] - g['a_plat'] - 8))):.0f}°")
