"""
Broutille — accès depuis le téléphone, sur le Wi-Fi de la maison.

Petit serveur web lancé par l'application : direct vidéo, repas du jour, dernière visite,
fiches des tortues ; depuis le jardin on note une pesée, un soin, on ajoute une photo à l'album.

Protégé par un code à 6 chiffres (cookie après la première saisie ; le QR code de
l'application le contient). Écoute sur le réseau local seulement : la box ne l'ouvre pas sur
Internet. Sans dépendance : http.server de Python, page HTML intégrée.
"""
import hashlib
import hmac
import json
import secrets
import socket
import tempfile
import threading
import time
from datetime import date, datetime
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import fiches
import rapports
from broutille_cam import ALBUM, INCONNUE, JournalOccupe, lire_journal, nom_fichier, secondes

PORT = 8642                      # 8765 est souvent pris (autres petits serveurs maison)
MAX_PHOTO = 25 * 1024 * 1024
ESSAIS_MAX, BLOCAGE_S = 8, 600       # code faux 8 fois : adresse bloquée 10 min


def nouveau_code():
    return f"{secrets.randbelow(10 ** 6):06d}"


def adresse_locale():
    """Adresse IP de ce PC sur le réseau local (celle qu'un téléphone du même Wi-Fi peut joindre)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))        # aucun paquet envoyé : choisit juste l'interface
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def _police(taille, gras=False):
    for nom in (["seguisb.ttf", "segoeuib.ttf"] if gras else ["segoeui.ttf"]):
        try:
            return ImageFont.truetype(nom, taille)
        except OSError:
            pass
    return ImageFont.load_default()


def duree_lisible(s):
    s = int(s)
    return f"{s} s" if s < 60 else f"{s // 60} min" if s < 3600 else f"{s // 3600} h {s % 3600 // 60:02d}"


def jour_fr(iso):
    return f"{iso[8:10]}/{iso[5:7]}" if iso else ""


class Serveur:
    """source() -> (image BGR, etat) ou None ; dossier() -> dossier des visites ;
    apres_modif() : prévient l'application qu'une fiche a changé (appelé depuis un fil du serveur)."""

    def __init__(self, registre, dossier, source, code, apres_modif=lambda: None, port=PORT, hote="0.0.0.0", secret=None):
        self.registre, self.dossier, self.source = registre, dossier, source
        self.code, self.apres_modif = code, apres_modif
        # le cookie n'est pas le code : un jeton de 256 bits tiré du code et d'un secret propre à ce PC.
        # Impossible à deviner, il change avec le code. secret : gardé dans la config pour que les
        # téléphones restent connectés d'un lancement à l'autre.
        self.jeton = hmac.new((secret or secrets.token_hex(32)).encode(), code.encode(), hashlib.sha256).hexdigest()
        self.echecs = {}                # ip -> (nombre, instant du dernier)
        self.f_nom, self.f_petit = _police(36, True), _police(18)   # lisible sur un petit écran
        serveur = self

        class Gestion(_Gestion):
            app = serveur

        self.httpd = ThreadingHTTPServer((hote, port), Gestion)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self.fil = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def demarrer(self):
        self.fil.start()
        return self

    def arreter(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def url(self, avec_code=True):
        base = f"http://{adresse_locale()}:{self.port}/"
        return base + (f"?code={self.code}" if avec_code else "")

    # --- images
    def image_direct(self, largeur=960):
        """JPEG de l'image en cours, avec le nom des tortues reconnues ; None sans surveillance."""
        donnees = self.source()
        if not donnees:
            return None
        image, etat = donnees
        h, w = image.shape[:2]
        e = min(1.0, largeur / w)
        petite = cv2.resize(image, (int(w * e), int(h * e)), interpolation=cv2.INTER_AREA) if e < 1 else image
        img = Image.fromarray(cv2.cvtColor(petite, cv2.COLOR_BGR2RGB))
        d = ImageDraw.Draw(img, "RGBA")
        fiches_ = self.registre.fiches
        for _num, boite, texte, sure, *reste in etat.get("pistes") or []:
            if not sure:
                continue
            cle = reste[0] if reste else None
            nom = fiches_[cle]["nom"] if cle in fiches_ and not texte.endswith("?") else "Tortue"
            x, y, bw, bh = (int(v * e) for v in boite)
            d.rounded_rectangle([x, y, x + bw, y + bh], radius=10, outline=(217, 164, 65, 255), width=3)
            tw = d.textlength(nom, font=self.f_nom)
            yt = max(0, y - 54)
            d.rounded_rectangle([x, yt, x + tw + 24, yt + 50], radius=12, fill=(16, 20, 15, 215))
            d.text((x + 12, yt + 4), nom, font=self.f_nom, fill=(233, 238, 227))
        ok, jpeg = cv2.imencode(".jpg", cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 75])
        return jpeg.tobytes() if ok else None

    def image_attente(self):
        img = Image.new("RGB", (960, 540), (16, 20, 15))
        d = ImageDraw.Draw(img)
        d.text((480, 270), "Surveillance arrêtée", font=self.f_nom, fill=(151, 163, 141), anchor="mm")
        ok, jpeg = cv2.imencode(".jpg", cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR))
        return jpeg.tobytes()

    # --- données
    def _journal(self):
        try:
            return lire_journal(self.dossier())
        except (JournalOccupe, OSError):
            return []

    def etat(self):
        journal = self._journal()
        aujourd_hui = date.today().isoformat()
        temps, derniere_vue, visites = {}, {}, {}
        for l in journal:
            cle = l.get("id_individu")
            if l["date"] == aujourd_hui and l["individu"] != INCONNUE:
                temps[l["individu"]] = temps.get(l["individu"], 0) + secondes(l)
            if cle:
                derniere_vue[cle] = max(derniere_vue.get(cle, ""), l["date"])
                visites[cle] = visites.get(cle, 0) + 1
        donnees = self.source()
        derniere = None
        if journal:
            l = journal[-1]
            derniere = {"nom": f"{l['proposition']} ?" if l.get("proposition") else l["individu"],
                        "quand": f"{jour_fr(l['date'])} à {l['heure'][:5]}", "duree": duree_lisible(secondes(l)),
                        "photo": Path(l["photo"]).name if l.get("photo") else ""}
        tortues = []
        for cle, f in sorted(self.registre.copie_fiches().items(), key=lambda x: (x[1].get("provisoire", False), x[1]["nom"])):
            b = rapports.bilan_poids(f.get("pesees", []))
            tortues.append({"cle": cle, "nom": f["nom"], "identite": fiches.resume_identite(f),
                            "vue": jour_fr(derniere_vue.get(cle, "")), "visites": visites.get(cle, 0),
                            "poids": rapports.poids_lisible(b["dernier"]["g"]) if b else "",
                            "alerte_poids": bool(b and b["alerte"])})
        return {"surveillance": donnees is not None,
                "presence": donnees[1].get("presence", 0) if donnees else 0,
                "aujourdhui": [{"nom": n, "duree": duree_lisible(s)} for n, s in sorted(temps.items(), key=lambda x: -x[1])],
                "derniere": derniere, "tortues": tortues, "heure": datetime.now().strftime("%H:%M")}

    def tortue(self, cle):
        f = self.registre.copie_fiches().get(cle)
        if not f:
            return None
        pesees = self.registre.pesees(cle)
        return {"cle": cle, "nom": f["nom"], "identite": fiches.resume_identite(f), "signes": f.get("signes", ""),
                "notes": f.get("notes", ""),
                "pesees": [{"date": jour_fr(p["date"]) + "/" + p["date"][:4], "poids": rapports.poids_lisible(p["g"]),
                            "note": p.get("note", "")} for p in reversed(pesees[-12:])],
                "carnet": [{"date": jour_fr(n["date"]) + "/" + n["date"][:4], "type": n.get("type", ""), "texte": n["texte"]}
                           for n in reversed(self.registre.carnet(cle)[-20:])],
                "album": [p.name for p in self.registre.album(cle)[:24]],
                "types": list(fiches.TYPES_CARNET)}

    # --- sécurité
    def bloque(self, ip):
        n, t = self.echecs.get(ip, (0, 0))
        if n >= ESSAIS_MAX and time.time() - t < BLOCAGE_S:
            return True
        if n >= ESSAIS_MAX:
            self.echecs.pop(ip, None)
        return False

    def verifier(self, ip, code):
        if self.bloque(ip):
            return False
        if code and hmac.compare_digest(str(code), self.code):
            self.echecs.pop(ip, None)
            return True
        if code:
            n, _t = self.echecs.get(ip, (0, 0))
            self.echecs[ip] = (n + 1, time.time())
        return False


