"""
Broutille — comportement des tortues, tiré du journal des visites.

  - rythme        : minutes à table par heure de la journée, régularité de l'arrivée
  - reseau_social : temps passé ensemble à la mangeoire, par paire, et indice d'affinité
  - dominance     : qui fait partir qui (une tortue arrive, l'autre s'en va peu après)
  - sante         : la dernière semaine comparée aux habitudes de la tortue

Seules les visites nommées (id_individu) comptent : une « Inconnue » ne dit rien d'une tortue.
Rien ici ne dépend de Tkinter. Les images sont faites avec Pillow, comme dans rapports.py.
"""

import math
from collections import defaultdict
from datetime import date, datetime, timedelta

from PIL import Image, ImageDraw

from rapports import AMBRE, ENCRE, FILET, GRIS, VERT, police

DEPLACEMENT_S = 60       # partie moins d'une minute après l'arrivée de l'autre : déplacée
ENSEMBLE_MIN_S = 5       # en dessous, deux visites qui se touchent ne comptent pas comme un repas partagé
SEMAINE = 7


# ------------------------------------------------------------------ lecture
def sejours(journal, jours=None, fin=None):
    """[(cle, debut, fin)] des visites nommées, triées par début. jours : seulement les N derniers."""
    fin_periode = datetime.combine(fin or date.today(), datetime.max.time())
    debut_periode = fin_periode - timedelta(days=jours) if jours else None
    res = []
    for l in journal:
        cle = l.get("id_individu")
        if not cle:
            continue
        try:
            debut = datetime.fromisoformat(f"{l['date']}T{l['heure']}")
            duree = float(l.get("duree_s") or 0)
        except (KeyError, ValueError):
            continue
        if debut > fin_periode or (debut_periode and debut < debut_periode):
            continue
        res.append((cle, debut, debut + timedelta(seconds=duree)))
    return sorted(res, key=lambda s: s[1])


def noms(journal):
    """Dernier nom connu de chaque tortue (les visites portent le nom du moment)."""
    n = {}
    for l in journal:
        if l.get("id_individu"):
            n[l["id_individu"]] = l.get("individu", l["id_individu"])
    return n


