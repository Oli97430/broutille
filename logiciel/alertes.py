"""
Broutille — alertes sur le téléphone, même hors de la maison, par ntfy (appli gratuite,
Android et iPhone, sans compte).

Le téléphone s'abonne à un « sujet » : un nom long et tiré au hasard, connu seulement de
l'application et du téléphone (le QR code le contient). Broutille y publie :
  - une tortue n'est pas venue depuis N jours ;
  - une tortue a perdu 10 % de son poids ou plus ;
  - l'image du direct est figée ;
  - la surveillance s'est arrêtée sur une erreur.

Chaque alerte part une seule fois par épisode (alertes.json dans le dossier des visites) :
pas de rafale à chaque vérification ni après un redémarrage.
"""
import json
import secrets
import threading
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import rapports
from i18n import t, tn

SERVEUR = "https://ntfy.sh"
FICHIER = "alertes.json"


def nouveau_sujet():
    """Nom de sujet impossible à deviner : c'est lui qui protège les alertes."""
    return "broutille-" + secrets.token_urlsafe(18).replace("_", "x").replace("-", "y")


def adresse_abonnement(serveur, sujet):
    return f"{serveur.rstrip('/')}/{sujet}"


def envoyer(serveur, sujet, titre, message, priorite=3, etiquettes=("turtle",), delai=10):
    """Publie une notification ; lève OSError si le serveur ne répond pas."""
    corps = json.dumps({"topic": sujet, "title": titre, "message": message, "priority": int(priorite),
                        "tags": list(etiquettes)}).encode("utf-8")
    req = urllib.request.Request(serveur.rstrip("/") + "/", data=corps, method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "Broutille"})
    with urllib.request.urlopen(req, timeout=delai) as rep:
        if rep.status >= 300:
            raise OSError(t("ntfy : réponse {code}", code=rep.status))


def a_envoyer(fiches, journal, aujourd_hui=None, jours_absence=3):
    """Alertes dues d'après les fiches et le journal : [(clé d'épisode, titre, message, priorité, étiquettes)].
    La clé d'épisode change quand la situation change (nouvelle visite, nouvelle pesée)."""
    aujourd_hui = aujourd_hui or date.today()
    derniere = {}
    for l in journal:
        for cle in (l.get("id_individu"), l.get("id_proposition")):   # visite à confirmer : elle a sans doute mangé
            if cle:
                derniere[cle] = max(derniere.get(cle, ""), l["date"])
    limite = (aujourd_hui - timedelta(days=jours_absence)).isoformat()
    sortie = []
    for cle, f in fiches.items():
        if f.get("provisoire") or f.get("hibernation"):
            continue
        vue = derniere.get(cle)
        if jours_absence and vue and vue < limite:
            jours = (aujourd_hui - date.fromisoformat(vue)).days
            sortie.append((f"absence:{cle}:{vue}", t("{nom} ne vient plus manger", nom=f["nom"]),
                           tn("Pas vue à la mangeoire depuis {n} jour (dernière visite le {date}).",
                              "Pas vue à la mangeoire depuis {n} jours (dernière visite le {date}).", jours,
                              date=t("{jour}/{mois}", jour=vue[8:10], mois=vue[5:7])), 4, ("turtle", "warning")))
        b = rapports.bilan_poids(f.get("pesees", []), aujourd_hui)
        if b and b["alerte"]:
            pire = min((e for e in (b["precedente"], b["mois"]) if e), key=lambda e: e["pct"])
            depuis = t("{jour}/{mois}", jour=pire["date"][8:10], mois=pire["date"][5:7])
            sortie.append((f"poids:{cle}:{b['dernier']['date']}", t("{nom} perd du poids", nom=f["nom"]),
                           t("Dernier poids : {poids}, {ecart} depuis le {date}. À surveiller.",
                             poids=rapports.poids_lisible(b["dernier"]["g"]), ecart=rapports.ecart_lisible(pire),
                             date=depuis), 4, ("turtle", "scales")))
    return sortie


class Alertes:
    """Envoi en arrière-plan, une fois par épisode. sur_erreur(texte) : appelé si l'envoi échoue."""

    def __init__(self, dossier, serveur, sujet, sur_erreur=lambda t: None, envoi=envoyer):
        self.dossier, self.serveur, self.sujet = Path(dossier), serveur, sujet
        self.sur_erreur, self.envoi = sur_erreur, envoi
        self._verrou = threading.Lock()

    @property
    def chemin(self):
        return self.dossier / FICHIER

    def _deja(self):
        try:
            return json.loads(self.chemin.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _retenir(self, deja):
        tmp = self.chemin.with_suffix(".tmp")
        tmp.write_text(json.dumps(deja, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.chemin)

    def signaler(self, episode, titre, message, priorite=3, etiquettes=("turtle",)):
        """Envoie si cet épisode n'a pas encore été signalé ; renvoie True si envoyé."""
        with self._verrou:
            deja = self._deja()
            sujet_alerte = episode.rsplit(":", 1)[0]       # « absence:t123 » : un seul épisode retenu par sujet
            if deja.get(sujet_alerte) == episode:
                return False
            try:
                self.envoi(self.serveur, self.sujet, titre, message, priorite, etiquettes)
            except OSError as e:
                self.sur_erreur(t("Alerte non envoyée : {erreur}", erreur=e))
                return False
            deja[sujet_alerte] = episode
            self._retenir(deja)
            return True

    def verifier(self, fiches, journal, jours_absence):
        return [ep for ep, *reste in a_envoyer(fiches, journal, jours_absence=jours_absence)
                if self.signaler(ep, *reste)]

    def en_fond(self, fonction, *args):
        threading.Thread(target=fonction, args=args, daemon=True).start()
