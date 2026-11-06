"""
Broutille — lancement au démarrage de Windows.

Un raccourci « Broutille.lnk » dans le dossier Démarrage de l'utilisateur lance l'appli sans
console. Il est créé ou retiré depuis les Réglages ; aucun droit administrateur n'est demandé.
"""

import os
import subprocess
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
NOM_RACCOURCI = "Broutille.lnk"
# raccourci d'EZVIZ Studio créé par son installateur, s'il existe
EZVIZ_MENU = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / \
    r"Microsoft\Windows\Start Menu\Programs\hicloud\Ezviz Studio\Ezviz Studio.lnk"


def dossier_demarrage():
    return Path(os.environ["APPDATA"]) / r"Microsoft\Windows\Start Menu\Programs\Startup"


def raccourci():
    return dossier_demarrage() / NOM_RACCOURCI


def programme_conseille():
    """Programme à ouvrir avant la surveillance : EZVIZ Studio s'il est installé."""
    return str(EZVIZ_MENU) if EZVIZ_MENU.exists() else ""


def _pythonw():
    candidat = Path(sys.executable).with_name("pythonw.exe")
    return candidat if candidat.exists() else Path(sys.executable)


def _powershell(script):
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                       capture_output=True, text=True, timeout=30,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0:
        raise OSError(r.stderr.strip() or "raccourci impossible")


def est_active():
    return raccourci().exists()


def activer(cible=None):
    """Crée le raccourci de démarrage : pythonw broutille_app.py --demarrage, dans ce dossier.
    cible : dossier de destination du raccourci (essais) ; par défaut le dossier Démarrage."""
    lien = Path(cible) / NOM_RACCOURCI if cible else raccourci()
    lien.parent.mkdir(parents=True, exist_ok=True)
    echapper = lambda t: str(t).replace("'", "''")
    _powershell(
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('" + echapper(lien) + "');"
        "$s.TargetPath = '" + echapper(_pythonw()) + "';"
        "$s.Arguments = '\"" + echapper(ICI / "broutille_app.py") + "\" --demarrage';"
        "$s.WorkingDirectory = '" + echapper(ICI) + "';"
        "$s.IconLocation = '" + echapper(ICI / "broutille.ico") + "';"
        "$s.Description = 'Broutille : surveillance de la mangeoire';"
        "$s.Save()")
    return lien


def desactiver(cible=None):
    lien = Path(cible) / NOM_RACCOURCI if cible else raccourci()
    lien.unlink(missing_ok=True)


def lancer_programme(chemin, sans_admin=False):
    """Ouvre un programme ou un raccourci. sans_admin : même s'il demande les droits
    administrateur (EZVIZ Studio), il est lancé avec les droits ordinaires, comme Broutille ;
    sans quoi Windows interdit à Broutille de cliquer dedans pour relancer le direct.
    Un programme qui a vraiment besoin de ces droits peut alors mal fonctionner."""
    chemin = Path(chemin)
    if not sans_admin:
        os.startfile(chemin)
        return
    cible, arguments, dossier = chemin, "", chemin.parent
    if chemin.suffix.lower() == ".lnk":
        lu = lire_raccourci(chemin) + ("", "", "")
        cible, arguments, dossier = Path(lu[0]), lu[1], Path(lu[2] or Path(lu[0]).parent)
    env = {**os.environ, "__COMPAT_LAYER": "RunAsInvoker"}
    subprocess.Popen(f'"{cible}" {arguments}'.strip(), cwd=str(dossier), env=env,
                     creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))


def lire_raccourci(lien):
    """(cible, arguments, dossier) d'un raccourci, pour les essais."""
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('" + str(lien).replace("'", "''") + "');"
                        "$s.TargetPath; $s.Arguments; $s.WorkingDirectory"],
                       capture_output=True, text=True, timeout=30, encoding="oem", errors="replace",
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    # PowerShell redirigé écrit dans la page de code OEM (cp850) : « Vidéos » resterait illisible en ANSI
    return tuple(r.stdout.strip().splitlines())
