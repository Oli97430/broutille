"""Accès téléphone (web.py) : code, cookie, direct, fiches, pesée, carnet, photo. Lancer : python tests/test_web.py"""
import http.client
import io
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
from PIL import Image

import broutille_cam as m
import web

ok = 0


def verifier(nom, condition, detail=""):
    global ok
    print(("OK   " if condition else "ÉCHEC") + f" {nom} {detail}")
    if not condition:
        raise SystemExit(1)
    ok += 1


d = Path(tempfile.mkdtemp(prefix="broutille_web_"))
r = m.Registre(d, descripteur=object())
zoe = r.creer("Zoé", "Tortue d'Hermann")
r.modifier(zoe, naissance="2019", sexe="Femelle")
image = np.full((720, 1280, 3), 90, np.uint8)
etat = {"presence": 1, "pistes": [(1, (400, 300, 200, 150), "Zoé", True, zoe), (2, (10, 10, 50, 50), "X ?", False, None)]}
direct = {"actif": True}
modifs = []
s = web.Serveur(r, lambda: d, lambda: (image, etat) if direct["actif"] else None, "123456",
                apres_modif=lambda: modifs.append(1), port=0, hote="127.0.0.1").demarrer()
COOKIE = {"Cookie": f"broutille={s.jeton}"}


def req(methode, chemin, corps=None, entetes=None):
    c = http.client.HTTPConnection("127.0.0.1", s.port, timeout=10)
    c.request(methode, chemin, body=corps, headers=entetes or {})
    rep = c.getresponse()
    donnees = rep.read() if "mjpg" not in chemin else rep.read1(200000)
    c.close()
    return rep.status, rep.getheader("Set-Cookie") or "", rep.getheader("Content-Type") or "", donnees


st, _, _, corps = req("GET", "/")
verifier("sans code : page de code", st == 200 and b'name="code"' in corps and b"direct.mjpg" not in corps)
st, _, _, _ = req("GET", "/api/etat")
verifier("sans code : données refusées", st == 403)
st, cookie, _, _ = req("GET", "/?code=123456")
verifier("lien du QR : jeton posé, pas le code", st == 303 and f"broutille={s.jeton}" in cookie and "123456" not in cookie
         and "HttpOnly" in cookie)
st, cookie, _, _ = req("POST", "/connexion", "code=123456", {"Content-Type": "application/x-www-form-urlencoded"})
verifier("code saisi : jeton posé", st == 303 and f"broutille={s.jeton}" in cookie)
st, *_ = req("GET", "/api/etat", entetes={"Cookie": "broutille=123456"})
verifier("le code seul en cookie ne suffit pas", st == 403)
st, _, _, corps = req("GET", "/", entetes=COOKIE)
verifier("avec cookie : page complète", st == 200 and b"direct.mjpg" in corps)

st, _, _, corps = req("GET", "/api/etat", entetes=COOKIE)
e = json.loads(corps)
verifier("état", st == 200 and e["surveillance"] and e["presence"] == 1 and e["tortues"][0]["nom"] == "Zoé"
         and "environ 7 ans" in e["tortues"][0]["identite"] or "an" in e["tortues"][0]["identite"])
st, _, typ, corps = req("GET", "/image.jpg", entetes=COOKIE)
verifier("image du direct", st == 200 and typ == "image/jpeg" and Image.open(io.BytesIO(corps)).size == (960, 540))
st, _, typ, corps = req("GET", "/direct.mjpg", entetes=COOKIE)
verifier("flux MJPEG", st == 200 and "multipart/x-mixed-replace" in typ and corps.startswith(b"--image"))
direct["actif"] = False
st, _, _, corps = req("GET", "/image.jpg", entetes=COOKIE)
verifier("sans surveillance : image d'attente", st == 200 and corps[:2] == b"\xff\xd8")