# ------------------------------------------------------------------ rythme
def rythme(liste):
    """{cle: [24 valeurs]} : minutes à table par heure de la journée, la durée répartie sur les
    heures qu'elle couvre (une visite de 12 h 50 à 13 h 10 compte pour les deux heures)."""
    r = defaultdict(lambda: [0.0] * 24)
    for cle, debut, fin in liste:
        t = debut
        while t < fin:
            prochaine = (t + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            bout = min(fin, prochaine)
            r[cle][t.hour] += (bout - t).total_seconds() / 60
            t = bout
    return dict(r)


def regularite(liste):
    """{cle: {"jours", "arrivee_moy" (heure décimale), "ecart_min" (écart type de la 1re arrivée)}}."""
    premieres = defaultdict(dict)
    for cle, debut, _fin in liste:
        jour = debut.date()
        h = debut.hour + debut.minute / 60 + debut.second / 3600
        premieres[cle][jour] = min(premieres[cle].get(jour, 24), h)
    res = {}
    for cle, par_jour in premieres.items():
        heures = list(par_jour.values())
        moy = sum(heures) / len(heures)
        ecart = math.sqrt(sum((h - moy) ** 2 for h in heures) / len(heures)) * 60
        res[cle] = {"jours": len(heures), "arrivee_moy": moy, "ecart_min": ecart}
    return res


def heure_lisible(h):
    m = round(h * 60)
    return f"{m // 60 % 24:02d} h {m % 60:02d}"


# ------------------------------------------------------------------ réseau social
def reseau_social(liste):
    """{(a, b): {"ensemble_s", "fois", "affinite"}} pour chaque paire vue ensemble.
    affinité = temps ensemble / temps où au moins l'une des deux est là (0 à 1) : 1 si elles
    mangent toujours ensemble, proche de 0 si elles se croisent à peine."""
    total = defaultdict(float)
    for cle, debut, fin in liste:
        total[cle] += (fin - debut).total_seconds()
    ensemble = defaultdict(float)
    fois = defaultdict(int)
    for i, (a, da, fa) in enumerate(liste):
        for b, db, fb in liste[i + 1:]:
            if db >= fa:
                break                       # triées par début : plus aucune ne chevauche a
            if a == b:
                continue
            commun = (min(fa, fb) - max(da, db)).total_seconds()
            if commun >= ENSEMBLE_MIN_S:
                paire = tuple(sorted((a, b)))
                ensemble[paire] += commun
                fois[paire] += 1
    res = {}
    for paire, s in ensemble.items():
        union = total[paire[0]] + total[paire[1]] - s
        res[paire] = {"ensemble_s": s, "fois": fois[paire], "affinite": s / union if union > 0 else 0.0}
    return res


# ------------------------------------------------------------------ dominance
def dominance(liste, delai=DEPLACEMENT_S):
    """Déplacements : B arrive pendant que A mange, A part moins de `delai` secondes après, et B
    reste au moins aussi longtemps. Renvoie (comptes {(gagnante, perdante): n},
    classement [(cle, gagnes, perdus, score)] du plus dominant au moins dominant)."""
    comptes = defaultdict(int)
    for i, (a, da, fa) in enumerate(liste):
        for b, db, fb in liste[i + 1:]:     # triées par début : seules les suivantes arrivent après a
            if db >= fa:
                break
            if a != b and db > da and (fa - db).total_seconds() <= delai and fb >= fa:
                comptes[(b, a)] += 1
    gagnes, perdus = defaultdict(int), defaultdict(int)
    for (g, p), n in comptes.items():
        gagnes[g] += n
        perdus[p] += n
    cles = set(gagnes) | set(perdus)
    # score : part des déplacements gagnés, lissée (une seule rencontre ne fait pas une reine)
    classement = sorted(((c, gagnes[c], perdus[c], (gagnes[c] + 1) / (gagnes[c] + perdus[c] + 2)) for c in cles),
                        key=lambda x: (-x[3], -x[1]))
    return dict(comptes), classement


# ------------------------------------------------------------------ santé
def sante(liste, fin=None, semaine=SEMAINE, reference=30):
    """Pour chaque tortue : minutes par jour sur la dernière semaine, comparées aux `reference`
    jours d'avant ; alerte si elle mange deux fois moins, ou si elle n'est pas venue depuis 3 jours
    alors qu'elle venait presque tous les jours. Une tortue suivie depuis moins de 3 jours n'a pas
    encore d'habitudes : pas d'alerte."""
    fin = fin or date.today()
    debut_semaine = fin - timedelta(days=semaine - 1)
    debut_ref = debut_semaine - timedelta(days=reference)
    par = defaultdict(lambda: {"semaine_s": 0.0, "ref_s": 0.0, "jours_ref": set(), "derniere": None,
                               "premiere": None, "arrivees_sem": [], "arrivees_ref": []})
    for cle, debut, f in liste:
        p = par[cle]
        jour = debut.date()
        p["derniere"] = max(p["derniere"] or jour, jour)
        p["premiere"] = min(p["premiere"] or jour, jour)
        s = (f - debut).total_seconds()
        h = debut.hour + debut.minute / 60
        if debut_semaine <= jour <= fin:
            p["semaine_s"] += s
            p["arrivees_sem"].append(h)
        elif debut_ref <= jour < debut_semaine:
            p["ref_s"] += s
            p["jours_ref"].add(jour)
            p["arrivees_ref"].append(h)
    res = {}
    for cle, p in par.items():
        jours_ref = max(1, min(reference, (debut_semaine - max(p["premiere"], debut_ref)).days))
        par_jour_sem = p["semaine_s"] / 60 / semaine
        par_jour_ref = p["ref_s"] / 60 / jours_ref if p["ref_s"] else None
        absente = (fin - p["derniere"]).days
        assidue = len(p["jours_ref"]) >= 0.7 * jours_ref
        alertes = []
        if par_jour_ref and (fin - p["premiere"]).days >= 3:
            if par_jour_sem < 0.5 * par_jour_ref:
                alertes.append(f"mange deux fois moins ({par_jour_sem:.0f} min/j contre {par_jour_ref:.0f})")
            if absente >= 3 and assidue:
                alertes.append(f"pas venue depuis {absente} jours")
            if p["arrivees_sem"] and p["arrivees_ref"]:
                decalage = (sum(p["arrivees_sem"]) / len(p["arrivees_sem"])
                            - sum(p["arrivees_ref"]) / len(p["arrivees_ref"]))
                if abs(decalage) >= 2:
                    alertes.append(f"arrive {abs(decalage):.0f} h plus {'tard' if decalage > 0 else 'tôt'}")
        res[cle] = {"semaine_min_j": par_jour_sem, "ref_min_j": par_jour_ref, "absente_j": absente,
                    "alertes": alertes}
    return res


# ------------------------------------------------------------------ images
def image_rythme(r, noms_, taille=(980, 60), fond=(255, 255, 255), encre=ENCRE, discret=GRIS, chaud=VERT):
    """Carte de chaleur : une ligne par tortue, une case par heure, plus foncée quand elle mange."""
    cles = sorted(r, key=lambda c: -sum(r[c]))
    f = police(14)
    gauche, haut, ligne = 170, 30, 30
    l = taille[0]
    h = haut + ligne * max(1, len(cles)) + 10
    img = Image.new("RGB", (l, h), fond)
    d = ImageDraw.Draw(img)
    case = (l - gauche - 10) / 24
    for heure in range(0, 24, 2):
        d.text((gauche + heure * case + case / 2, 6), f"{heure}h", font=f, fill=discret, anchor="ma")
    for i, cle in enumerate(cles):
        y = haut + i * ligne
        d.text((gauche - 10, y + ligne / 2), noms_.get(cle, cle)[:18], font=f, fill=encre, anchor="rm")
        maxi = max(r[cle]) or 1
        for heure, v in enumerate(r[cle]):
            a = v / maxi
            couleur = tuple(int(fc + (cc - fc) * a) for fc, cc in zip(fond, chaud))
            d.rectangle([gauche + heure * case + 1, y + 2, gauche + (heure + 1) * case - 1, y + ligne - 3], fill=couleur)
    return img


def image_reseau(reseau, totaux, noms_, taille=(620, 520), fond=(255, 255, 255), encre=ENCRE, discret=GRIS,
                 trait=VERT, filet=FILET):
    """Les tortues en cercle ; un trait par paire vue ensemble, plus épais quand l'affinité est forte.
    La taille du rond suit le temps total à table."""
    l, h = taille
    img = Image.new("RGB", taille, fond)
    d = ImageDraw.Draw(img)
    f = police(14)
    cles = sorted(totaux, key=lambda c: -totaux[c])
    if not cles:
        d.text((l / 2, h / 2), "Pas encore de visites nommées", font=police(18), fill=discret, anchor="mm")
        return img
    cx, cy, rayon = l / 2, h / 2, min(l, h) / 2 - 70
    pos = {c: (cx + rayon * math.cos(2 * math.pi * i / len(cles) - math.pi / 2),
               cy + rayon * math.sin(2 * math.pi * i / len(cles) - math.pi / 2)) for i, c in enumerate(cles)}
    maxi = max((v["affinite"] for v in reseau.values()), default=0) or 1
    for (a, b), v in sorted(reseau.items(), key=lambda x: x[1]["affinite"]):
        if a in pos and b in pos:
            e = max(1, int(12 * v["affinite"] / maxi))
            d.line([pos[a], pos[b]], fill=trait if v["affinite"] >= 0.5 * maxi else filet, width=e)
    tmax = max(totaux.values()) or 1
    for c in cles:
        x, y = pos[c]
        r = 8 + 18 * math.sqrt(totaux[c] / tmax)
        d.ellipse([x - r, y - r, x + r, y + r], fill=AMBRE, outline=encre)
        d.text((x, y + r + 4), noms_.get(c, c)[:16], font=f, fill=encre, anchor="ma")
    return img

