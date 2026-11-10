"""
Broutille — caméras IP du réseau local (Mercusys, Tapo, et toute caméra RTSP/ONVIF).

Une caméra Mercusys (MC510…) ou Tapo se lit directement en RTSP : pas d'application à laisser
ouverte, pas de fenêtre à filmer, pas de « direct » à relancer. Il suffit d'un « compte de la
caméra » créé dans l'appli du fabricant (différent du compte Mercusys) :
    Accueil → carte de la caméra → Paramètres de l'appareil → Paramètres avancés → Compte de la caméra
Adresse : rtsp://identifiant:motdepasse@IP:554/stream1 (haute qualité) ou /stream2 (légère).
"""
import ipaddress
import socket
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

PORT_RTSP, PORT_ONVIF = 554, 2020       # 2020 : port ONVIF des caméras TP-Link (Mercusys, Tapo)
MARQUES = {
    "Mercusys (MC510, MC200…)": ("stream1", "stream2"),
    "Tapo (C200, C310…)": ("stream1", "stream2"),
    "Autre caméra RTSP": ("", ""),
}


def adresse_locale():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))        # aucun paquet envoyé : choisit juste l'interface
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def _ouvert(ip, port, delai):
    try:
        with socket.create_connection((ip, port), timeout=delai):
            return True
    except OSError:
        return False


def chercher(delai=0.4, reseau=None, arret=None):
    """Caméras du réseau local : [(ip, onvif_tp_link)] des appareils qui répondent sur le port RTSP.
    onvif_tp_link : le port 2020 répond aussi, signe d'une Mercusys ou d'une Tapo. Une dizaine de secondes."""
    moi = adresse_locale()
    passerelles = set()
    if reseau:
        reseaux = [ipaddress.ip_network(reseau, strict=False)]
    else:
        # les réseaux des cartes physiques (un maillage Deco a un /22), puis les voisins courants :
        # une box et un répéteur (ou deux box) ont souvent 192.168.0 et 192.168.1
        reseaux, passerelles = reseaux_locaux()
        if not reseaux:
            reseaux = [ipaddress.ip_network(f"{moi}/24", strict=False)]
        for autre in ("192.168.0.0/24", "192.168.1.0/24"):
            if not any(ipaddress.ip_network(autre).subnet_of(r) for r in reseaux if r.version == 4):
                reseaux.append(ipaddress.ip_network(autre))
    hotes = list(dict.fromkeys(str(h) for r in reseaux for h in r.hosts()
                               if str(h) != moi and str(h) not in passerelles))   # la box n'est pas une caméra
    trouvees = []
    verrou = threading.Lock()

    def essayer(ip):
        if arret is not None and arret.is_set():
            return
        # une Mercusys n'accepte que quelques connexions vidéo à la fois : son port 554 peut se taire un
        # instant (appli ouverte sur le téléphone) ; le port ONVIF 2020, lui, répond toujours
        onvif = _ouvert(ip, PORT_ONVIF, delai)
        if onvif or _ouvert(ip, PORT_RTSP, delai):
            with verrou:
                trouvees.append((ip, onvif))

    with ThreadPoolExecutor(max_workers=64) as pool:
        list(pool.map(essayer, hotes))
    return sorted(trouvees, key=lambda t: (not t[1], tuple(int(x) for x in t[0].split("."))))


# débuts d'adresses matérielles (MAC) de TP-Link, maison mère de Mercusys et Tapo
OUI_TP_LINK = {"60-32-b1", "50-c7-bf", "98-da-c4", "1c-61-b4", "54-af-97", "5c-62-8b", "3c-52-a1", "b0-a7-b9",
               "28-87-ba", "30-de-4b", "40-ed-00", "6c-5a-b0", "9c-53-22", "a8-42-a1", "ac-15-a2", "c0-06-c3",
               "d8-07-b6", "e4-fa-c4", "f0-a7-31", "48-22-54", "78-8c-b5", "14-eb-b6", "00-31-92", "10-27-f5",
               "18-d6-c7", "20-23-51", "24-2f-d0", "34-60-f9", "3c-84-6a", "5c-a6-e6", "68-ff-7b", "70-4f-57",
               "80-89-17", "84-d8-1b", "90-9a-4a", "a0-f3-c1", "b0-95-75", "c4-6e-1f", "d4-6e-0e", "e8-48-b8",
               "ec-08-6b", "f4-f2-6d", "f8-1a-67"}


