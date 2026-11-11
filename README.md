# Broutille

**La mangeoire qui reconnaît ses tortues.** Des auges imprimées en 3D plantées au sol, une ou plusieurs caméras, et une application Windows. Broutille filme chaque visite, dit l'espèce, reconnaît chaque tortue, suit ses repas, son poids et son comportement, et vous prévient sur le téléphone si quelque chose ne va pas.

🌍 **13 langues** : français · English · Español · Deutsch · Português · Italiano · Nederlands · 中文 · 日本語 · 한국어 · ไทย · Tiếng Việt · Bahasa Indonesia. L'application, la page du téléphone, les alertes, les graphiques et la fiche PDF suivent la langue de Windows ; elle se change dans **⚙ Réglages**. *English summary: [README.en.md](README.en.md).*

📖 **[Guide d'utilisation complet](GUIDE.md)** · 📦 **[Versions publiées](https://github.com/Oli97430/broutille/releases)**

![Broutille](modele_3d/apercus/broutille_ensemble.png)

## Ce que fait l'application

### Surveiller

| | |
|---|---|
| 🎥 **Enregistrement automatique** | Un clip dès qu'une tortue arrive, 3 s d'avant comprises, limité à 2 min même si elle mange une heure. |
| 📷 **Caméras** | Webcam USB, **caméra IP Wi-Fi** (Mercusys, Tapo, toute caméra RTSP : cherchée sur le réseau, testée, sans application à laisser ouverte), fenêtre ouverte (EZVIZ Studio… même cachée), flux RTSP/HLS, page YouTube, fichier vidéo. |
| 🎛 **Plusieurs caméras** | Mangeoire, abri, bassin : une surveillance par caméra, en même temps. Une pastille par caméra (vert : surveillée, rouge : tortue à table, ambre : image figée). Chaque visite note sa caméra. |
| 🐢 **Tortues seulement** | Pierres, mains, ombres sont écartées ; *Pas une tortue* efface le reste et ne revient plus. |
| 🔎 **Espèce** | Radiée ou sillonnée par défaut ; 9 espèces au choix. |
| 🏷️ **Individu** | Chaque tortue est reconnue par le dessin de sa carapace. En cas de doute : « Zoé ? », confirmé d'un clic, et Broutille retient ces images. |
| 👆 **Nommer sur la vidéo** | Un clic sur une tortue du direct : la nommer, ou ouvrir sa fiche si elle est reconnue. |
| 👥 **Plusieurs à table** | Une ligne de journal par tortue. |
| 🧊 **Image figée** | Alerte et bandeau rouge après 1 min sans image ; relance automatique du direct (EZVIZ) en option. |
| 🔁 **Démarrage avec Windows** | Broutille ouvre EZVIZ Studio si besoin, attend chaque caméra (Wi-Fi encore éteint, lecteur qui s'ouvre) puis surveille. |

### Suivre chaque tortue

| | |
|---|---|
| 🐢 **Fiche complète** | Identité (sexe, naissance — l'âge se calcule seul —, arrivée, origine, signes distinctifs, notes), pesées et courbe de poids, album photo, vues apprises par la reconnaissance, carnet de soins (vermifuge, vétérinaire, hibernation, ponte…). |
| ✅ **À confirmer** | Les visites douteuses une à une, au clavier : Entrée = la proposition, 1 à 9 = une tortue, Espace = passer. |
| 📊 **Statistiques** | Repas sur 30 jours par tortue, temps à table, absences ; une tortue qui ne vient plus passe en rouge. |
| ⚖ **Poids** | Courbe par tortue, perte de 10 % signalée, rappel de pesée après 30 jours. |
| 🧭 **Comportement** | Rythme (heure d'arrivée, régularité), réseau social (qui mange avec qui), dominance (qui chasse qui), déplacements (zones, contacts, poursuites), santé (cette semaine contre les précédentes). |
| 📄 **Vétérinaire** | Fiche PDF de deux pages : photos, identité, repas, poids, dernières visites. |

### Partager et être prévenu

| | |
|---|---|
| 📱 **Téléphone** | Une page sur le Wi-Fi de la maison, ouverte en scannant un QR code et protégée par un code : direct, repas du jour, fiches, pesée ou soin noté depuis le jardin, photo ajoutée à l'album. |
| 🔔 **Alertes** | Même loin de la maison, avec l'appli gratuite ntfy : tortue absente, perte de poids, image figée, surveillance arrêtée. Une alerte par épisode. |
| 🎬 **Clips verticaux** | Après la visite d'une tortue reconnue : 1080 × 1920, 25 s, le cadre suit la tortue, nom et âge incrustés. Prêts pour Shorts, Reels et TikTok, téléchargeables depuis le téléphone. |
| 📺 **Plein écran** | Pour diffuser en direct sur YouTube (avec OBS) : noms et âges des tortues reconnues, « EN DIRECT », heure, repas du jour, rien de privé à l'écran. Touche P : photo 1920 × 1080. |
| 💾 **Sauvegarde** | Une archive par jour sur clé USB ou OneDrive : journal, fiches, pesées, carnets, galeries, positions. |

## Configuration

**La carte graphique n'est pas nécessaire.**

| | Minimum | Conseillé |
|---|---|---|
| Système | Windows 10 ou 11, 64 bits | Windows 11 |
| Processeur | 4 cœurs | 8 cœurs |
| Mémoire | 8 Go | 16 Go |
| Carte graphique | aucune | NVIDIA, 4 Go de mémoire vidéo |
| Disque | 30 Go libres | 50 Go libres |

Temps d'une analyse complète sur un Intel i9-11900 : environ **0,5 s** avec une RTX 3090, **3,3 à 5 s** sur processeur seul. Une tortue étant lente, c'est suffisant. Deux caméras font environ deux fois plus de calcul : sur processeur seul, l'analyse de chacune est un peu plus espacée. Pic de mémoire mesuré : 4,5 Go, plus 3,1 Go de mémoire vidéo avec le GPU.

Facultatif : [ffmpeg](https://ffmpeg.org) installé donne des clips verticaux en H.264, le format que toutes les plateformes acceptent.

## Démarrer

**En un clic** : téléchargez [`Broutille-Setup.exe`](https://github.com/Oli97430/broutille/releases/latest/download/Broutille-Setup.exe) et double-cliquez dessus.

- Aucun droit administrateur n'est demandé. L'installateur installe Python 3.11 s'il manque, puis les bibliothèques (environ 3 Go, 5 à 30 minutes selon la connexion) ; une fenêtre noire montre l'avancement.
- Il ajoute **Broutille** au menu Démarrer (et au Bureau si vous cochez la case), avec **Préparer Broutille** pour réparer les bibliothèques en cas de problème.
- Windows peut afficher « Windows a protégé votre ordinateur », car l'installateur n'est pas signé : cliquez *Informations complémentaires*, puis *Exécuter quand même*.
- Mettre à jour : lancez le nouvel installateur par-dessus ; les bibliothèques déjà téléchargées sont gardées.
- Désinstaller : Paramètres de Windows → Applications → Broutille. Vos visites, fiches et réglages (`Vidéos\Broutille`, `%USERPROFILE%\.broutille.json`) sont gardés.

Les modèles de vision (environ 3 Go) se téléchargent au premier lancement.

*Installation à la main, pour les développeurs* : Python 3.11, puis `logiciel\installer.bat` (ou `logiciel\preparer.ps1`), puis `logiciel\Broutille.bat`.

Ensuite :

1. **🐢 Ajouter une tortue** pour chaque tortue : nom, espèce, puis 3 à 5 photos (face, deux profils, dessus).
2. Choisir la caméra :
   - caméra Wi-Fi : **📷 Caméra IP** → *Chercher sur le Wi-Fi* → identifiant du **compte de la caméra** → *Tester* → *Utiliser* ;
   - EZVIZ Studio ou autre lecteur : **🪟 Fenêtre**, puis **⛶ Cadrer** ;
   - une autre caméra en plus : **＋ Caméra** dans la ligne *Caméras*.
3. **▶ Démarrer** (ou **▶▶ Démarrer toutes**).

**Caméra Mercusys ou Tapo** : créez d'abord le *compte de la caméra* dans l'appli du fabricant (Paramètres de l'appareil → Paramètres avancés → Compte de la caméra). Ce n'est pas votre compte Mercusys : avec l'adresse e-mail, la caméra refuse l'accès, et *Tester* le dit.

## Nommer et corriger

Clic droit sur une visite :

- **✔ Oui, c'est Zoé** : confirme la proposition.
- **Un autre nom** ou **Nouvelle tortue…** : corrige ou crée la fiche.
- **Pas une tortue** : ne sera plus noté.
- **🐢 Fiche de…**, **🎬 Clip vertical**.

Double-clic dans *Mes tortues* : la fiche complète. Clic droit : poids, photos, carnet, ou « C'est la même tortue que » pour fusionner deux fiches.

**Plus vous confirmez, mieux Broutille reconnaît** : chaque confirmation ajoute un angle à la galerie, et une tortue reconnue y ajoute ses autres vues de la visite.

## La mangeoire

![Auge](modele_3d/apercus/broutille_auge.png)

Source paramétrique : [`modele_3d/broutille.scad`](modele_3d/broutille.scad) (OpenSCAD 2021.01). STL dans [`modele_3d/stl/`](modele_3d/stl).

| Fichier | Qté | Taille | Orientation | Remplissage |
|---|---|---|---|---|
| `broutille_auge.stl` | 3 conseillées | 200 × 248 × 50 mm | à plat, ouverture vers le haut | 25 % |
| `broutille_piquet.stl` | 2 par auge | 240 × 30 × 16 mm | couché, tel quel | 100 % |
| `broutille_abreuvoir.stl` | 1 | 246 × 244 × 18 mm | à plat ; ASA réglé pour l'étanchéité, voir [le guide](GUIDE.md#abreuvoir) | 25 % |
| `broutille_abri_petit.stl` | 1 | 224 × 200 × 110 mm | à l'envers, tel quel ; moyen et grand en 4 quarts, voir [le guide](GUIDE.md#abri-cachette) | 15 % |
| `broutille_abri_patte.stl` | 4 par abri | 46 × 36 × 8 mm | à plat ; glissée dans une encoche de l'abri, un piquet par patte | 100 % |
| `broutille_pierre.stl` | 1 | 246 × 198 × 13,5 mm | à plat, relief vers le haut ; pierre à griffes, voir [le guide](GUIDE.md#pierre-à-griffes) | 20 % |
| `broutille_rampe.stl` | 2 (une par côté) | 174 × 122 × 72 mm | à plat, tel quel ; bordure de 60 mm, autre hauteur : voir [le guide](GUIDE.md#rampe) | 15 % |
| `broutille_pesee_juvenile.stl` | 1 | 129 × 106 × 41 mm | ouverture vers le haut ; berceau de pesée, voir [le guide](GUIDE.md#berceau-de-pesée) | 6 parois |
| `broutille_pesee_adulte.stl` | 1 | 218 × 181 × 66 mm | ouverture vers le haut ; carapace jusqu'à 20 cm | 6 parois |
| `broutille_serre_panneau.stl` | 6 (2 × n + 2) | 232 × 20 × 150 mm | debout, tel quel ; serre à juvéniles, voir [le guide](GUIDE.md#serre-à-juvéniles) | 15 % |
| `broutille_serre_poteau_angle.stl` | 4 | 64 × 64 × 162 mm | debout, tel quel | 15 % |
| `broutille_serre_poteau_droit.stl` | 2 (2 × (n − 1)) | 38 × 67 × 162 mm | debout, tel quel | 15 % |
| `broutille_serre_couvercle.stl` | 2 (n) | 249 × 249 × 12 mm | à plat, rails vers le haut ; plaque de polycarbonate 240 × 238 × 4 mm | 15 % |
| `broutille_serre_tourniquet.stl` | 6 (2 × n + 2) | 60 × 16 × 4 mm | à plat ; vis 4 × 30 | 100 % |
| `broutille_pondoir_coin.stl` | 4 | 249 × 249 × 160 mm | debout, tel quel ; pondoir, voir [le guide](GUIDE.md#pondoir) | 15 % |
| `broutille_pondoir_cle.stl` | 4 | 159 × 14 × 20 mm | couchée, tel quel | 100 % |
| `broutille_pondoir_couvercle.stl` | 4 | 249 × 249 × 20 mm | à l'envers, tel quel | 15 % |
| `broutille_pondoir_cle_couvercle.stl` | 8 | 18 × 10 × 3 mm | à plat | 100 % |
| `broutille_pondoir_rampe.stl` | 1 | 184 × 64 × 110 mm | couchée sur le côté, tel quel ; 60 mm hors sol | 15 % |
| `broutille_suspendue_ratelier.stl` | 1 | 250 × 97 × 110 mm | fond sur le plateau ; mangeoire suspendue, voir [le guide](GUIDE.md#mangeoire-suspendue) | 15 % |
| `broutille_suspendue_pied.stl` | 2, sans piquets | 70 × 130 × 76 mm | socle sur le plateau | 15 % |
| `broutille_suspendue_rehausse.stl` | 2 par cran de 40 mm | 27 × 41 × 56 mm | debout, tel quel | 15 % |

**Réglages** : ASA ou PETG (pas de PLA dehors), couches de 0,2 mm, 4 périmètres, sans supports. Plateau de 256 × 256 mm minimum : l'auge fait 248 mm avec ses pattes. Couleur conseillée : gris moyen mat, pour que la tortue ressorte.

**Pose** :

1. Aligner les auges bout à bout, sur un sol plat.
2. Planter 2 piquets par auge, en diagonale, à travers les pattes, au maillet en caoutchouc.
3. Sol trop dur : remplacer le piquet par une sardine ou un fer à béton Ø 20 mm au plus (trou de 22 mm).

Pas de quincaillerie. Le fond est percé : la pluie s'évacue. Verdure, foin et fruits se posent dans l'auge. Le plastique imprimé garde les saletés dans ses couches : brosser à l'eau régulièrement.

## La vidéo

La caméra reste libre, sans support imprimé, à l'extérieur de la mangeoire. Quelle que soit la source (webcam, caméra Wi-Fi, fenêtre), ces règles donnent les meilleures reconnaissances :

- **Position** : assez haut pour voir le dos, à 30–45° sous l'horizontale. Le dessin des écailles est le meilleur signe d'identité.
- **Taille** : une tortue doit faire au moins 250 pixels à l'écran. Une webcam 1080p à 2 m convient pour des adultes.
- **Fenêtre** : elle ne doit pas être réduite, mais peut être cachée par d'autres. Broutille trouve seul la vidéo dans la fenêtre ; **⛶ Cadrer** retire en plus d'autres caméras d'une mosaïque.
- **Abri** : une webcam de PC n'est pas étanche.

## Précision mesurée

Sur des photos réelles d'iNaturalist, **pas sur vos tortues** : ces chiffres donnent un ordre de grandeur.

| Mesure | Résultat | Conditions |
|---|---|---|
| Détection d'une tortue | 99,6 % (505/507) | photos variées, GPU |
| Espèce radiata | 93,9 % | une seule image, 362 photos, radiata contre sulcata |
| Espèce sulcata | 98,6 % | une seule image, 143 photos, radiata contre sulcata |
| Bonne tortue en tête | 66 à 86 % | une image, 3 à 10 tortues de même espèce, 1 ou 2 références |
| Inconnue dépassant le seuil, galeries pleines | radiata 4 à 5,5 %, sulcata 1 à 1,5 % | par image, seuil 0,70 ; borne haute, voir plus bas |

Le dernier test compare une tortue inconnue à 2 à 10 fiches de 30 à 60 photos. Chaque fausse fiche réunit des animaux différents, ce qui est pire que la réalité : le chiffre est une borne haute. La marge y est appliquée, mais pas la règle de visite : Broutille exige en plus 2 images sûres à 8 s d'écart ou plus, et que 75 % des images sûres désignent la même tortue. Deux images d'une tortue immobile ne sont toutefois pas deux preuves vraiment indépendantes. Le taux réel par visite n'a pas été mesuré.

## Limites connues

- **Reconnaissance** : mesurée sur des photos (voir ci-dessus), pas encore sur une longue période de vraies visites. Pour un suivi de santé, contrôlez les visites importantes sur le clip.
- **Fenêtre** : capture par Windows Graphics Capture, qui voit EZVIZ Studio même caché. EZVIZ Studio arrête le direct au bout d'un moment : la relance automatique (Réglages) clique sur son bouton.
- **Mots de passe** : masqués partout à l'écran, dans les messages et les alertes, mais enregistrés en clair dans `%USERPROFILE%\.broutille.json` (mot de passe de la caméra IP, code du téléphone, sujet ntfy).
- **Vue libre** : une tortue vue sous un angle absent de sa galerie reste « Inconnue » tant qu'elle n'est pas confirmée. Le début d'utilisation demande donc quelques clics.
- **Sulcata** : carapace moins dessinée que la radiata ; les bonnes conditions de lumière comptent davantage.
- **Croissance** : le dessin d'un juvénile change. Confirmer des visites régulièrement entretient sa galerie.
- **Espèces proches** : Hermann et grecque se confondent souvent (environ 1 fois sur 3 seulement juste). Elles ne sont pas cochées par défaut.
- **Plusieurs caméras** : une tortue vue en même temps par deux caméras compte deux visites. Placez-les sur des endroits différents (mangeoire, abri).
- **Traductions** : faites par machine et vérifiées sur la forme (aucun texte manquant), pas relues par des locuteurs natifs.
- **Mangeoire** : la tenue des piquets est à vérifier selon votre terrain.

## Fichiers produits

Dans `Vidéos\Broutille` (modifiable dans *Réglages*) :

| Fichier | Contenu |
|---|---|
| `AAAA-MM-JJ_HH-MM-SS_<caméra>.mp4` | clip de la visite |
| `…_<n>_photo.jpg`, `…_<n>_tortue.jpg` | image de la visite, tortue isolée |
| `visites.csv` | date, heure, durée, tortue, espèce, proposition, correction, caméra |
| `individus\` | fiches (identité, pesées, carnet), galeries, albums ; le ménage n'y touche pas |
| `positions\AAAA-MM.csv` | trajet de chaque tortue pendant ses visites (comportement, déplacements) |
| `partage\` | photos du plein écran et clips verticaux (`partage\clips`) |

Par défaut, les clips de plus de 60 jours sont effacés et le dossier est limité à 20 Go. Réglages : `%USERPROFILE%\.broutille.json`. Vidéos et photos restent sur le PC ; seules les alertes passent par ntfy.sh, si vous les activez.

## Ligne de commande

```bash
python logiciel/broutille_cam.py --source 0 --dossier visites
python logiciel/broutille_cam.py --source "fenetre:EZVIZ Studio" --dossier visites
python logiciel/broutille_cam.py --source rtsp://192.168.1.20:554/stream1 --dossier visites
python logiciel/broutille_cam.py --source enregistrement.mp4 --dossier sortie
```

## Développement

```
broutille/
├── logiciel/
│   ├── broutille_app.py        interface Tkinter (caméras, fiches, statistiques, comportement, réglages)
│   ├── broutille_cam.py        moteur : présence, suivi, journal, registre des tortues
│   ├── vision.py               détection, espèce, descripteur d'individu
│   ├── sources.py              webcam, fenêtre ouverte, flux, fichier ; masquage des mots de passe
│   ├── cameras.py              caméras IP : recherche sur le réseau, accès RTSP (Digest)
│   ├── web.py                  page du téléphone (code, jeton, direct MJPEG, envois)
│   ├── alertes.py              alertes ntfy
│   ├── clips.py                clips verticaux 9:16
│   ├── fiches.py, rapports.py  identité, âge, repas, poids, fiche PDF
│   ├── comportement.py         rythme, réseau social, dominance, santé
│   ├── deplacements.py         trajets, zones, contacts, poursuites
│   ├── sauvegarde.py, demarrage.py
│   ├── i18n.py, langues/       13 langues ; langues/<code>.json = {texte français : traduction}
│   ├── modeles/                vecteurs de référence des espèces
│   └── tests/                  bancs d'essai et tests de bout en bout
└── modele_3d/                  sources OpenSCAD, STL, aperçus, generer.sh
```

```bash
cd logiciel
python tests/test_direct.py         # mode direct : Excel, reconnexion, objet fixe… (1 min)
python tests/test_moteur.py         # bout en bout sur vidéo simulée, environ 3 min sur GPU
python tests/test_multicam.py       # deux caméras en même temps
python tests/test_cameras.py        # caméras IP
python tests/test_web.py            # page du téléphone et sa sécurité
python tests/test_partage.py        # alertes, clips verticaux
python tests/test_revue.py          # non-régression des revues de code
python tests/test_fiches.py tests/test_rapports.py tests/test_comportement.py tests/test_deplacements.py tests/test_suivi.py
python tests/cles_i18n.py           # tous les textes traduits dans les 12 langues
```

Ajouter une langue : copier `langues/en.json` en `langues/<code>.json`, traduire les valeurs, ajouter le code dans `i18n.LANGUES`, puis `python tests/cles_i18n.py`.

## Modèles et licences

| Élément | Source | Licence |
|---|---|---|
| Détection | [Grounding DINO tiny](https://huggingface.co/IDEA-Research/grounding-dino-tiny) | Apache 2.0 |
| Espèce | [BioCLIP](https://huggingface.co/imageomics/bioclip) | MIT |
| Individu | [MegaDescriptor-L-384](https://huggingface.co/BVRA/MegaDescriptor-L-384) | **CC BY-NC 4.0 : usage non commercial** |
| Lecture des pages vidéo | [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Unlicense |
| Capture des fenêtres | [windows-capture](https://github.com/NiiightmareXD/windows-capture) | MIT |
| QR codes | [segno](https://github.com/heuer/segno) | BSD |
| Photos de référence et de test | [iNaturalist](https://www.inaturalist.org), Creative Commons | selon chaque photo ; seuls des vecteurs sont livrés |

À cause de MegaDescriptor, l'ensemble ne peut pas être utilisé commercialement tel quel.