json_ = {**COOKIE, "Content-Type": "application/json"}
st, _, _, _ = req("POST", "/api/pesee", json.dumps({"cle": zoe, "g": "1 250,5", "date": "2026-11-01"}), json_)
verifier("pesée depuis le téléphone", st == 200 and r.pesees(zoe)[0]["g"] == 1250.5 and modifs)
st, _, _, corps = req("POST", "/api/pesee", json.dumps({"cle": zoe, "g": "0"}), json_)
verifier("pesée absurde refusée", st == 400)
st, _, _, _ = req("POST", "/api/pesee", json.dumps({"cle": zoe, "g": "900", "date": "2999-01-01"}), json_)
verifier("date future refusée", st == 400)
st, _, _, _ = req("POST", "/api/note", json.dumps({"cle": zoe, "type": "Soin", "texte": "Bain tiède"}), json_)
verifier("note au carnet", st == 200 and r.carnet(zoe)[0]["texte"] == "Bain tiède")
st, _, _, _ = req("POST", "/api/note", json.dumps({"cle": "inconnue", "texte": "x"}), json_)
verifier("tortue inconnue refusée", st == 400)

tampon = io.BytesIO()
Image.new("RGB", (1600, 1200), (120, 90, 40)).save(tampon, "JPEG")
st, _, _, _ = req("POST", f"/api/photo?cle={zoe}&nom=IMG_0042.jpg", tampon.getvalue(), {**COOKIE, "Content-Type": "image/jpeg"})
verifier("photo dans l'album", st == 200 and len(r.album(zoe)) == 1 and "IMG_0042" in r.album(zoe)[0].name)
st, _, _, _ = req("POST", f"/api/photo?cle={zoe}", b"pas une image", {**COOKIE, "Content-Type": "image/jpeg"})
verifier("fichier illisible refusé", st == 400 and len(r.album(zoe)) == 1)
st, _, typ, _ = req("GET", f"/img/album/{zoe}/{r.album(zoe)[0].name}", entetes=COOKIE)
verifier("photo d'album servie", st == 200 and typ == "image/jpeg")
st, _, typ, _ = req("GET", f"/img/portrait/{zoe}", entetes=COOKIE)
verifier("portrait servi", st == 200 and typ == "image/jpeg")

(d / "secret.txt").write_text("privé")
st1, *_ = req("GET", "/img/visite/..%2F..%2Fsecret.txt", entetes=COOKIE)
st2, *_ = req("GET", "/img/visite/../individus/registre.json", entetes=COOKIE)
st3, *_ = req("GET", f"/img/album/{zoe}/..%2F..%2Fregistre.json", entetes=COOKIE)
verifier("pas de sortie du dossier", st1 == st2 == 404 and st3 in (404,))

st, _, _, corps = req("GET", f"/api/tortue?cle={zoe}", entetes=COOKIE)
t = json.loads(corps)
verifier("fiche détaillée", t["pesees"][0]["poids"] and t["carnet"][0]["type"] == "Soin" and len(t["album"]) == 1)

for _ in range(web.ESSAIS_MAX):
    req("GET", "/?code=000000")
st, _, _, corps = req("GET", "/?code=123456")
verifier("trop d'essais faux : bloqué, même avec le bon code", st == 403 and "10 minutes" in corps.decode())
st, *_ = req("GET", "/api/etat", entetes=COOKIE)
verifier("un téléphone déjà connecté continue", st == 200)
st, _, _, corps = req("POST", f"/api/photo?cle={zoe}", b"", {**COOKIE, "Content-Length": "-1"})
verifier("taille négative refusée", st == 400)
web.PAUSE_ECHEC_S = 0
s2 = web.Serveur(r, lambda: d, lambda: None, "654321", port=0, hote="127.0.0.1")
for k in range(web.ESSAIS_MAX_TOTAL):
    s2.verifier(f"10.0.{k}.1", "000000")
verifier("trop d'essais en changeant d'adresse : bloqué partout", not s2.verifier("10.9.9.9", "654321"))
s2.httpd.server_close()

s.arreter()
print(f"\n{ok} vérifications réussies")
