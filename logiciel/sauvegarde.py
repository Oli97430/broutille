"""
Broutille — sauvegarde quotidienne.

Une archive « Broutille_AAAA-MM-JJ.zip » par jour dans le dossier choisi (clé USB, OneDrive,
autre disque) : le journal des visites, les fiches des tortues (pesées comprises), leurs
galeries de photos et les « Pas une tortue ». Les clips vidéo ne sont pas sauvegardés : trop
lourds, et le ménage les efface de toute façon. Les GARDER dernières archives sont gardées.
"""

import zipfile
from datetime import date
from pathlib import Path

GARDER = 7
FICHIERS = ("visites.csv", "visites_en_attente.jsonl", "registre.json", "registre.bak")
DOSSIERS = ("individus", "pas_une_tortue")
PREFIXE = "Broutille_"


def nom_archive(jour=None):
    return f"{PREFIXE}{(jour or date.today()).isoformat()}.zip"


def a_faire(destination, jour=None):
    """Vrai si la sauvegarde du jour manque."""
    return bool(destination) and not (Path(destination) / nom_archive(jour)).exists()


def sauvegarder(dossier, destination, jour=None, garder=GARDER):
    """Écrit l'archive du jour (sans rien écraser si elle existe déjà) et efface les plus
    anciennes au-delà de `garder`. Renvoie (chemin, nombre de fichiers) ou None si déjà faite.
    OSError si la destination est absente (clé USB débranchée) ou pleine."""
    dossier, destination = Path(dossier), Path(destination)
    if not destination.is_dir():
        raise OSError(f"dossier de sauvegarde introuvable : {destination}")
    final = destination / nom_archive(jour)
    if final.exists():
        return None
    tmp = final.with_suffix(".tmp")
    n = 0
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for nom in FICHIERS:
            p = dossier / nom
            if p.is_file():
                z.write(p, nom)
                n += 1
        for nom in DOSSIERS:
            racine = dossier / nom
            if not racine.is_dir():
                continue
            for p in sorted(racine.rglob("*")):
                if p.is_file() and p.suffix != ".tmp":
                    z.write(p, p.relative_to(dossier).as_posix())
                    n += 1
    tmp.replace(final)          # une archive à moitié écrite (clé arrachée) ne passe jamais pour bonne
    anciennes = sorted(destination.glob(f"{PREFIXE}????-??-??.zip"))
    for p in anciennes[:-garder] if garder else []:
        p.unlink(missing_ok=True)
    return final, n


def restaurer(archive, dossier):
    """Remet une archive dans le dossier des visites. Les fichiers présents sont remplacés ;
    à faire Broutille fermé."""
    with zipfile.ZipFile(archive) as z:
        for membre in z.namelist():
            if membre.startswith("/") or ".." in Path(membre).parts:
                raise ValueError(f"archive suspecte : {membre}")
        z.extractall(dossier)
