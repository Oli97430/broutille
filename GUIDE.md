# Guide d'utilisation de Broutille

De la première impression à l'usage quotidien. Comptez environ **une demi-journée de mise en place** hors temps d'impression, puis quelques minutes par semaine.

## Sommaire

1. [Ce qu'il vous faut](#1-ce-quil-vous-faut)
2. [Imprimer et poser la mangeoire](#2-imprimer-et-poser-la-mangeoire)
3. [Installer l'application](#3-installer-lapplication)
4. [Choisir la source vidéo](#4-choisir-la-source-vidéo)
5. [Placer la caméra](#5-placer-la-caméra)
6. [Présenter vos tortues](#6-présenter-vos-tortues)
7. [La surveillance au quotidien](#7-la-surveillance-au-quotidien)
8. [Confirmer et corriger](#8-confirmer-et-corriger)
9. [Mes tortues](#9-mes-tortues)
10. [Statistiques et alertes](#10-statistiques-et-alertes)
11. [Réglages](#11-réglages)
12. [Entretien](#12-entretien)
13. [Problèmes fréquents](#13-problèmes-fréquents)
14. [Que vaut la reconnaissance ?](#14-que-vaut-la-reconnaissance-)

---

## 1. Ce qu'il vous faut

### L'ordinateur

| | Minimum | Conseillé |
|---|---|---|
| Système | Windows 10 ou 11, 64 bits | Windows 11 |
| Processeur | 4 cœurs | 8 cœurs |
| Mémoire | 8 Go | 16 Go |
| Carte graphique | **aucune** | NVIDIA avec 4 Go de mémoire vidéo |
| Disque | 30 Go libres | 50 Go libres |
| Autre | Python 3.11, port USB ou réseau | PC allumé en continu |

Répartition du disque : 5 Go pour l'application, 3 Go pour les modèles, 20 Go de vidéos au plus par défaut.

**La carte graphique n'est pas nécessaire.** Mesures sur un Intel i9-11900 :

| | Une analyse complète |
|---|---|
| Carte NVIDIA RTX 3090 | environ 0,5 s |
| Processeur, 8 fils | 3,3 s |
| Processeur, 4 fils | 3,9 s |
| Processeur, 2 fils | 5,0 s |

Une tortue étant lente, une analyse toutes les 5 s suffit. Sur un processeur plus ancien, comptez nettement plus ; ce cas n'a pas été mesuré, et Broutille espace alors simplement ses analyses. L'application utilise jusqu'à 4,5 Go de mémoire, et 3,1 Go de mémoire vidéo avec une carte graphique.

### La vidéo

Une seule source au choix : webcam USB, fenêtre ouverte (EZVIZ Studio ou autre), flux Internet.

### La mangeoire

- Une imprimante 3D à plateau de 256 × 256 mm au moins.
- Du filament ASA ou PETG, en gris moyen mat si possible. Pas de PLA dehors.
- Un maillet en caoutchouc.

---

## 2. Imprimer et poser la mangeoire

### Imprimer

Fichiers dans `modele_3d/stl/` :

| Pièce | Quantité | Remplissage | Sur le plateau |
|---|---|---|---|
| `broutille_auge.stl` | 3 conseillées | 25 % | ouverture vers le haut |
| `broutille_piquet.stl` | 2 par auge | 100 % | tel quel, couché |

Réglages : couches de 0,2 mm, 4 périmètres, sans supports. Avant de tout lancer, imprimez une auge et un piquet, et vérifiez que le piquet passe dans le trou de la patte.

### Poser

1. Choisissez un sol plat, à l'ombre si possible : la nourriture se conserve mieux et l'image est plus régulière.
2. Alignez les auges bout à bout.
3. Plantez 2 piquets par auge au maillet, à travers les pattes, sans forcer d'un coup : c'est du plastique.
4. Sol trop dur : remplacez le piquet par une sardine ou un fer à béton de 20 mm de diamètre au plus.

### Remplir

Posez verdure, foin et fruits directement dans l'auge. Le fond est percé, la pluie s'évacue.

---

## 3. Installer l'application

1. Installez [Python 3.11](https://www.python.org/downloads/) si besoin.
2. Double-cliquez sur `logiciel/installer.bat`. Comptez 10 à 30 minutes selon votre connexion.
3. Double-cliquez sur `logiciel/Broutille.bat`.

Le premier lancement télécharge les modèles (environ 3 Go). En haut à droite, « Modèles prêts (GPU) » ou « Modèles prêts (Processeur) » indique que tout est en place.

---

## 4. Choisir la source vidéo

Le champ **Caméra** est en haut à gauche.

### Webcam USB

Choisissez `Webcam 0`, ou `Webcam 1` si le PC a déjà une caméra intégrée.

### Fenêtre ouverte (EZVIZ Studio...)

1. Ouvrez votre logiciel et affichez la caméra de la mangeoire.
2. Cliquez sur **🪟 Fenêtre**, puis choisissez la fenêtre dans la liste.
3. Cliquez sur **⛶ Cadrer** et tracez à la souris la zone de l'image de la mangeoire.

**Le cadrage est important** : il retire boutons, horloges et autres caméras de la mosaïque, et la tortue y gagne en taille.

Règles :

- La fenêtre doit rester ouverte, pas réduite dans la barre des tâches.
- Elle peut en général être cachée par une autre. Si l'image reste noire, gardez-la visible à l'écran.
- La capture se fait à 10 images par seconde : suffisant pour des tortues.
- Une fenêtre affiche souvent une image réduite : mettez-la en grand, ou en plein écran si votre logiciel le permet.

### Flux Internet

Tapez l'adresse dans le champ **Caméra** :

| Type | Exemple |
|---|---|
| Caméra IP en RTSP | `rtsp://utilisateur:motdepasse@192.168.1.20:554/flux` |
| Flux HLS | `https://exemple.com/direct/index.m3u8` |
| Page vidéo en direct | `https://www.youtube.com/watch?v=...` |

**Astuce EZVIZ** : si votre modèle propose le RTSP, préférez-le à la capture de fenêtre, car l'image est meilleure et n'oblige pas à garder le logiciel ouvert. L'adresse exacte dépend du modèle : consultez sa notice.

Le mot de passe est masqué dans les messages, mais il reste enregistré en clair dans `%USERPROFILE%\.broutille.json`. Ne partagez pas ce fichier.

### Fichier vidéo

Cliquez sur **🎞 Vidéo** pour analyser un enregistrement existant.

---

## 5. Placer la caméra

La caméra est libre, à l'extérieur de la mangeoire, en vue large. Ces règles font toute la différence :

| Règle | Pourquoi |
|---|---|
| **Voir le dos de la tortue** : viser de haut, 30 à 45° sous l'horizontale | Le dessin des écailles est le meilleur signe d'identité |
| **Une tortue d'au moins 250 pixels** à l'écran | En dessous, les écailles ne se distinguent plus |
| **Ne plus bouger la caméra** | Les vues restent comparables d'un jour à l'autre |
| **Éviter le contre-jour et le plein soleil direct** | Ombres dures et reflets masquent le dessin |
| **Abriter une webcam de PC** | Elle n'est pas étanche, et la pluie sur l'objectif ruine l'image |

Une webcam 1080p à 2 m convient à des adultes. Pour des juvéniles, rapprochez-la. Câble USB : 5 m au plus, au-delà prenez une rallonge active.

---

## 6. Présenter vos tortues

C'est l'étape la plus importante. **Broutille ne connaît que les tortues que vous lui présentez.**

1. Cliquez sur **🐢 Ajouter une tortue**.
2. Donnez son nom et son espèce.
3. Répondez **Oui** pour ajouter des photos.
4. Choisissez 3 à 5 photos nettes : face, profil gauche, profil droit, dessus.

Des photos faites à la mangeoire avec la même caméra valent mieux que des photos au téléphone.

Vous pouvez aussi démarrer sans photo : les visites apparaissent « Inconnue », et un clic droit crée la fiche depuis la visite (voir [§ 8](#8-confirmer-et-corriger)).

**Espèces** : radiée et sillonnée sont cochées d'office. Si vous en avez d'autres, cochez-les dans *Réglages* ; ne cochez que celles que vous avez, c'est ce qui évite les confusions.

---

## 7. La surveillance au quotidien

Cliquez sur **▶ Démarrer**.

| À l'écran | Sens |
|---|---|
| Cadre orange | une tortue suivie |
| « Zoé » | reconnue avec certitude |
| « Zoé ? » | ressemble à Zoé, sans certitude |
| « Tortue radiée » | espèce seule : elle ne ressemble à aucune fiche |
| Badge rouge REC | clip en cours |
| « 2 tortues à table » | deux tortues confirmées dans le champ |

À son départ (20 s sans la voir), la visite s'ajoute à la colonne de droite.

Bon à savoir :

- **Il faut du temps pour nommer une tortue** : au moins 2 images sûres, à 8 s d'écart ou plus. Une visite de quelques secondes reste « Inconnue ».
- Un clip dure 2 minutes au plus ; la durée de présence, elle, est comptée en entier.
- Une tortue immobile reste suivie, même endormie.
- Si la source se coupe, Broutille se reconnecte seule.

Pour que tout redémarre après une coupure : cochez *Démarrer la surveillance à l'ouverture* dans *Réglages*, et mettez un raccourci vers `Broutille.bat` dans le dossier Démarrage de Windows.

---

## 8. Confirmer et corriger

Clic droit sur une visite :

| Choix | Effet |
|---|---|
| **✔ Oui, c'est Zoé** | confirme la proposition |
| **Un autre nom** | corrige la visite |
| **Nouvelle tortue…** | crée une fiche avec les images de cette visite |
| **Pas une tortue** | efface la visite, son clip et ses photos ; Broutille ignorera ce qui y ressemble |

**Chaque confirmation rend Broutille meilleure** : les images rejoignent la galerie de la tortue, et un nouvel angle devient reconnaissable. Les premiers jours demandent donc quelques clics, puis de moins en moins.

Un double-clic ouvre le clip de la visite.

> Si `visites.csv` est ouvert dans Excel, une correction est refusée avec un message : fermez Excel, puis recommencez. Les nouvelles visites, elles, attendent et ne sont pas perdues.

---

## 9. Mes tortues

Onglet **Mes tortues**, à droite. Clic droit sur une tortue :

| Choix | Effet |
|---|---|
| **Nommer / changer l'espèce…** | met à jour la fiche et toutes ses visites |
| **Ajouter des photos…** | enrichit la galerie |
| **C'est la même tortue que** | fusionne deux fiches |
| **Supprimer la fiche…** | efface la galerie ; ses visites restent, sous « Inconnue » |

Un double-clic ouvre le dossier de sa galerie. Retirez-y une photo qui ne montre pas la bonne tortue : elle sera oubliée.

Couleurs : **orange** pour une fiche provisoire, **rouge** pour une tortue absente depuis trop longtemps.

La case *Créer une fiche pour une tortue inconnue*, en bas de fenêtre, est décochée d'office. Cochée, chaque inconnue crée une fiche ; pratique au tout début, mais une même tortue vue sous un autre angle peut en créer plusieurs, à fusionner ensuite.

---

## 10. Statistiques et alertes

- **Repas d'aujourd'hui** : temps à table par tortue.
- **📊 Statistiques** : sur 30 jours, visites, temps à table, jours de venue, dernière visite.
- **Alerte d'absence** : une tortue passe en rouge après 3 jours sans visite (réglable).

Une tortue qui mange moins ou ne vient plus peut signaler un problème de santé, mais aussi une simple hibernation ou estivation. Broutille attire l'attention ; il ne remplace pas un vétérinaire.

Toutes les visites sont dans `visites.csv`, lisible par Excel. Fermez-le après consultation pour permettre les corrections.

---

## 11. Réglages

| Réglage | Effet | Par défaut |
|---|---|---|
| Dossier des visites | où tout est rangé | `Vidéos\Broutille` |
| Signaler une tortue absente | alerte rouge | 3 jours |
| Effacer les clips après | ménage automatique | 60 jours |
| Taille maximale du dossier | ménage automatique | 20 Go |
| Démarrer à l'ouverture | surveillance automatique | non |
| Espèces présentes | candidates pour l'espèce | radiée, sillonnée |
| Oublier les « Pas une tortue » | annule ces marquages | — |

Le curseur **Exigence pour nommer une tortue**, en bas de fenêtre :

- trop de fausses identités : montez-le ;
- trop d'« Inconnue » alors que votre galerie est fournie : baissez-le un peu.

Le ménage ne touche jamais au journal ni aux galeries des tortues.

---

## 12. Entretien

| Quand | Quoi |
|---|---|
| Chaque jour | retirer les restes de nourriture |
| Chaque semaine | brosser les auges à l'eau : le plastique imprimé retient les saletés dans ses couches |
| Chaque semaine | confirmer les visites en attente |
| Tous les mois | vérifier les piquets et nettoyer l'objectif |
| Tous les 6 mois | ajouter de nouvelles photos des juvéniles, dont le dessin change |

**Sauvegarde** : copiez le dossier `Vidéos\Broutille\individus` : il contient les fiches et les galeries, c'est-à-dire tout ce que Broutille a appris.

---

## 13. Problèmes fréquents

| Symptôme | Cause probable | Solution |
|---|---|---|
| « La source vidéo ne renvoie aucune image » | webcam prise par une autre application, ou accès refusé | fermer Teams ou Zoom ; Paramètres › Confidentialité › Caméra |
| Webcam introuvable | mauvais numéro | essayer `Webcam 1`, `Webcam 2` |
| Fenêtre : image noire | lecteur vidéo non capturable en arrière-plan | garder la fenêtre visible à l'écran |
| Fenêtre : « Source interrompue » | fenêtre réduite ou fermée | la rouvrir : Broutille reprend seul |
| Flux : aucune image | adresse fausse, mot de passe, RTSP désactivé | tester l'adresse dans VLC |
| Tortue pas détectée | trop petite, trop sombre | rapprocher la caméra, cadrer, améliorer la lumière |
| Toujours « Inconnue » | galerie trop maigre, pas assez de temps de visite | ajouter des photos, confirmer des visites |
| Mauvais nom | galerie polluée, tortues très semblables | corriger, retirer les mauvaises photos, monter l'exigence |
| Une pierre est suivie | fausse détection | clic droit › *Pas une tortue* |
| Message « visites.csv est ouvert ailleurs » | Excel ouvert | fermer Excel : les visites en attente s'écrivent seules |
| Lenteur, ventilateur bruyant | pas de carte graphique | normal ; réduire la résolution de la source |
| L'application ne s'ouvre pas | voir le fichier d'erreurs | `%USERPROFILE%\.broutille_erreurs.log` |

---

## 14. Que vaut la reconnaissance ?

**Honnêtement : très bien pour l'espèce, correctement pour l'individu, et rien n'a encore été mesuré sur vos propres tortues.** Les chiffres viennent de photos réelles d'iNaturalist. Voir le tableau complet dans le [README](README.md#précision-mesurée).

Ce qui l'améliore le plus, dans l'ordre :

1. une caméra fixe, qui voit le dos ;
2. une tortue grande à l'écran, avec un bon cadrage ;
3. de la lumière douce et régulière ;
4. une galerie enrichie par vos confirmations.

La radiée, avec son dessin en étoiles, se reconnaît par nature mieux que la sillonnée adulte, dont la carapace est plus uniforme.
