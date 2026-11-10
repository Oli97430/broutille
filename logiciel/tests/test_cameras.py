"""Caméras IP (Mercusys, Tapo) : adresse RTSP, libellé sans mot de passe, recherche sur le réseau.
Lancer : python tests/test_cameras.py"""
import socket
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import broutille_app as A
import cameras

ok = 0


def verifier(nom, condition, detail=""):
    global ok
    print(("OK   " if condition else "ÉCHEC") + f" {nom} {detail}")
    if not condition:
        raise SystemExit(1)
    ok += 1


u = cameras.adresse("192.168.1.184", "broutille", "p@ss:w/rd", "stream1")
verifier("adresse RTSP, caractères spéciaux encodés", u == "rtsp://broutille:p%40ss%3Aw%2Frd@192.168.1.184:554/stream1", u)
verifier("relue telle quelle", cameras.lire_adresse(u) == ("192.168.1.184", "broutille", "p@ss:w/rd", "stream1", 554))
for mauvais in (("pas-une-ip", "a", "b"), ("192.168.1.184", "", "b"), ("192.168.1.184", "a", "")):
    try:
        cameras.adresse(*mauvais)
        verifier(f"refusé : {mauvais}", False)
    except ValueError:
        pass
verifier("adresses incomplètes refusées", True)
libelle = A.libelle_source(u)
verifier("libellé sans mot de passe", libelle == "Caméra IP : 192.168.1.184 (stream1)" and "p%40" not in libelle, libelle)
verifier("le libellé renvoie à la caméra enregistrée", A.source_depuis_saisie(libelle, u) == u)
verifier("une autre saisie reste une autre source", A.source_depuis_saisie("Webcam 1", u) == "1")

# recherche : un faux serveur RTSP (port quelconque) sur 127.0.0.1
serveur = socket.socket()
serveur.bind(("127.0.0.1", 0))
serveur.listen(8)
threading.Thread(target=lambda: [serveur.accept() for _ in range(8)], daemon=True).start()
cameras.PORT_RTSP = serveur.getsockname()[1]
trouvees = cameras.chercher(reseau="127.0.0.0/30")
verifier("caméra trouvée sur le réseau", ("127.0.0.1", False) in trouvees, trouvees)
print(f"\n{ok} vérifications réussies")
