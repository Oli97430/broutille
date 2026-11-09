"""
Broutille — repas sur 30 jours et fiche pour le vétérinaire.

  - repas_par_jour : minutes à table et visites de chaque jour, pour une tortue
  - graphique_repas : image PIL du graphique (barres par jour, moyenne)
  - fiche_veterinaire : PDF de deux pages (photo, résumé, graphique, dernières visites)

Rien ici ne dépend de Tkinter : le module se teste seul. Le PDF est fait avec Pillow,
sans autre bibliothèque.
"""

from datetime import date, datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import fiches

JOURS = 30
# page A4 à 150 points par pouce
PAGE = (1240, 1754)
MARGE = 90

# couleurs claires : la fiche s'imprime
ENCRE, GRIS, CLAIR, FILET = (25, 30, 24), (110, 118, 104), (238, 241, 234), (205, 211, 199)
VERT, AMBRE, ROUGE = (95, 150, 55), (196, 140, 40), (200, 60, 55)


def police(taille, gras=False):
    for nom in (["seguisb.ttf", "segoeuib.ttf", "arialbd.ttf"] if gras else ["segoeui.ttf", "arial.ttf"]):
        try:
            return ImageFont.truetype(nom, taille)
        except OSError:
            pass
    return ImageFont.load_default()


def _secondes(ligne):
    try:
        return float(ligne.get("duree_s") or 0)
    except ValueError:
        return 0.0


def visites_de(journal, cle):
    """Visites où la tortue est reconnue ou confirmée (id_individu), les plus récentes d'abord.
    Une simple proposition (« Zoé ? ») n'est pas comptée : elle n'est pas sûre."""
    return sorted((l for l in journal if l.get("id_individu") == cle),
                  key=lambda l: (l.get("date", ""), l.get("heure", "")), reverse=True)


def repas_par_jour(journal, cle, jours=JOURS, fin=None):
    """[(date, secondes, visites)] des `jours` derniers jours, du plus ancien au plus récent,
    jours sans visite compris (0)."""
    fin = fin or date.today()
    debut = fin - timedelta(days=jours - 1)
    cumul = {debut + timedelta(days=i): [0.0, 0] for i in range(jours)}
    for l in visites_de(journal, cle):
        try:
            jour = date.fromisoformat(l["date"])
        except (KeyError, ValueError):
            continue
        if jour in cumul:
            cumul[jour][0] += _secondes(l)
            cumul[jour][1] += 1
    return [(j, s, n) for j, (s, n) in sorted(cumul.items())]


def resume(series):
    """Chiffres de la période : visites, jours venue, temps total, moyenne par jour venu, plus
    longue absence (jours d'affilée sans visite, en comptant jusqu'à aujourd'hui)."""
    venus = [s for _j, s, n in series if n]
    absence, courante = 0, 0
    for _j, _s, n in series:
        courante = 0 if n else courante + 1
        absence = max(absence, courante)
    total = sum(s for _j, s, _n in series)
    return {"visites": sum(n for _j, _s, n in series), "jours_venue": len(venus), "jours": len(series),
            "total_s": total, "moyenne_s": total / len(venus) if venus else 0.0,
            "absence_max": absence, "absence_actuelle": courante}


def duree_lisible(secondes):
    secondes = int(round(secondes))
    if secondes < 60:
        return f"{secondes} s"
    if secondes < 3600:
        return f"{secondes // 60} min"
    return f"{secondes // 3600} h {secondes % 3600 // 60:02d}"


