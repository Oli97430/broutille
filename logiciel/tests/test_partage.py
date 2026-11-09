"""Alertes ntfy (alertes.py), clips verticaux (clips.py) et leur service au téléphone.
Lancer : python tests/test_partage.py"""
import http.client
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cv2
import numpy as np

import alertes
import broutille_cam as m
import clips
import web

ok = 0


def verifier(nom, condition, detail=""):
    global ok
    print(("OK   " if condition else "ÉCHEC") + f" {nom} {detail}")
    if not condition:
        raise SystemExit(1)
    ok += 1


# ---------------------------------------------------------------- alertes
AUJ = date(2026, 11, 9)
fiches = {"a": {"nom": "Zoé", "pesees": [{"date": "2026-10-01", "g": 1000}, {"date": "2026-11-05", "g": 880}]},
          "b": {"nom": "Bruno", "pesees": []},
          "c": {"nom": "Hermann n°2", "provisoire": True},
          "d": {"nom": "Dodo", "hibernation": True}}
journal = [{"date": "2026-11-01", "id_individu": "a"}, {"date": "2026-11-08", "id_individu": "b"},
           {"date": "2026-10-01", "id_individu": "c"}, {"date": "2026-10-01", "id_individu": "d"},
           {"date": "2026-11-09", "id_individu": "", "id_proposition": "x"}]
dues = alertes.a_envoyer(fiches, journal, AUJ, jours_absence=3)
cles = sorted(d[0] for d in dues)
verifier("alertes dues : absence et perte de poids de Zoé seulement", cles == ["absence:a:2026-11-01", "poids:a:2026-11-05"], cles)
verifier("message lisible", any("8 jours" in d[2] for d in dues) and any("−120 g" in d[2] for d in dues),
         [d[2] for d in dues])
verifier("pas d'alerte d'absence si 0 jour", all(not d[0].startswith("absence") for d in alertes.a_envoyer(fiches, journal, AUJ, 0)))

d = Path(tempfile.mkdtemp(prefix="broutille_partage_"))
envois = []
a = alertes.Alertes(d, "http://serveur", "sujet", envoi=lambda *x: envois.append(x))
a.signaler("figee:1", "Image figée", "…")
a.signaler("figee:1", "Image figée", "…")
a.signaler("figee:2", "Image figée", "…")
verifier("une fois par épisode", len(envois) == 2)
b = alertes.Alertes(d, "http://serveur", "sujet", envoi=lambda *x: envois.append(x))
b.signaler("figee:2", "Image figée", "…")
verifier("retenu après redémarrage", len(envois) == 2)
erreurs = []


def en_panne(*_):
    raise OSError("pas de réseau")


c = alertes.Alertes(d, "http://serveur", "sujet", sur_erreur=erreurs.append, envoi=en_panne)
c.signaler("arret:1", "Surveillance arrêtée", "…")
verifier("échec signalé, épisode non retenu (réessayé plus tard)", erreurs and "arret" not in json.loads((d / "alertes.json").read_text()))
s1, s2 = alertes.nouveau_sujet(), alertes.nouveau_sujet()
verifier("sujets longs et différents", s1 != s2 and len(s1) >= 30 and s1.startswith("broutille-"))

# envoi réel vers un faux serveur ntfy local : JSON en UTF-8
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
recu = []


class FauxNtfy(BaseHTTPRequestHandler):
    def do_POST(self):
        recu.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *_):
        pass


faux = ThreadingHTTPServer(("127.0.0.1", 0), FauxNtfy)
threading.Thread(target=faux.serve_forever, daemon=True).start()
alertes.envoyer(f"http://127.0.0.1:{faux.server_address[1]}", "sujet-test", "Zoé perd du poids", "Dernier poids : 880 g", 4)
faux.shutdown()
verifier("format ntfy (JSON, accents)", recu and recu[0]["topic"] == "sujet-test" and recu[0]["title"] == "Zoé perd du poids"
         and recu[0]["priority"] == 4)

# ---------------------------------------------------------------- clips
source = d / "visite.mp4"
L, H, FPS = 1280, 720, 10
e = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (L, H))
positions = []
herbe = np.random.default_rng(3).integers(0, 90, (H, L, 3), dtype=np.uint8)
for _ in range(FPS * 2):                        # écran d'attente gris du lecteur, à sauter
    e.write(np.full((H, L, 3), 60, np.uint8))
