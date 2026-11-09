"""Non-régression de la revue de code (novembre 2026) : un essai par défaut corrigé.
Lancer : python tests/test_revue.py"""
import http.client
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PIL import Image

import broutille_cam as m
import clips
import sources
import web

ok = 0


def verifier(nom, condition, detail=""):
    global ok
    print(("OK   " if condition else "ÉCHEC") + f" {nom} {detail}")
    if not condition:
        raise SystemExit(1)
    ok += 1


d = Path(tempfile.mkdtemp(prefix="broutille_revue_"))
r = m.Registre(d, descripteur=object())
zoe = r.creer("Zoé", "Tortue d'Hermann")

# --- téléphone
s = web.Serveur(r, lambda: d, lambda: None, "123456", port=0, hote="127.0.0.1").demarrer()
c = http.client.HTTPConnection("127.0.0.1", s.port, timeout=10)
c.request("GET", "/api/etat", headers={"Cookie": f"broutille={s.jeton}"})
rep = c.getresponse()
rep.read()
verifier("connexion gardée ouverte : accès au départ", rep.status == 200)
s.arreter()
try:
    c.request("GET", "/api/etat", headers={"Cookie": f"broutille={s.jeton}"})
    statut = c.getresponse().status
except OSError:
    statut = "coupée"
verifier("accès coupé : la connexion déjà ouverte n'a plus rien", statut in ("coupée", 403), statut)

s = web.Serveur(r, lambda: d, lambda: None, "123456", port=0, hote="127.0.0.1").demarrer()
COOKIE = {"Cookie": f"broutille={s.jeton}"}


def req(methode, chemin, corps=None, entetes=None, hote=None):
    c = http.client.HTTPConnection("127.0.0.1", s.port, timeout=10)
    c.putrequest(methode, chemin, skip_host=True)
    c.putheader("Host", hote or f"127.0.0.1:{s.port}")
    for k, v in {**COOKIE, **(entetes or {})}.items():
        c.putheader(k, v)
    if corps is not None:
        c.putheader("Content-Length", str(len(corps)))
    c.endheaders(corps)
    rep = c.getresponse()
    donnees = rep.read()
    c.close()
    return rep.status, dict(rep.getheaders()), donnees


st, *_ = req("GET", "/api/etat", hote="broutille.attaquant.example:8642")
verifier("nom de domaine refusé (DNS rebinding)", st == 421)
st, *_ = req("POST", "/api/note", b"[1]", {"Content-Type": "application/json"})
verifier("JSON qui n'est pas un objet : 400, pas de connexion coupée", st == 400)
nom = clips.nom_clip({"date": "2026-11-09", "heure": "10:00:00"}, "Céleste")
verifier("nom de clip en ASCII", nom == "2026-11-09_10-00_Celeste.mp4", nom)
(d / "partage" / "clips").mkdir(parents=True)
(d / "partage" / "clips" / "2026-11-09_10-00_Łucja.mp4").write_bytes(b"0123456789")
st, ent, corps = req("GET", "/clips/2026-11-09_10-00_%C5%81ucja.mp4?telecharger=1")
verifier("ancien clip accentué : servi et téléchargeable", st == 200 and corps == b"0123456789"
         and "UTF-8''" in ent.get("Content-Disposition", ""), (st, ent.get("Content-Disposition")))
st, *_ = req("GET", "/img/visite/E:broutille.jpg")
verifier("photo de visite : pas de lecteur Windows dans le nom", st == 404)
bombe = Image.new("1", (15000, 13000))         # 195 Mpx, quelques Ko en PNG
tampon = d / "bombe.png"
bombe.save(tampon)
st, *_ = req("POST", f"/api/photo?cle={zoe}", tampon.read_bytes(), {"Content-Type": "image/png"})
verifier("image géante refusée proprement", st == 400 and not r.album(zoe), st)
s.arreter()
verifier("nouveaux codes à 8 chiffres", len(web.nouveau_code()) == 8)

# --- registre et journal
r.ajouter_note(zoe, "2026-10-01", "Soin", "A")
r.ajouter_note(zoe, "2026-10-05", "Soin", "B")
affichee = r.carnet(zoe)[1]                      # « B », affichée au rang 1
r.ajouter_note(zoe, "2026-09-01", "Soin", "ajoutée depuis le téléphone")   # décale les rangs
r.retirer_note(zoe, 1, affichee)
verifier("carnet : la note affichée est celle retirée", [n["texte"] for n in r.carnet(zoe)] == ["ajoutée depuis le téléphone", "A"])

journal = d / "visites.csv"
m.ecrire_journal(journal, [])
with open(journal, "a", encoding="utf-8") as f:
    f.write("v1;2026-11-09;10:00:00;30;Zoé;Tortue d'Hermann;0.9;a.mp4;;image\n")            # champs de fin absents (Excel)
    f.write("v2;2026-11-09;11:00:00;30;Zoé;Tortue d'Hermann;0.9;b.mp4;;image;;;;;en trop\n")  # un champ de trop
lignes = m.lire_journal(d)
verifier("lignes au nombre de champs inattendu gardées", [l["id_visite"] for l in lignes] == ["v1", "v2"]
         and lignes[0]["id_individu"] == "" and None not in lignes[1])

(r.dossier / "registre.json").write_text("{abîmé", encoding="utf-8")
bak_avant = (r.dossier / "registre.bak").read_text(encoding="utf-8")
r.modifier(zoe, signes="encoche")
verifier("registre abîmé : la copie .bak saine n'est pas écrasée",
         (r.dossier / "registre.bak").read_text(encoding="utf-8") == bak_avant
         and json.loads((r.dossier / "registre.json").read_text(encoding="utf-8"))[zoe]["signes"] == "encoche")

# --- sources
masque = sources.masquer("rtsp://admin:secret@192.168.1.5/live?user=admin&pwd=hunter2")
verifier("mots de passe masqués, y compris dans la requête", "secret" not in masque and "hunter2" not in masque, masque)
print(f"\n{ok} vérifications réussies")