def graphique_repas(series, titre="", taille=(1060, 420), fond=(255, 255, 255), encre=ENCRE, discret=GRIS,
                    filet=FILET, barre=VERT, vide=ROUGE):
    """Graphique des minutes à table par jour : une barre par jour, la moyenne des jours venus
    en pointillé, un trait rouge sous les jours sans visite. Les couleurs se passent en
    paramètres : thème sombre de l'appli, ou clair pour l'impression."""
    l, h = taille
    img = Image.new("RGB", taille, fond)
    d = ImageDraw.Draw(img)
    f_titre, f_axe = police(max(14, h // 18), True), police(max(12, h // 24))
    haut = 0
    if titre:
        d.text((0, 0), titre, font=f_titre, fill=encre)
        haut = int(f_titre.size * 1.6)
    gauche, bas = int(f_axe.size * 4.2), int(f_axe.size * 2.4)
    x0, y0, x1, y1 = gauche, haut + 6, l - 8, h - bas
    minutes = [s / 60 for _j, s, _n in series]
    maxi = max(minutes + [1.0])
    pas = next((p for p in (1, 2, 5, 10, 15, 20, 30, 60, 120, 240, 480) if maxi / p <= 5), maxi / 5)
    plafond = pas * (int(maxi / pas) + 1)
    for k in range(0, int(plafond / pas) + 1):
        v = k * pas
        y = y1 - (y1 - y0) * v / plafond
        d.line([(x0, y), (x1, y)], fill=filet, width=1)
        d.text((x0 - 8, y), f"{v:g}", font=f_axe, fill=discret, anchor="rm")
    d.text((0, y0 - 2), "min", font=f_axe, fill=discret, anchor="la")
    n = len(series)
    largeur = (x1 - x0) / max(n, 1)
    for i, ((jour, s, nb), m) in enumerate(zip(series, minutes)):
        bx0, bx1 = x0 + i * largeur + largeur * 0.15, x0 + (i + 1) * largeur - largeur * 0.15
        if nb:
            d.rectangle([bx0, y1 - max(2, (y1 - y0) * m / plafond), bx1, y1], fill=barre)
        else:
            d.line([(bx0, y1 + 3), (bx1, y1 + 3)], fill=vide, width=3)
        if i % 5 == 0 or i == n - 1:
            d.text(((bx0 + bx1) / 2, y1 + 8), jour.strftime("%d/%m"), font=f_axe, fill=discret, anchor="ma")
    venus = [m for m, (_j, _s, nb) in zip(minutes, series) if nb]
    if venus:
        moy = sum(venus) / len(venus)
        y = y1 - (y1 - y0) * moy / plafond
        for x in range(x0, x1, 14):
            d.line([(x, y), (min(x + 7, x1), y)], fill=AMBRE, width=2)
        texte = f"moyenne {duree_lisible(moy * 60)} par jour venu"
        boite = d.textbbox((x1 - 4, y - 6), texte, font=f_axe, anchor="rd")
        d.rectangle([boite[0] - 6, boite[1] - 3, boite[2] + 4, boite[3] + 3], fill=fond)
        d.text((x1 - 4, y - 6), texte, font=f_axe, fill=AMBRE, anchor="rd")
    d.line([(x0, y1), (x1, y1)], fill=discret, width=1)
    return img


# ------------------------------------------------------------------ poids
def poids_lisible(g):
    """En grammes jusqu'à 10 kg (le vétérinaire suit le gramme), en kg au-delà."""
    if g >= 10000:
        return f"{g / 1000:.2f} kg".replace(".", ",")
    return f"{g:,.0f} g".replace(",", " ")


def bilan_poids(pesees, fin=None):
    """Dernier poids et variations : depuis la pesée précédente, sur 30 jours et sur un an
    (par rapport à la pesée la plus proche de cette date, avant elle). None si aucune pesée."""
    if not pesees:
        return None
    fin = fin or date.today()
    pesees = sorted(pesees, key=lambda p: p["date"])
    dernier = pesees[-1]

    def avant(jours):
        limite = (fin - timedelta(days=jours)).isoformat()
        anciennes = [p for p in pesees if p["date"] <= limite]
        return anciennes[-1] if anciennes else None

    def ecart(ref):
        if not ref or ref is dernier:
            return None
        return {"date": ref["date"], "g": dernier["g"] - ref["g"], "pct": 100 * (dernier["g"] - ref["g"]) / ref["g"]}

    precedente = pesees[-2] if len(pesees) > 1 else None
    b = {"dernier": dernier, "precedente": ecart(precedente), "mois": ecart(avant(30)), "an": ecart(avant(365)),
         "nombre": len(pesees)}
    # une perte de 10 % ou plus inquiète chez une tortue : on le signale
    pertes = [e["pct"] for e in (b["precedente"], b["mois"]) if e]
    b["alerte"] = bool(pertes) and min(pertes) <= -10
    return b


def ecart_lisible(e):
    if not e:
        return "—"
    signe = "+" if e["g"] >= 0 else "−"
    return f"{signe}{poids_lisible(abs(e['g']))} ({signe}{abs(e['pct']):.1f} %)".replace(".", ",")


def graphique_poids(pesees, titre="", taille=(1060, 420), fond=(255, 255, 255), encre=ENCRE, discret=GRIS,
                    filet=FILET, trait=VERT):
    """Courbe du poids : une pesée = un point, reliés dans l'ordre des dates ; l'axe du temps est
    à l'échelle (des pesées espacées restent espacées)."""
    l, h = taille
    img = Image.new("RGB", taille, fond)
    d = ImageDraw.Draw(img)
    f_titre, f_axe = police(max(14, h // 18), True), police(max(12, h // 24))
    haut = 0
    if titre:
        d.text((0, 0), titre, font=f_titre, fill=encre)
        haut = int(f_titre.size * 1.6)
    pesees = sorted(pesees, key=lambda p: p["date"])
    if not pesees:
        d.text((l / 2, h / 2), "Aucune pesée : ajoutez-en une.", font=f_titre, fill=discret, anchor="mm")
        return img
    gauche, bas = int(f_axe.size * 5.5), int(f_axe.size * 2.4)
    x0, y0, x1, y1 = gauche, haut + 10, l - 24, h - bas
    jours = [date.fromisoformat(p["date"]) for p in pesees]
    poids = [p["g"] for p in pesees]
    j0, j1 = jours[0], max(jours[-1], jours[0] + timedelta(days=30))
    bas_g, haut_g = min(poids), max(poids)
    marge = max((haut_g - bas_g) * 0.15, haut_g * 0.03, 5)
    bas_g, haut_g = max(0, bas_g - marge), haut_g + marge
    etendue = haut_g - bas_g
    pas = next((p for p in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000, 10000, 20000, 50000)
                if etendue / p <= 6), etendue / 6)
    v = pas * int(bas_g / pas)
    while v <= haut_g:
        if v >= bas_g:
            y = y1 - (y1 - y0) * (v - bas_g) / etendue
            d.line([(x0, y), (x1, y)], fill=filet, width=1)
            d.text((x0 - 8, y), poids_lisible(v), font=f_axe, fill=discret, anchor="rm")
        v += pas

    def position(jour, g):
        return (x0 + (x1 - x0) * (jour - j0).days / max((j1 - j0).days, 1),
                y1 - (y1 - y0) * (g - bas_g) / etendue)

    points = [position(j, g) for j, g in zip(jours, poids)]
    if len(points) > 1:
        d.line(points, fill=trait, width=3, joint="curve")
    for (x, y), g in zip(points, poids):
        d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=trait, outline=fond, width=2)
    x, y = points[-1]
    d.text((x, y - 12), poids_lisible(poids[-1]), font=f_axe, fill=encre, anchor="rb" if x > x1 - 80 else "mb")
    # repères de date : début, fin, et quelques-uns entre
    n_reperes = 5
    for k in range(n_reperes + 1):
        jour = j0 + timedelta(days=round((j1 - j0).days * k / n_reperes))
        x = position(jour, bas_g)[0]
        ancre = "la" if k == 0 else "ra" if k == n_reperes else "ma"     # rien ne dépasse du cadre
        d.text((x, y1 + 8), jour.strftime("%d/%m/%y"), font=f_axe, fill=discret, anchor=ancre)
    d.line([(x0, y1), (x1, y1)], fill=discret, width=1)
    return img


# ------------------------------------------------------------------ fiche PDF
def _vignette(chemin, boite):
    try:
        img = Image.open(chemin).convert("RGB")
    except (OSError, ValueError):
        return None
    img.thumbnail(boite)
    return img


def _ligne_tableau(d, y, cellules, largeurs, f, couleur=ENCRE):
    x = MARGE
    for texte, larg in zip(cellules, largeurs):
        d.text((x, y), str(texte), font=f, fill=couleur)
        x += larg


def fiche_veterinaire(chemin_pdf, dossier, fiche, cle, journal, jours=JOURS, fin=None, galerie=None):
    """Écrit la fiche PDF d'une tortue. fiche : {"nom", "espece", ...} du registre ;
    galerie : dossier des photos de référence (individus/<cle>). Renvoie le chemin écrit."""
    dossier = Path(dossier)
    fin = fin or date.today()
    series = repas_par_jour(journal, cle, jours, fin)
    r = resume(series)
    visites = visites_de(journal, cle)
    f_titre, f_sous, f_gras, f_texte, f_petit = police(54, True), police(30), police(28, True), police(26), police(21)

    page1 = Image.new("RGB", PAGE, "white")
    d = ImageDraw.Draw(page1)
    y = MARGE
    titre = fiche.get("nom", "Tortue")
    while d.textlength(titre, font=f_titre) > PAGE[0] - 2 * MARGE - 360 and len(titre) > 4:
        titre = titre[:-2].rstrip() + "…" if not titre.endswith("…") else titre[:-2] + "…"
    d.text((MARGE, y), titre, font=f_titre, fill=ENCRE)
    y += 70
    d.text((MARGE, y), fiches.resume_identite(fiche, fin), font=f_sous, fill=GRIS)
    d.text((PAGE[0] - MARGE, MARGE + 12), f"Fiche du {fin.strftime('%d/%m/%Y')}", font=f_texte, fill=GRIS, anchor="ra")
    d.text((PAGE[0] - MARGE, MARGE + 50), f"Réf. {cle}", font=f_petit, fill=GRIS, anchor="ra")
    y += 60
    d.line([(MARGE, y), (PAGE[0] - MARGE, y)], fill=FILET, width=2)
    y += 30

    # photos de référence : les trois premières de la galerie
    photos = sorted(Path(galerie).glob("*.jpg"))[:3] if galerie and Path(galerie).is_dir() else []
    x = MARGE
    hauteur_photos = 0
    for p in photos:
        v = _vignette(p, (330, 300))
        if v:
            page1.paste(v, (x, y))
            x += v.width + 20
            hauteur_photos = max(hauteur_photos, v.height)
    if not photos:
        d.text((MARGE, y), "Pas de photo de référence dans la galerie.", font=f_texte, fill=GRIS)
        hauteur_photos = 40
    y += hauteur_photos + 40

    d.text((MARGE, y), f"Repas des {jours} derniers jours (du {series[0][0].strftime('%d/%m')} au "
                       f"{series[-1][0].strftime('%d/%m/%Y')})", font=f_gras, fill=ENCRE)
    y += 50
    lignes = [
        ("Visites à la mangeoire", r["visites"]),
        ("Jours où elle est venue", f"{r['jours_venue']} sur {r['jours']}"),
        ("Temps total à table", duree_lisible(r["total_s"])),
        ("Moyenne par jour venu", duree_lisible(r["moyenne_s"])),
        ("Plus longue absence", f"{r['absence_max']} jour{'s' if r['absence_max'] > 1 else ''}"),
        ("Dernière visite", f"{visites[0]['date'][8:10]}/{visites[0]['date'][5:7]}/{visites[0]['date'][:4]} à {visites[0].get('heure', '')[:5]}"
         if visites else "aucune"),
    ]
    if fiche.get("arrivee"):
        lignes.append(("Arrivée à la maison", fiches.date_lisible(fiche["arrivee"])))
    if fiche.get("signes"):
        lignes.append(("Signes distinctifs", fiche["signes"][:38] + ("…" if len(fiche["signes"]) > 38 else "")))
    bp = bilan_poids(fiche.get("pesees", []), fin)
    if bp:
        jour = bp["dernier"]["date"]
        lignes.append(("Dernier poids", f"{poids_lisible(bp['dernier']['g'])} le {jour[8:10]}/{jour[5:7]}/{jour[:4]}"))
    for etiquette, valeur in lignes:
        d.text((MARGE, y), etiquette, font=f_texte, fill=GRIS)
        d.text((MARGE + 520, y), str(valeur), font=f_texte, fill=ENCRE)
        y += 42
    if r["absence_actuelle"] >= 3:
        y += 6
        d.text((MARGE, y), f"Pas vue depuis {r['absence_actuelle']} jours.", font=f_gras, fill=ROUGE)
        y += 44
    y += 24
    graphe = graphique_repas(series, "Minutes à table par jour", (PAGE[0] - 2 * MARGE, 520))
    page1.paste(graphe, (MARGE, y))
    y += graphe.height + 30
    d.text((MARGE, y), "Les barres comptent les visites où la tortue a été reconnue ou confirmée. Un trait rouge "
                       "marque un jour sans visite.", font=f_petit, fill=GRIS)
    y += 32
    d.text((MARGE, y), "Durées mesurées par vidéo : elles indiquent la présence à la mangeoire, pas la quantité "
                       "mangée.", font=f_petit, fill=GRIS)
    d.text((PAGE[0] / 2, PAGE[1] - 60), "Broutille — page 1/2", font=f_petit, fill=GRIS, anchor="ma")

    # page 2 : poids, puis dernières visites, avec la photo de la tortue quand elle existe encore
    page2 = Image.new("RGB", PAGE, "white")
    d = ImageDraw.Draw(page2)
    y = MARGE
    d.text((MARGE, y), f"{fiche.get('nom', 'Tortue')} — poids", font=f_gras, fill=ENCRE)
    y += 54
    max_visites = 18
    if bp:
        for etiquette, valeur in (("Pesées enregistrées", bp["nombre"]),
                                  ("Depuis la pesée précédente", ecart_lisible(bp["precedente"])),
                                  ("Sur 30 jours", ecart_lisible(bp["mois"])),
                                  ("Sur un an", ecart_lisible(bp["an"]))):
            d.text((MARGE, y), etiquette, font=f_texte, fill=GRIS)
            d.text((MARGE + 520, y), str(valeur), font=f_texte, fill=ENCRE)
            y += 40
        if bp["alerte"]:
            d.text((MARGE, y), "Perte de poids de 10 % ou plus.", font=f_gras, fill=ROUGE)
            y += 44
        y += 10
        graphe = graphique_poids(fiche.get("pesees", []), "", (PAGE[0] - 2 * MARGE, 400))
        page2.paste(graphe, (MARGE, y))
        y += graphe.height + 50
        max_visites = 8
    else:
        d.text((MARGE, y), "Aucune pesée enregistrée.", font=f_texte, fill=GRIS)
        y += 70
    d.text((MARGE, y), "Dernières visites", font=f_gras, fill=ENCRE)
    y += 56
    largeurs = (230, 140, 170, 240)
    _ligne_tableau(d, y, ("Date", "Heure", "Durée", "Remarque"), largeurs, f_gras, GRIS)
    y += 46
    d.line([(MARGE, y - 8), (PAGE[0] - MARGE, y - 8)], fill=FILET, width=2)
    vignettes = []
    for l in visites[:max_visites]:
        jour = l.get("date", "")
        remarque = "corrigée à la main" if l.get("corrige") else ""
        _ligne_tableau(d, y, (f"{jour[8:10]}/{jour[5:7]}/{jour[:4]}", l.get("heure", "")[:5],
                              duree_lisible(_secondes(l)), remarque), largeurs, f_texte)
        y += 40
        photo = dossier / f"{l.get('id_visite', '')}_tortue.jpg"
        if photo.exists() and len(vignettes) < 8:
            vignettes.append((photo, jour))
    if not visites:
        d.text((MARGE, y), "Aucune visite enregistrée.", font=f_texte, fill=GRIS)
        y += 40
    if vignettes:
        y += 30
        d.text((MARGE, y), "Photos des dernières visites", font=f_gras, fill=ENCRE)
        y += 50
        x = MARGE
        for photo, jour in vignettes:
            v = _vignette(photo, (240, 200))
            if v is None:
                continue
            if x + v.width > PAGE[0] - MARGE:
                x, y = MARGE, y + 250
            if y + v.height > PAGE[1] - 120:
                break
            page2.paste(v, (x, y))
            d.text((x, y + v.height + 6), f"{jour[8:10]}/{jour[5:7]}", font=f_petit, fill=GRIS)
            x += v.width + 22
    d.text((PAGE[0] / 2, PAGE[1] - 60), "Broutille — page 2/2", font=f_petit, fill=GRIS, anchor="ma")

    chemin_pdf = Path(chemin_pdf)
    page1.save(chemin_pdf, "PDF", resolution=150, save_all=True, append_images=[page2])
    return chemin_pdf


def nom_fichier_fiche(fiche, jour=None):
    jour = jour or date.today()
    nom = "".join(c if c.isalnum() or c in " -_" else "_" for c in fiche.get("nom", "tortue")).strip() or "tortue"
    return f"Fiche {nom} {jour.strftime('%Y-%m-%d')}.pdf"


if __name__ == "__main__":       # essai rapide : python rapports.py <dossier Broutille> <clé>
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from broutille_cam import Registre, lire_journal
    dossier = Path(sys.argv[1])
    reg = Registre(dossier)
    reg.charger()
    cle = sys.argv[2]
    sortie = fiche_veterinaire(dossier / nom_fichier_fiche(reg.fiches[cle]), dossier, reg.fiches[cle], cle,
                               lire_journal(dossier), galerie=reg.dossier / cle)
    print(sortie, datetime.now())