for i in range(FPS * 20):                       # un carré rouge traverse l'image de gauche à droite
    image = cv2.add(np.full((H, L, 3), (40, 120, 50), np.uint8), herbe)     # herbe texturée, comme un vrai jardin
    x = 100 + i * 5
    cv2.rectangle(image, (x, 300), (x + 120, 420), (0, 0, 255), -1)
    e.write(image)
    if i % 10 == 0 and i / FPS >= clips.AVANT:
        positions.append((i / FPS + 2 - clips.AVANT, x // 2, 150, 60, 60, L // 2, H // 2))   # mesurées sur une image 2x plus petite
e.release()
sortie = clips.faire_clip(source, d / "clips" / "vertical.mp4", "Zoé", "Tortue d'Hermann  ·  7 ans", positions, "09/11/2026")
lecture = cv2.VideoCapture(str(sortie))
dims = (lecture.get(cv2.CAP_PROP_FRAME_WIDTH), lecture.get(cv2.CAP_PROP_FRAME_HEIGHT))
n = lecture.get(cv2.CAP_PROP_FRAME_COUNT)


def rouge_au_centre(i):
    lecture.set(cv2.CAP_PROP_POS_FRAMES, i)
    ok_, img = lecture.read()
    milieu = img[800:1100, 300:780]
    return ok_ and (milieu[..., 2] > 180).mean() > 0.2 and (milieu[..., 1] < 80).mean() > 0.2


verifier("clip vertical 1080×1920, ≤ 25 s", dims == (1080, 1920) and 6 * FPS <= n <= 25 * FPS + 1, (dims, n))
verifier("le cadre suit la tortue", rouge_au_centre(int(n * 0.3)) and rouge_au_centre(int(n * 0.8)))
lecture.set(cv2.CAP_PROP_POS_FRAMES, 0)
_, premiere = lecture.read()
verifier("écran d'attente gris sauté", float(cv2.cvtColor(premiere[400:1500], cv2.COLOR_BGR2GRAY).std()) > 10)
lecture.release()
verifier("décalage : visite arrivée 55 s après le début du fichier",
         clips.decalage({"video": "2026-11-08_16-55-46.mp4", "date": "2026-11-08", "heure": "16:56:41"}) == 55
         and clips.decalage({"video": "autre.mp4", "date": "2026-11-08", "heure": "16:56:41"}) == clips.AVANT)
court = d / "court.mp4"
e = cv2.VideoWriter(str(court), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (L, H))
for _ in range(FPS * 3):
    e.write(np.zeros((H, L, 3), np.uint8))
e.release()
verifier("visite trop courte : pas de clip", clips.faire_clip(court, d / "clips" / "court_v.mp4", "Zoé") is None)
verifier("nom du clip", clips.nom_clip({"date": "2026-11-09", "heure": "14:32:10"}, "Zoé l'aînée") == "2026-11-09_14-32_Zo__l_a_n_e.mp4"
         or clips.nom_clip({"date": "2026-11-09", "heure": "14:32:10"}, "Zoé l'aînée").startswith("2026-11-09_14-32_Zo"))
for k in range(5):
    (d / "clips" / f"vieux{k}.mp4").write_bytes(b"x")
clips.menage(d / "clips", garder=3)
verifier("ménage : les plus récents gardés", len(list((d / "clips").glob("*.mp4"))) == 3)

# ---------------------------------------------------------------- clips servis au téléphone
partage = d / "partage" / "clips"
partage.mkdir(parents=True)
clip = partage / "2026-11-09_14-32_Zoe.mp4"
clip.write_bytes(bytes(range(256)) * 40)
r = m.Registre(d, descripteur=object())
s = web.Serveur(r, lambda: d, lambda: None, "123456", port=0, hote="127.0.0.1").demarrer()
COOKIE = {"Cookie": f"broutille={s.jeton}"}


def req(chemin, entetes=None):
    c = http.client.HTTPConnection("127.0.0.1", s.port, timeout=10)
    c.request("GET", chemin, headers={**COOKIE, **(entetes or {})})
    rep = c.getresponse()
    corps = rep.read()
    c.close()
    return rep.status, dict(rep.getheaders()), corps


st, _, corps = req("/api/etat")
verifier("liste des clips dans l'état", st == 200 and json.loads(corps)["clips"] == [clip.name])
st, ent, corps = req(f"/clips/{clip.name}", {"Range": "bytes=100-199"})
verifier("lecture par plages (iPhone)", st == 206 and corps == clip.read_bytes()[100:200]
         and ent.get("Content-Range") == f"bytes 100-199/{clip.stat().st_size}")
st, ent, corps = req(f"/clips/{clip.name}?telecharger=1")
verifier("téléchargement", st == 200 and "attachment" in ent.get("Content-Disposition", "") and len(corps) == clip.stat().st_size)
st, *_ = req(f"/clips/{clip.name}", {"Range": "bytes=999999-"})
verifier("plage impossible refusée", st == 416)
st1, *_ = req("/clips/..%2F..%2Fvisites.csv")
st2, *_ = req("/clips/inconnu.mp4")
verifier("seuls les clips de la liste sont servis", st1 == st2 == 404)
st, *_ = req(f"/clips/{clip.name}", {"Cookie": ""})
verifier("clips protégés par le code", st == 403)
s.arreter()
print(f"\n{ok} vérifications réussies")