def appareils_tp_link(exclure=()):
    """Adresses IP des appareils TP-Link vus récemment sur le réseau (table ARP de Windows). Une
    caméra Mercusys dont le compte de la caméra n'est pas encore créé n'ouvre pas son flux, mais
    elle apparaît ici… comme une prise, un répéteur ou une box TP-Link : simple indice, jamais
    choisi d'office. Les passerelles sont exclues."""
    exclure = set(exclure) | reseaux_locaux()[1]
    import subprocess
    try:
        sortie = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=10, encoding="oem", errors="replace",
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    trouves = []
    for ligne in sortie.splitlines():
        morceaux = ligne.split()
        if len(morceaux) >= 2 and morceaux[1].count("-") == 5:
            ip, mac = morceaux[0], morceaux[1].lower()
            if mac[:8] in OUI_TP_LINK and ip not in exclure and not ip.endswith(".255"):
                trouves.append(ip)
    return trouves


def adresse(ip, identifiant, mot_de_passe, chemin="stream1", port=PORT_RTSP):
    """Adresse RTSP complète ; identifiant et mot de passe encodés (un « @ » ou un « : » ne casse rien).
    chemin peut garder sa requête (« cam/realmonitor?channel=1 ») pour les autres marques."""
    ip = ip.strip()
    ipaddress.IPv4Address(ip)                   # ValueError si ce n'est pas une adresse IPv4
    if not identifiant or not mot_de_passe:
        raise ValueError("identifiant et mot de passe du compte de la caméra nécessaires")
    cred = f"{urllib.parse.quote(identifiant, safe='')}:{urllib.parse.quote(mot_de_passe, safe='')}@"
    chemin = chemin.strip().lstrip("/")
    return f"rtsp://{cred}{ip}:{int(port)}/{chemin}"


def verifier_acces(ip, port, chemin, identifiant, mot_de_passe, delai=5.0):
    """Demande le flux à la caméra (RTSP DESCRIBE, identification Basic qu'elle propose) : "ok", "refuse"
    (identifiant ou mot de passe faux), "introuvable" (mauvais chemin), "muet" (pas de réponse)."""
    import base64
    cle = base64.b64encode(f"{identifiant}:{mot_de_passe}".encode("utf-8")).decode("ascii")
    chemin = chemin.lstrip("/")
    try:
        with socket.create_connection((ip, int(port)), timeout=delai) as s:
            s.settimeout(delai)
            demande = (f"DESCRIBE rtsp://{ip}:{int(port)}/{chemin} RTSP/1.0\r\nCSeq: 2\r\nAccept: application/sdp\r\n"
                       f"Authorization: Basic {cle}\r\n\r\n")
            s.sendall(demande.encode("utf-8"))
            reponse = s.recv(200).decode("ascii", "replace")
    except OSError:
        return "muet"
    code = reponse.split(" ", 2)[1] if reponse.startswith("RTSP/") and len(reponse.split(" ")) > 1 else ""
    return {"200": "ok", "401": "refuse", "403": "refuse", "404": "introuvable"}.get(code, "muet")


def lire_adresse(source):
    """(ip, identifiant, mot de passe, chemin avec sa requête, port) d'une adresse rtsp://, ou None."""
    try:
        u = urllib.parse.urlsplit(str(source))
        if u.scheme != "rtsp" or not u.hostname:
            return None
        chemin = u.path.lstrip("/") + (f"?{u.query}" if u.query else "")
        return (u.hostname, urllib.parse.unquote(u.username or ""), urllib.parse.unquote(u.password or ""),
                chemin, u.port or PORT_RTSP)
    except ValueError:
        return None


def reseaux_locaux():
    """(réseaux IPv4 des cartes réseau physiques, passerelles) d'après ipconfig : bornés à /22, sans
    adresse automatique (169.254) ni carte virtuelle ou VPN connue."""
    import re
    import subprocess
    try:
        sortie = subprocess.run(["ipconfig"], capture_output=True, text=True, timeout=10, encoding="oem", errors="replace",
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except (OSError, subprocess.SubprocessError):
        return [], set()
    reseaux, passerelles = [], set()
    for bloc in re.split(r"\r?\n(?=\S)", sortie):
        titre = bloc.splitlines()[0].lower() if bloc.strip() else ""
        if any(m in titre for m in ("vmware", "virtualbox", "hyper-v", "vethernet", "wsl", "vpn", "tap-", "tailscale",
                                    "zerotier", "loopback", "bluetooth")):
            continue
        ips = re.findall(r"IPv4[^:]*:\s*([\d.]+)", bloc)
        masques = re.findall(r"(?:Masque de sous-r.seau|Subnet Mask)[^:]*:\s*([\d.]+)", bloc)
        for ip, masque in zip(ips, masques):
            if ip.startswith("169.254.") or ip.startswith("127."):
                continue
            try:
                r = ipaddress.ip_network(f"{ip}/{masque}", strict=False)
            except ValueError:
                continue
            if r.prefixlen < 22:
                r = ipaddress.ip_network(f"{ip}/22", strict=False)
            if r.is_private:
                reseaux.append(r)
        passerelles.update(re.findall(r"(?:Passerelle par d.faut|Default Gateway)[^:]*:\s*([\d.]+)", bloc))
    return reseaux, passerelles