class _Gestion(BaseHTTPRequestHandler):
    app = None
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):      # pas de bavardage dans la console
        pass

    # --- outils
    def _envoyer(self, statut, corps, type_="text/html; charset=utf-8", entetes=()):
        corps = corps.encode("utf-8") if isinstance(corps, str) else corps
        self.send_response(statut)
        self.send_header("Content-Type", type_)
        self.send_header("Content-Length", str(len(corps)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in entetes:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(corps)

    def _json(self, donnees, statut=200):
        self._envoyer(statut, json.dumps(donnees, ensure_ascii=False), "application/json; charset=utf-8")

    def _cookie(self):
        c = cookies.SimpleCookie(self.headers.get("Cookie", ""))
        return c["broutille"].value if "broutille" in c else ""

    def _autorise(self):
        return hmac.compare_digest(self._cookie().encode(), self.app.jeton.encode())

    def _lire_corps(self, maxi):
        n = int(self.headers.get("Content-Length") or 0)
        if n > maxi:
            raise ValueError("trop gros")
        return self.rfile.read(n)

    def _fichier_image(self, chemin):
        try:
            with Image.open(chemin) as img:
                img.draft("RGB", (900, 900))
                img = img.convert("RGB")
                img.thumbnail((900, 900))
                tampon = tempfile.SpooledTemporaryFile()
                img.save(tampon, "JPEG", quality=82)
                tampon.seek(0)
                self._envoyer(200, tampon.read(), "image/jpeg")
        except (OSError, ValueError):
            self._envoyer(404, "introuvable", "text/plain")

    # --- GET
    def do_GET(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        ip = self.client_address[0]
        if "code" in q:                     # lien du QR code : on pose le cookie et on nettoie l'adresse
            if self.app.verifier(ip, q["code"][0]):
                self._envoyer(303, "", entetes=[("Location", "/"), ("Set-Cookie",
                              f"broutille={self.app.jeton}; Max-Age=31536000; HttpOnly; SameSite=Strict; Path=/")])
            else:
                self._envoyer(403, PAGE_CODE.replace("{erreur}", "Code faux." if not self.app.bloque(ip)
                                                     else "Trop d'essais : réessayez dans 10 minutes."))
            return
        if not self._autorise():
            self._envoyer(200 if url.path == "/" else 403, PAGE_CODE.replace("{erreur}", ""))
            return
        try:
            self._route_get(url.path, q)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def _route_get(self, chemin, q):
        a = self.app
        if chemin == "/":
            self._envoyer(200, PAGE)
        elif chemin == "/api/etat":
            self._json(a.etat())
        elif chemin == "/api/tortue":
            t = a.tortue(q.get("cle", [""])[0])
            self._json(t, 200) if t else self._json({"erreur": "inconnue"}, 404)
        elif chemin == "/image.jpg":
            self._envoyer(200, a.image_direct() or a.image_attente(), "image/jpeg")
        elif chemin == "/direct.mjpg":
            self._mjpeg()
        elif chemin.startswith("/img/visite/"):
            nom = Path(chemin).name
            if nom.endswith(".jpg"):
                self._fichier_image(Path(a.dossier()) / nom)
            else:
                self._envoyer(404, "", "text/plain")
        elif chemin.startswith("/img/portrait/"):
            cle = Path(chemin).name
            p = a.registre.photo_profil(cle) if cle in a.registre.fiches else None
            self._fichier_image(p) if p else self._envoyer(404, "", "text/plain")
        elif chemin.startswith("/img/album/"):
            morceaux = chemin.split("/")
            if len(morceaux) == 5 and morceaux[3] in a.registre.fiches:
                self._fichier_image(a.registre.dossier / morceaux[3] / ALBUM / Path(morceaux[4]).name)
            else:
                self._envoyer(404, "", "text/plain")
        else:
            self._envoyer(404, "introuvable", "text/plain")

    def _mjpeg(self):
        """Direct en MJPEG, ~5 images/s : lu tel quel par la balise <img> du navigateur du téléphone."""
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=image")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        fin = time.time() + 3600             # une heure max par connexion : la page se reconnecte seule
        while time.time() < fin:
            jpeg = self.app.image_direct() or self.app.image_attente()
            self.wfile.write(b"--image\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(jpeg)).encode()
                             + b"\r\n\r\n" + jpeg + b"\r\n")
            self.wfile.flush()
            time.sleep(0.2 if self.app.source() else 2.0)

    # --- POST
    def do_POST(self):
        url = urlparse(self.path)
        ip = self.client_address[0]
        if url.path == "/connexion":
            try:
                code = parse_qs(self._lire_corps(1000).decode("utf-8", "replace")).get("code", [""])[0].strip()
            except ValueError:
                code = ""
            if self.app.verifier(ip, code):
                self._envoyer(303, "", entetes=[("Location", "/"), ("Set-Cookie",
                              f"broutille={self.app.jeton}; Max-Age=31536000; HttpOnly; SameSite=Strict; Path=/")])
            else:
                msg = "Trop d'essais : réessayez dans 10 minutes." if self.app.bloque(ip) else "Code faux."
                self._envoyer(403, PAGE_CODE.replace("{erreur}", msg))
            return
        if not self._autorise():
            self._json({"erreur": "code"}, 403)
            return
        q = parse_qs(url.query)
        a = self.app
        try:
            if url.path == "/api/photo":
                cle = q.get("cle", [""])[0]
                if cle not in a.registre.fiches:
                    raise ValueError("tortue inconnue")
                corps = self._lire_corps(MAX_PHOTO)
                nom = nom_fichier(Path(q.get("nom", ["telephone"])[0]).stem)[:30] or "telephone"
                with tempfile.TemporaryDirectory() as d:
                    tmp = Path(d) / f"{nom}.jpg"
                    tmp.write_bytes(corps)
                    if not a.registre.ajouter_album(cle, [tmp]):
                        raise ValueError("photo illisible")
            else:
                donnees = json.loads(self._lire_corps(20000) or b"{}")
                cle = donnees.get("cle", "")
                if cle not in a.registre.fiches:
                    raise ValueError("tortue inconnue")
                jour = date.fromisoformat(donnees.get("date") or date.today().isoformat())
                if jour > date.today():
                    raise ValueError("date dans le futur")
                if url.path == "/api/pesee":
                    g = float(str(donnees.get("g", "")).replace(",", ".").replace(" ", ""))
                    a.registre.ajouter_pesee(cle, jour.isoformat(), g, str(donnees.get("note", ""))[:200])
                elif url.path == "/api/note":
                    a.registre.ajouter_note(cle, jour.isoformat(), str(donnees.get("type") or "Note")[:30],
                                            str(donnees.get("texte", ""))[:1000])
                else:
                    self._json({"erreur": "introuvable"}, 404)
                    return
        except (ValueError, TypeError, KeyError) as e:
            self._json({"erreur": str(e)}, 400)
            return
        a.apres_modif()
        self._json({"ok": True})


PAGE_CODE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Broutille</title>
<style>body{margin:0;background:#10140f;color:#e9eee3;font:17px system-ui,sans-serif;display:grid;place-items:center;min-height:100vh}
form{background:#1b2119;padding:28px;border-radius:16px;width:min(320px,86vw)}h1{margin:0 0 6px}p{color:#97a38d;margin:0 0 18px}
input{width:100%;box-sizing:border-box;font-size:28px;letter-spacing:8px;text-align:center;padding:12px;border-radius:10px;border:1px solid #2d3729;background:#10140f;color:#e9eee3}
button{margin-top:14px;width:100%;padding:14px;font-size:17px;font-weight:600;border:0;border-radius:10px;background:#7fb950;color:#10200a}
.e{color:#f85149;margin-top:12px;min-height:1em}</style></head><body>
<form method="post" action="/connexion"><h1>Broutille</h1><p>Code affiché dans l'application, bouton 📱 Téléphone.</p>
<input name="code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" autofocus>
<button>Entrer</button><div class="e">{erreur}</div></form></body></html>"""

PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#10140f"><title>Broutille</title>
<style>
:root{--fond:#10140f;--carte:#1b2119;--bord:#2d3729;--texte:#e9eee3;--discret:#97a38d;--vert:#7fb950;--rouge:#f85149;--ambre:#d9a441}
*{box-sizing:border-box}body{margin:0;background:var(--fond);color:var(--texte);font:16px system-ui,-apple-system,sans-serif;padding:0 14px 40px}
header{display:flex;align-items:center;justify-content:space-between;padding:14px 0 10px;position:sticky;top:0;background:var(--fond);z-index:2}
h1{font-size:22px;margin:0}.pastille{font-size:14px;font-weight:600;padding:6px 12px;border-radius:20px;background:var(--carte);color:var(--discret)}
.pastille.on{color:var(--vert)}.pastille.table{color:var(--rouge)}
.video{width:100%;border-radius:12px;background:#000;display:block;aspect-ratio:16/9;object-fit:contain}
section{background:var(--carte);border-radius:14px;padding:14px;margin-top:14px}h2{font-size:13px;letter-spacing:.06em;color:var(--discret);margin:0 0 10px;text-transform:uppercase}
.ligne{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--bord)}.ligne:last-child{border:0}
.discret{color:var(--discret)}.derniere{display:flex;gap:12px;align-items:center}.derniere img{width:120px;height:80px;object-fit:cover;border-radius:8px;background:#000}
.tortues{display:grid;grid-template-columns:1fr 1fr;gap:10px}.t{background:var(--fond);border-radius:12px;overflow:hidden;border:1px solid var(--bord);text-align:left;color:inherit;font:inherit;padding:0}
.t img{width:100%;aspect-ratio:4/3;object-fit:cover;display:block;background:#000}.t div{padding:8px 10px}.t b{display:block}.t small{color:var(--discret);font-size:13px}
.alerte{color:var(--rouge)!important}
dialog{border:0;border-radius:16px;background:var(--carte);color:var(--texte);width:min(560px,94vw);max-height:90vh;padding:16px}dialog::backdrop{background:#000a}
label{display:block;font-size:13px;color:var(--discret);margin:10px 0 4px}input,select,textarea{width:100%;font:inherit;padding:10px;border-radius:10px;border:1px solid var(--bord);background:var(--fond);color:var(--texte)}
.rang{display:flex;gap:8px}.rang>*{flex:1}button.b{margin-top:10px;width:100%;padding:12px;font:600 16px system-ui;border:0;border-radius:10px;background:var(--vert);color:#10200a}
button.sec{background:var(--bord);color:var(--texte)}.album{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}.album img{width:100%;aspect-ratio:1;object-fit:cover;border-radius:6px}
.msg{position:fixed;left:50%;bottom:20px;transform:translateX(-50%);background:var(--vert);color:#10200a;padding:10px 18px;border-radius:20px;font-weight:600;display:none;z-index:9}
.msg.err{background:var(--rouge);color:#fff}
</style></head><body>
<header><h1>🐢 Broutille</h1><span id="pastille" class="pastille">…</span></header>
<img class="video" id="video" src="/direct.mjpg" alt="Direct de la mangeoire">
<section><h2>Aujourd'hui à table</h2><div id="aujourdhui" class="discret">…</div></section>
<section><h2>Dernière visite</h2><div id="derniere" class="discret">…</div></section>
<section><h2>Mes tortues</h2><div id="tortues" class="tortues"></div></section>
<dialog id="fiche"></dialog><div id="msg" class="msg"></div>
<script>
const $=s=>document.querySelector(s), esc=t=>String(t??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const aujourdhui=()=>new Date(Date.now()-new Date().getTimezoneOffset()*6e4).toISOString().slice(0,10);
function message(t,err){const m=$("#msg");m.textContent=t;m.className="msg"+(err?" err":"");m.style.display="block";setTimeout(()=>m.style.display="none",2500)}
async function api(u,o){const r=await fetch(u,o);if(r.status===403){location.reload();throw 0}const j=await r.json();if(!r.ok)throw new Error(j.erreur||"erreur");return j}
async function etat(){try{const e=await api("/api/etat");
 const p=$("#pastille");p.textContent=!e.surveillance?"● En veille":e.presence?`● ${e.presence} à table`:"● Surveillance";p.className="pastille"+(e.presence?" table":e.surveillance?" on":"");
 $("#aujourdhui").innerHTML=e.aujourdhui.length?e.aujourdhui.map(x=>`<div class="ligne"><span>${esc(x.nom)}</span><span class="discret">${esc(x.duree)}</span></div>`).join(""):"Pas encore de repas";
 const d=e.derniere;$("#derniere").innerHTML=d?`<div class="derniere">${d.photo?`<img src="/img/visite/${encodeURIComponent(d.photo)}">`:""}<div><b>${esc(d.nom)}</b><br><span class="discret">${esc(d.quand)} · ${esc(d.duree)}</span></div></div>`:"Aucune visite";
 $("#tortues").innerHTML=e.tortues.map(t=>`<button class="t" onclick="fiche('${esc(t.cle)}')"><img loading="lazy" src="/img/portrait/${esc(t.cle)}" onerror="this.style.visibility='hidden'"><div><b>${esc(t.nom)}</b><small>${t.vue?"vue le "+esc(t.vue):"jamais vue"}${t.poids?" · <span class='"+(t.alerte_poids?"alerte":"")+"'>"+esc(t.poids)+"</span>":""}</small></div></button>`).join("");
}catch(e){}}
async function fiche(cle){const t=await api("/api/tortue?cle="+encodeURIComponent(cle));const f=$("#fiche");
 f.innerHTML=`<div style="display:flex;justify-content:space-between;align-items:start"><div><h1>${esc(t.nom)}</h1><div style="color:var(--ambre)">${esc(t.identite)}</div>${t.signes?`<div class="discret">${esc(t.signes)}</div>`:""}</div><button class="b sec" style="width:auto;margin:0;padding:8px 14px" onclick="fiche_fermer()">✕</button></div>
 <section><h2>⚖ Pesée</h2><div class="rang"><div><label>Poids (g)</label><input id="g" inputmode="decimal" placeholder="1250"></div><div><label>Date</label><input id="gd" type="date" value="${aujourdhui()}" max="${aujourdhui()}"></div></div>
 <label>Remarque</label><input id="gn"><button class="b" onclick="peser('${esc(cle)}')">Enregistrer la pesée</button>
 ${t.pesees.slice(0,4).map(p=>`<div class="ligne"><span>${esc(p.date)}</span><span>${esc(p.poids)}</span></div>`).join("")}</section>
 <section><h2>📒 Carnet</h2><div class="rang"><div><label>Type</label><select id="nt">${t.types.map(x=>`<option>${esc(x)}</option>`).join("")}</select></div><div><label>Date</label><input id="nd" type="date" value="${aujourdhui()}" max="${aujourdhui()}"></div></div>
 <label>Ce qui s'est passé</label><textarea id="nx" rows="2"></textarea><button class="b" onclick="noter('${esc(cle)}')">Noter</button>
 ${t.carnet.slice(0,5).map(n=>`<div class="ligne"><span>${esc(n.date)} · ${esc(n.type)}</span><span class="discret" style="text-align:right;max-width:60%">${esc(n.texte)}</span></div>`).join("")}</section>
 <section><h2>🖼 Album</h2><label class="b" style="text-align:center;margin:0 0 10px;background:var(--vert);color:#10200a;font-weight:600;padding:12px;border-radius:10px">📷 Ajouter une photo<input type="file" accept="image/*" multiple hidden onchange="envoyer('${esc(cle)}',this.files)"></label>
 <div class="album">${t.album.map(n=>`<img loading="lazy" src="/img/album/${esc(cle)}/${encodeURIComponent(n)}">`).join("")}</div></section>`;
 if(!f.open)f.showModal()}
function fiche_fermer(){$("#fiche").close()}
async function peser(cle){try{await api("/api/pesee",{method:"POST",body:JSON.stringify({cle,g:$("#g").value,date:$("#gd").value,note:$("#gn").value})});message("Pesée enregistrée");fiche(cle);etat()}catch(e){message(e.message||"Erreur",1)}}
async function noter(cle){try{await api("/api/note",{method:"POST",body:JSON.stringify({cle,type:$("#nt").value,date:$("#nd").value,texte:$("#nx").value})});message("Noté");fiche(cle)}catch(e){message(e.message||"Erreur",1)}}
async function envoyer(cle,fichiers){let n=0;for(const f of fichiers){try{await api(`/api/photo?cle=${encodeURIComponent(cle)}&nom=${encodeURIComponent(f.name)}`,{method:"POST",body:f});n++}catch(e){message(e.message||"Erreur",1)}}
 if(n){message(n+" photo"+(n>1?"s":"")+" ajoutée"+(n>1?"s":""));fiche(cle);etat()}}
$("#video").onerror=()=>setTimeout(()=>$("#video").src="/direct.mjpg?"+Date.now(),3000);
document.addEventListener("visibilitychange",()=>{if(!document.hidden){$("#video").src="/direct.mjpg?"+Date.now();etat()}});
etat();setInterval(etat,10000);
</script></body></html>"""
