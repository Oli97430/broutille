"""Identité d'une tortue : dates partielles (naissance souvent connue à l'année près), âge lisible,
résumé d'une ligne. Fonctions pures, sans interface, testées dans tests/test_fiches.py.

Champs d'une fiche du registre (tous facultatifs sauf nom et espèce) :
  sexe        "Mâle" | "Femelle" | "" (inconnu)
  naissance   "AAAA", "AAAA-MM" ou "AAAA-MM-JJ"
  arrivee     même format : arrivée à la maison
  origine     texte libre (éleveur, refuge, née ici…)
  signes      signes distinctifs (écaille abîmée, marque…)
  notes       texte libre
  profil      nom de la photo de profil (album/<nom> ou <nom> de la galerie)
  carnet      [{"date": "AAAA-MM-JJ", "type": "Soin", "texte": "..."}] par ordre de date
"""
from datetime import date

SEXES = ("", "Mâle", "Femelle")
TYPES_CARNET = ("Note", "Soin", "Vétérinaire", "Vermifuge", "Hibernation", "Ponte", "Mue / carapace")
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre")


def lire_date_partielle(texte, aujourd_hui=None):
    """« 2019 », « 03/2019 », « 15/03/2019 » ou ISO → "AAAA", "AAAA-MM" ou "AAAA-MM-JJ".
    Chaîne vide → "". ValueError si la date est impossible ou dans le futur."""
    t = (texte or "").strip().replace(".", "/").replace("-", "/").replace(" ", "")
    if not t:
        return ""
    morceaux = t.split("/")
    if len(morceaux[0]) == 4:            # ISO : AAAA/MM/JJ
        morceaux = morceaux[::-1]
    if not all(m.isdigit() for m in morceaux) or len(morceaux) > 3:
        raise ValueError(f"date illisible : « {texte} »")
    annee = int(morceaux[-1])
    if annee < 100:                      # « 03/19 »
        annee += 2000
    mois = int(morceaux[-2]) if len(morceaux) >= 2 else None
    jour = int(morceaux[-3]) if len(morceaux) == 3 else None
    aujourd_hui = aujourd_hui or date.today()
    if not 1900 <= annee <= aujourd_hui.year:
        raise ValueError(f"année impossible : {annee}")
    if mois is None:
        return f"{annee:04d}"
    if not 1 <= mois <= 12:
        raise ValueError(f"mois impossible : {mois}")
    if jour is None:
        if (annee, mois) > (aujourd_hui.year, aujourd_hui.month):
            raise ValueError("date dans le futur")
        return f"{annee:04d}-{mois:02d}"
    d = date(annee, mois, jour)           # ValueError si le 31/02
    if d > aujourd_hui:
        raise ValueError("date dans le futur")
    return d.isoformat()


def date_lisible(valeur):
    """"2019" → "2019" ; "2019-03" → "mars 2019" ; "2019-03-15" → "15/03/2019" ; "" → ""."""
    if not valeur:
        return ""
    p = valeur.split("-")
    if len(p) == 1:
        return p[0]
    if len(p) == 2:
        return f"{MOIS[int(p[1]) - 1]} {p[0]}"
    return f"{p[2]}/{p[1]}/{p[0]}"


def date_saisie(valeur):
    """Valeur stockée → texte à remettre dans le champ de saisie."""
    if not valeur:
        return ""
    p = valeur.split("-")
    return "/".join(reversed(p))


def age_mois(naissance, aujourd_hui=None):
    """Âge en mois entiers (date partielle : on compte depuis le milieu de la période)."""
    if not naissance:
        return None
    aujourd_hui = aujourd_hui or date.today()
    p = [int(x) for x in naissance.split("-")]
    annee, mois, jour = p[0], (p[1] if len(p) > 1 else 7), (p[2] if len(p) > 2 else 1)
    m = (aujourd_hui.year - annee) * 12 + aujourd_hui.month - mois - (1 if aujourd_hui.day < jour else 0)
    return max(0, m)


def age_lisible(naissance, aujourd_hui=None):
    """"7 ans", "1 an et 3 mois", "5 mois", "moins d'un mois" ; "environ" si seule l'année est connue."""
    m = age_mois(naissance, aujourd_hui)
    if m is None:
        return ""
    environ = "environ " if len(naissance) == 4 else ""
    ans, reste = divmod(m, 12)
    if ans == 0:
        return environ + (f"{reste} mois" if reste else "moins d'un mois")
    texte = f"{ans} an{'s' if ans > 1 else ''}"
    if reste and ans < 3 and not environ:   # les mois ne comptent plus passé trois ans
        texte += f" et {reste} mois"
    return environ + texte


def resume_identite(fiche, aujourd_hui=None):
    """Une ligne : « Tortue d'Hermann · Femelle · 7 ans (née en 2019) »."""
    morceaux = [fiche.get("espece", "")]
    sexe = fiche.get("sexe", "")
    if sexe:
        morceaux.append(sexe)
    if fiche.get("naissance"):
        nee = "né" if sexe == "Mâle" else "née"
        quand = date_lisible(fiche["naissance"])
        prefixe = "le " if len(fiche["naissance"]) == 10 else "en "
        morceaux.append(f"{age_lisible(fiche['naissance'], aujourd_hui)} ({nee} {prefixe}{quand})")
    return "  ·  ".join(m for m in morceaux if m)
