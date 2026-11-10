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

### Abreuvoir

![Abreuvoir en forme de tortue](modele_3d/apercus/broutille_abreuvoir.png)

`broutille_abreuvoir.stl`, en un seul morceau : une tortue de 246 × 244 × 18 mm, dont la carapace est la cuvette et les nervures dessinent les écailles d'une radiata. Il se fixe avec 2 `broutille_piquet.stl`, dans les pattes percées.

**Sécurité** : une tortue peut se noyer dans un récipient profond. La cuvette contient 14 mm d'eau au plus (environ 140 ml), avec des pentes de 27 à 32° et des nervures de prise. Pour un juvénile, mettez 8 mm d'eau (environ 70 ml).

**Réglages ASA**, à ajuster selon votre filament :

| Réglage | Valeur |
|---|---|
| Buse | 250 à 260 °C |
| Plateau | 100 à 110 °C, avec colle ou PEI texturé |
| Enceinte | fermée, sans ventilateur ou presque (0 à 20 %) |
| Bordure (brim) | 8 mm, indispensable : l'ASA se décolle sur une grande pièce |
| Couches | 0,2 mm |
| Parois | 6 |
| Couches pleines dessus et dessous | 8 |
| Remplissage | 25 % |
| Supports | aucun |
| Débit | +2 à 3 % : des couches bien soudées retiennent l'eau |

**Avant de le donner aux tortues** :

1. Remplissez-le et posez-le sur du papier pendant 24 h, pour vérifier qu'il ne fuit pas.
2. Lavez-le à l'eau chaude et laissez-le aérer quelques jours : l'ASA sent et dégage du styrène à l'impression. Imprimez dans une pièce ventilée.
3. S'il fuit, ou pour un nettoyage plus facile, enduisez la cuvette d'une résine époxy certifiée contact alimentaire. L'ASA imprimé n'a pas de certification de ce type.

**Entretien** : changez l'eau chaque jour et brossez la cuvette, car un biofilm s'installe vite dans les couches d'impression. Pour le vider, retirez les 2 piquets. Placez-le à l'ombre : en plein soleil, 140 ml d'eau chauffent et s'évaporent vite.

### Abri-cachette

![Abri-cachette en forme de carapace](modele_3d/apercus/broutille_abri.png)

Une carapace creuse, dessus gravé des écailles en étoile de la radiata, où la tortue se met à l'ombre et à l'abri. Source : [`modele_3d/abri.scad`](modele_3d/abri.scad).

**Choisir la taille** : l'entrée doit dépasser la carapace d'au moins 20 % en largeur et en hauteur.

| Taille | Carapace jusqu'à | Abri (L × l × h) | Entrée (l × h) | Fichiers |
|---|---|---|---|---|
| petit | 12 cm | 240 × 200 × 110 mm | 100 × 65 mm | `broutille_abri_petit.stl`, une pièce |
| moyen | 20 cm | 360 × 300 × 160 mm | 190 × 100 mm | `broutille_abri_moyen_quart0` à `3.stl` |
| grand | 30 cm | 500 × 440 × 220 mm | 290 × 150 mm | `broutille_abri_grand_quart0` à `3.stl` |

Pour chaque taille, ajoutez 4 `broutille_abri_patte.stl` (46 × 36 × 8 mm, à plat) et 4 `broutille_piquet.stl`.

Pour une sulcata adulte, aucune taille ne convient : il lui faut un abri en bois.

**Impression** : chaque fichier sort **à l'envers**, le dessus sur le plateau. C'est voulu : toutes les pentes font 45° ou plus, et l'entrée devient une encoche ouverte vers le haut. Aucun support. Mêmes réglages ASA que l'abreuvoir, avec 4 parois au lieu de 6.

**Assemblage des quarts** (moyen et grand) :

1. Posez les 4 quarts côte à côte, à l'endroit.
2. Alignez les nervures intérieures, de part et d'autre de chaque joint.
3. Boulonnez-les avec des vis M5 × 16, une rondelle et un écrou, par l'intérieur : 11 vis (le joint de l'avant n'en a que 2, à cause de l'entrée).

**Pose** :

- **Ancrage** : posez l'abri, puis glissez une `broutille_abri_patte.stl` dans chacune des 4 encoches du bas de la paroi, de l'extérieur, languette en avant, jusqu'à ce que la collerette touche la paroi. Plantez un `broutille_piquet.stl` (ou une sardine) dans le trou de 22 mm de chaque patte. La languette passe sous la paroi : l'abri ne glisse plus et ne se soulève plus. Pour le déplacer, retirez les 4 piquets.
- **Ombre et lumière** : un abri en plein soleil chauffe. Imprimez-le en couleur claire, ou posez-le à mi-ombre. Ne mettez jamais de lampe chauffante au-dessus : l'ASA ramollit vers 95 °C.
- **Sol** : un lit de terre ou de feuilles sous l'abri garde l'humidité, utile aux juvéniles.

### Pierre à griffes

![Pierre à griffes](modele_3d/apercus/broutille_pierre.png)

`broutille_pierre.stl`, une pièce de 246 × 198 × 13,5 mm avec ses pattes (dalle seule : 196 × 164 mm). Le dessus imite une ardoise : bosses et petites strates de 0 à 2,5 mm, sur une épaisseur de 11 mm. En marchant dessus, la tortue use ses griffes ; en broutant ce qui y est posé, elle use son bec. Source : [`modele_3d/pierre.scad`](modele_3d/pierre.scad). Ni imprimée ni essayée.

**Impression** :

1. Posez le fichier tel quel, à plat, relief vers le haut. Aucun support.
2. ASA ou PETG, couches de 0,2 mm, 4 parois, 5 couches pleines dessus, 20 % de remplissage.
3. ASA : bordure (brim) de 8 mm, la dalle est large et se décolle aux coins.
4. Couleur conseillée : gris ou brun mat, proche de la terre.

**Pose** :

1. Posez la dalle à plat, contre l'auge ou sur le passage qui y mène : la tortue la traverse à chaque repas.
2. Plantez 2 `broutille_piquet.stl` dans les pattes percées de 22 mm, comme pour l'auge. Sans pattes : `openscad -o stl/broutille_pierre.stl -D pattes=false pierre.scad`.
3. Pour le bec, posez de temps en temps une partie de la verdure sur la dalle plutôt que dans l'auge.

**Sécurité** :

- Le bord est un quart de rond de 9 mm qui descend à 3 mm du sol : rien de coupant, un juvénile monte et descend sans tomber.
- Le plastique s'use bien moins vite qu'une vraie pierre : regardez les griffes et le bec tous les mois. S'ils restent trop longs, ajoutez une vraie pierre plate ou une ardoise brute, et demandez conseil à un vétérinaire.
- Brossez la dalle à l'eau chaque semaine : la terre et les fientes restent dans le relief.

### Rampe

![Rampe, une de chaque côté de la bordure](modele_3d/apercus/broutille_rampe.png)

`broutille_rampe.stl` fait franchir à un juvénile une bordure de 60 mm (planche, parpaing, bord de bac) : 174 × 122 × 72 mm, pente de 22°, nervures rondes en travers tous les 14 mm, côtés de 12 mm. En haut, un palier de 30 mm arrive au niveau de la bordure. Source : [`modele_3d/rampe.scad`](modele_3d/rampe.scad). Ni imprimée ni essayée.

**Autre hauteur** : changez `hauteur` dans `rampe.scad`. La pente reste à 22° (25° au plus). Au-delà de 236 mm de long (bordure de plus de 85 mm environ), la rampe est coupée en tronçons qui s'emboîtent par une queue d'aronde verticale. Exemple pour 100 mm, 2 tronçons :

```bash
openscad -o stl/broutille_rampe_100_t0.stl -D hauteur=100 -D troncon=0 rampe.scad
openscad -o stl/broutille_rampe_100_t1.stl -D hauteur=100 -D troncon=1 rampe.scad
```

**Impression** :

1. Posez chaque fichier tel quel, à plat sur son grand dessous. Aucun support.
2. ASA ou PETG, couches de 0,2 mm, 4 parois, 15 % de remplissage : la rampe est pleine, inutile de la remplir plus.
3. Imprimez-en 2 : une de chaque côté de la bordure, pour que la tortue puisse revenir.

**Pose** :

1. Collez le palier contre la bordure, sur un sol plat et ferme.
2. Vérifiez que le palier arrive au ras du dessus de la bordure. S'il est plus bas, calez la rampe ou recalculez-la à la bonne hauteur.
3. Tronçons : posez le tronçon du pied, puis descendez le suivant par le dessus sur la queue d'aronde, jusqu'au sol.

**Sécurité** :

- Une tortue sur le dos ne se retourne pas toujours seule. Pente de 22° au plus et côtés bas : le juvénile ne bascule pas, et ne tombe pas sur le côté.
- La bordure elle-même doit être assez large pour qu'il n'en tombe pas (5 cm au moins), sinon posez une planche dessus.
- Observez les premiers passages. Si la tortue glisse sur les nervures mouillées, brossez-les : la mousse et la terre les rendent lisses.

### Berceau de pesée

![Berceau de pesée sur une balance de cuisine](modele_3d/apercus/broutille_pesee.png)

Une cuvette posée sur une balance de cuisine, où la tortue reste le temps de la pesée. Le fond à écailles en relief l'empêche de patiner ; les parois lisses à 60° l'empêchent de remonter. La face avant est droite, à l'aplomb du dessous : rien ne cache l'écran. Source : [`modele_3d/pesee.scad`](modele_3d/pesee.scad). Ni imprimé ni essayé.

| Taille | Carapace jusqu'à | Berceau (l × p × h) | Dessous | Fond plat | Fichier |
|---|---|---|---|---|---|
| juvénile | 10 cm | 129 × 106 × 41 mm | Ø 83 mm | Ø 80 mm | `broutille_pesee_juvenile.stl` |
| adulte | 20 cm | 218 × 181 × 66 mm | Ø 143 mm | Ø 140 mm | `broutille_pesee_adulte.stl` |

Masse estimée d'après le volume du fichier, imprimé plein en ASA : 50 g (juvénile), 145 g (adulte). La balance fait la tare, la masse compte peu.

**Impression** :

1. Posez le fichier tel quel, ouverture vers le haut. Aucun support : les parois font 60°.
2. ASA ou PETG, couches de 0,2 mm, 6 parois de 0,4 mm : la paroi de 2,4 mm sort pleine.
3. Le berceau sert à l'intérieur : du PLA convient aussi.

**Peser** :

1. Posez le berceau au centre du plateau, la face droite côté écran.
2. Appuyez sur TARE : l'écran affiche 0.
3. Posez la tortue au fond, à plat, et lisez le poids dès qu'il est stable.
4. Notez-le, à la même heure et avant le repas, pour comparer d'une semaine à l'autre.

**Sécurité** :

- Le dessous doit tenir entier sur le plateau de la balance. Pour l'adulte (Ø 143 mm), mesurez le plateau avant d'imprimer.
- Vérifiez la portée de la balance : tortue et berceau ensemble, souvent 5 kg au plus.
- Ne laissez pas la tortue seule dans le berceau : un adulte peut accrocher le bord avec les pattes avant.
- Le fond est plein : il retient l'urine, fréquente à la pesée. Rincez et séchez le berceau après chaque séance.

### Serre à juvéniles

![Serre à juvéniles, 2 panneaux de long, un couvercle levé](modele_3d/apercus/broutille_serre.png)

Un enclos fermé pour juvéniles : parois en panneaux, couvercle grillagé en alvéoles hexagonales de 12 mm (ni bec ni patte de chat ne passe), et une plaque de polycarbonate glissée dans le couvercle pour garder chaleur et humidité. Source : [`modele_3d/serre.scad`](modele_3d/serre.scad). Ni imprimée ni essayée.

**Dimensions** (2 panneaux de long, par défaut) : intérieur 466 × 216 × 150 mm, 534 × 284 mm hors tout sans les pattes. Chaque panneau de plus ajoute 250 mm de long : changez `n_long`. La largeur fait toujours un panneau.

| Pièce | Taille | Quantité pour `n_long` panneaux | Pour 2 |
|---|---|---|---|
| `broutille_serre_panneau.stl` | 232 × 20 × 150 mm | 2 × `n_long` + 2 | 6 |
| `broutille_serre_poteau_angle.stl` | 64 × 64 × 162 mm | 4 | 4 |
| `broutille_serre_poteau_droit.stl` | 38 × 67 × 162 mm | 2 × (`n_long` − 1) | 2 |
| `broutille_serre_couvercle.stl` | 249 × 249 × 12 mm | `n_long` | 2 |
| `broutille_serre_tourniquet.stl` | 60 × 16 × 4 mm | 2 × `n_long` + 2 | 6 |
| `broutille_piquet.stl` | 240 × 30 × 16 mm | un par poteau | 6 |

**À acheter** :

- Polycarbonate de 4 mm (compact ou alvéolaire) : une plaque de 240 × 238 mm par couvercle, découpée au cutter. Autre épaisseur ou autre taille : changez `pc` dans `serre.scad` (largeur de 234 à 244 mm) et réimprimez le couvercle.
- Une vis inox 4 × 30 à tête ronde par poteau, avec une rondelle.

**Impression** :

1. Posez chaque fichier tel quel : panneaux et poteaux debout, couvercle et tourniquet à plat. Aucun support.
2. ASA de préférence : la serre chauffe au soleil, et le PETG ramollit plus tôt. Couches de 0,2 mm, 4 parois, 15 % de remplissage.
3. Bordure (brim) de 8 mm sous les panneaux : ils sont hauts et minces.
4. Avant de tout lancer, imprimez un panneau et un poteau : le tenon doit glisser dans la mortaise sans forcer.

**Montage** :

1. Posez les poteaux à leur place, pattes vers l'extérieur.
2. Descendez chaque panneau par le haut dans les mortaises de deux poteaux, jusqu'au sol.
3. Plantez un piquet dans chaque patte.
4. Glissez la plaque dans le couvercle par le côté sans rail, sous les lèvres, jusqu'au fond. Elle passe l'ergot de l'avant en se cintrant un peu.
5. Posez les couvercles, côté sans rail vers l'avant : leurs coins s'emboîtent sur les bossages des poteaux.
6. Vissez un tourniquet sur chaque poteau, sans serrer à fond. Tournez-le sur les coins des couvercles pour fermer, de côté pour ouvrir.

**Sécurité** :

- **Plaque au soleil** : une serre fermée chauffe vite et peut tuer un juvénile. Placez-la à mi-ombre, mettez un thermomètre dedans, et retirez la plaque dès qu'il fait chaud : les alvéoles aèrent.
- Ménagez dans la serre un coin d'ombre, une cachette et de l'eau peu profonde.
- Les panneaux sont posés sur le sol : un juvénile peut creuser dessous. Enterrez-les de 2 à 3 cm, ou posez la serre sur un sol dur.

### Pondoir

![Pondoir : cadre de sable, rampe et couvercle grillagé](modele_3d/apercus/broutille_pondoir.png)

Un cadre de sable sans fond, de 440 × 440 × 160 mm (428 mm à l'intérieur), où la femelle creuse et pond. Des repères sont gravés à l'intérieur tous les 2 cm depuis le haut, de 2 à 14 cm. Après la ponte, un couvercle grillagé protège les œufs des prédateurs. Source : [`modele_3d/pondoir.scad`](modele_3d/pondoir.scad). Ni imprimé ni essayé.

![Repères de profondeur gravés sur la paroi intérieure](modele_3d/apercus/broutille_pondoir_reperes.png)

| Pièce | Taille | Quantité |
|---|---|---|
| `broutille_pondoir_coin.stl` | 249 × 249 × 160 mm | 4 |
| `broutille_pondoir_cle.stl` | 159 × 14 × 20 mm | 4 |
| `broutille_pondoir_rampe.stl` | 184 × 64 × 110 mm | 1 |
| `broutille_pondoir_couvercle.stl` | 249 × 249 × 20 mm | 4 |
| `broutille_pondoir_cle_couvercle.stl` | 18 × 10 × 3 mm | 8 |
| `broutille_piquet.stl` | 240 × 30 × 16 mm | 4 |

**À acheter** : environ 30 L de sable de rivière lavé (le cadre plein en contient 29 L), 4 étiquettes de jardin en plastique de 20 mm de large, un feutre indélébile.

**Impression** :

1. Coins debout, clés couchées, rampe couchée sur le côté : tels quels. Aucun support.
2. Couvercle **à l'envers**, tel quel : le dessus est sur le plateau, le rebord vers le haut. Les logements des clés font un pont de 10 mm, sans support.
3. ASA ou PETG, couches de 0,2 mm, 4 parois, 15 % de remplissage.

**Pose** :

1. Choisissez un endroit ensoleillé, au sol bien drainé.
2. Creusez une tranchée de 100 mm de profondeur, posez les 4 coins, et descendez une clé par le haut dans chaque joint.
3. Rebouchez autour. Il reste 60 mm hors sol : c'est la hauteur de la rampe. Pour une autre hauteur, réglez `hors_sol` (de 20 à 90 mm) et réimprimez la rampe.
4. Remplissez de sable humide jusqu'en haut, et tassez légèrement.
5. Accrochez la rampe sur un bord, au milieu d'un côté.

**Après la ponte** :

1. Retirez la rampe.
2. Posez les 4 quarts du couvercle, rebord à l'extérieur du cadre, et enfoncez les 8 petites clés dans leurs logements.
3. Plantez un piquet à chaque coin, à travers le coin du couvercle puis la patte du cadre : ni renard ni chien ne soulève le couvercle.
4. Écrivez la date de ponte sur une oreille au feutre, ou piquez une étiquette de jardin dans sa fente.
5. Si vous déterrez les œufs pour un incubateur, les repères disent à quelle profondeur ils étaient. Ne les retournez pas.

**Sécurité** : les alvéoles de 12 mm retiennent aussi les nouveau-nés. Regardez le pondoir chaque jour à l'approche de l'éclosion. Arrosez un peu le sable s'il sèche en surface.

### Mangeoire suspendue

![Mangeoire suspendue sur 2 piquets](modele_3d/apercus/broutille_suspendue.png)

`broutille_suspendue_ratelier.stl`, un râtelier de 250 × 97 × 110 mm : la verdure reste au-dessus du sol, propre, et les feuilles dépassent entre des barreaux ronds de 7 mm, espacés de 20 mm. Le fond en alvéoles laisse partir l'eau. Source : [`modele_3d/mangeoire_suspendue.scad`](modele_3d/mangeoire_suspendue.scad). Ni imprimée ni essayée.

**Sur 2 piquets** : chaque joue coiffe la tête d'un `broutille_piquet.stl`. La hauteur se règle en plantant les piquets plus ou moins profond : le fond du râtelier est 16 mm sous le dessus des têtes.

1. Plantez 2 piquets à 223 mm d'axe en axe, le grand côté de la tête (30 mm) en travers du râtelier.
2. Arrêtez quand le dessus des têtes est à la hauteur voulue plus 16 mm, à la même hauteur des deux côtés. Gardez au moins 80 mm de piquet en terre : le fond est alors à 145 mm du sol au plus.
3. Posez le râtelier sur les têtes.

**Sur ses pieds** : 2 `broutille_suspendue_pied.stl` (socle de 70 × 130 mm) mettent le fond à 60 mm du sol. Une `broutille_suspendue_rehausse.stl` sur chaque pied le monte de 40 mm, et elles s'empilent. Autre hauteur : `openscad -o stl/broutille_suspendue_pied.stl -D pied_h=80 -D 'piece="pied"' mangeoire_suspendue.scad`. Plantez un piquet dans un trou du socle si la tortue bouscule le râtelier.

![Mangeoire suspendue sur ses pieds, avec une rehausse](modele_3d/apercus/broutille_suspendue_pieds.png)

**Hauteur** : placez le fond un peu sous la tête de la tortue, debout et cou tendu. Elle broute ce qui dépasse et tire le reste entre les barreaux.

**Impression** :

1. Posez chaque fichier tel quel, fond sur le plateau. Aucun support : le haut des vides est en ogive.
2. ASA ou PETG, couches de 0,2 mm, 4 parois, 15 % de remplissage.

**Sécurité** :

- Le râtelier est seulement posé : une grosse sulcata peut le soulever. Pour elle, l'auge au sol convient mieux.
- Un juvénile passe la tête entre des barreaux espacés de 20 mm, et peut la coincer dans la pointe de l'ogive : pour lui, réduisez l'écart (`-D ecart=10`, qui resserre aussi les bouts du râtelier).
- Changez la verdure chaque jour et brossez le râtelier : les feuilles pourrissent entre les barreaux.

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

### Plusieurs caméras en même temps

Exemple : l'EZVIZ sur la mangeoire et une Mercusys sur l'abri.

1. Dans la ligne **Caméras**, cliquez **＋ Caméra** et donnez-lui un nom (Abri, Bassin…).
2. Choisissez sa source avec la liste **Caméra**, **📷 Caméra IP**, **🪟 Fenêtre** ou **🎞 Vidéo**, puis **⛶ Cadrer** si besoin.
3. Pour la surveiller seule, **▶ Démarrer** ; pour tout lancer d'un coup, **▶▶ Démarrer toutes**.

Chaque pastille montre l'état de sa caméra :

- **vert** : surveillée ;
- **rouge** : une tortue est à table ;
- **ambre** : image figée.

Un clic sur une pastille affiche cette caméra. La vidéo, le plein écran et les clics pour nommer une tortue concernent la caméra affichée. Un clic droit renomme ou retire une caméra.

Chaque visite note sa caméra : elle apparaît dans **Dernière visite** et dans la colonne `camera` du journal.

Au démarrage de Windows, toutes les caméras démarrent. Celles qui filment une fenêtre attendent que leur lecteur soit ouvert.

Deux caméras font environ deux fois plus de calcul : sur un PC sans carte graphique, l'analyse de chacune est un peu plus espacée.

### Caméra IP Wi-Fi (Mercusys MC510, Tapo…)

C'est la solution la plus simple : Broutille lit directement la caméra. Aucune appli n'a besoin de rester ouverte, et le direct ne se fige pas.

1. Dans l'appli Mercusys : **Accueil → carte de la caméra → Paramètres de l'appareil → Paramètres avancés → Compte de la caméra**. Créez un identifiant et un mot de passe (6 à 32 caractères), différents de votre compte Mercusys.
2. Dans la même appli, réglez la qualité vidéo sur **Meilleure qualité**.
3. Dans Broutille, cliquez **📷 Caméra IP**, puis **Chercher sur le Wi-Fi** : l'adresse de la caméra se remplit seule.
4. Entrez l'identifiant et le mot de passe du compte de la caméra, puis **Tester** : une image doit s'afficher.
5. Cliquez **Utiliser cette caméra**, puis **⛶ Cadrer** si la mangeoire n'occupe qu'une partie de l'image.

Le mot de passe n'apparaît jamais à l'écran (« Caméra IP : 192.168.1.184 »).

Si la recherche annonce « flux vidéo fermé », le compte de la caméra n'est pas encore créé.

Pour que l'adresse ne change pas, réservez-la dans votre box (bail DHCP fixe).

**Image légère (stream2)** : à choisir seulement si le PC rame. La reconnaissance des tortues préfère la haute qualité.

### Fenêtre ouverte (EZVIZ Studio...)

1. Ouvrez votre logiciel et affichez la caméra de la mangeoire.
2. Cliquez sur **🪟 Fenêtre**, puis choisissez la fenêtre dans la liste.
3. Cliquez sur **⛶ Cadrer** et tracez à la souris la zone de l'image de la mangeoire.

**Le cadrage est important** : il retire boutons, horloges et autres caméras de la mosaïque, et la tortue y gagne en taille.

**La vidéo est trouvée seule** : au démarrage, Broutille observe la fenêtre 2,5 s. La partie qui bouge est la vidéo ; boutons, listes et fonds restent fixes et sont retirés. Les clips et les photos ne gardent que l'image de la caméra. Si rien ne bouge (direct arrêté), seules les bandes unies autour sont retirées. Le cadre est revu toutes les minutes. **⛶ Cadrer** s'applique ensuite dans cette image : lancez-le pendant que le direct tourne.

Règles :

- La fenêtre doit rester ouverte, pas réduite dans la barre des tâches.
- **Elle peut être cachée par d'autres fenêtres**, Broutille agrandi par-dessus compris : la capture passe par Windows Graphics Capture (comme OBS), qui voit les lecteurs vidéo même cachés, EZVIZ Studio compris.
- Sur un Windows trop ancien ou sans le paquet `windows-capture`, Broutille revient à l'ancienne capture : certains lecteurs doivent alors rester visibles, sans rien par-dessus. Si une fenêtre les couvre, Broutille s'arrête de capturer plutôt que d'enregistrer la fenêtre du dessus.
- **EZVIZ Studio arrête le direct au bout d'un moment** : la vidéo reste figée. Après 1 min sans le moindre changement, Broutille sonne et affiche **IMAGE FIGÉE** en rouge sur la vidéo. Relancez le direct dans EZVIZ, ou laissez Broutille le faire (ci-dessous).

**Relance automatique du direct** :

1. **⚙ Réglages** › **Ouvrir d'abord ce programme** : EZVIZ Studio (proposé tout seul).
2. Cochez **L'ouvrir sans droits administrateur**. EZVIZ Studio demande ces droits ; tant qu'il les a, Windows interdit à Broutille de cliquer dedans.
3. Fermez EZVIZ Studio, puis rouvrez-le **par Broutille** : redémarrez Windows avec « Lancer Broutille au démarrage de Windows » coché, ou relancez Broutille avec le direct arrêté.
4. Dans EZVIZ, arrêtez le direct, puis **⚙ Réglages** › **📍 Montrer le bouton…** : posez la souris sur ce qui relance le direct (le bouton ▶, ou la caméra dans la liste de gauche) et ne bougez plus 3 secondes.
5. Cochez **Image figée : relancer le direct**, puis **Enregistrer**.

Quand l'image se fige, Broutille double-clique à cet endroit, sans bouger votre souris, jusqu'à 5 fois à 90 s d'écart. Si EZVIZ a encore les droits administrateur, le message « Relance impossible » le dit. Si EZVIZ fonctionne mal sans ces droits, décochez la case : l'alerte reste, la relance se fait à la main.
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

**Confirmer vite** : bouton **✅ À confirmer**. Les visites pas encore nommées défilent une par une, la plus récente d'abord, avec la tortue en grand et la scène à côté :

| Touche | Effet |
|---|---|
| **Entrée** | « Oui, c'est Zoé » : accepte la proposition de Broutille |
| **1** à **9** | cette tortue (le numéro est sur chaque bouton) |
| **Espace** | passer, sans rien changer |

**Nouvelle tortue…**, **Pas une tortue** (efface la visite) et **▶ Clip** se cliquent. Cinq minutes par semaine suffisent pour que la reconnaissance et l'analyse du comportement progressent nettement.

**Nommer une tortue en direct, sur la vidéo** : pendant la surveillance, cliquez sur le cadre d'une tortue (ou sur son étiquette). Le même menu s'ouvre : un nom, **Nouvelle tortue…** ou **Pas une tortue**.

- L'étiquette prend le nom aussitôt, et la visite sera notée à ce nom, comme corrigée à la main.
- Ses vues seules (sans voisine tout près) rejoignent la galerie de cette tortue à la fin de la visite.
- Un **cadre gris fin** avec un « ? » est une tortue pas encore confirmée : cliquez dessus pour la nommer quand même, et sa visite sera enregistrée. **Pas une tortue** fait disparaître le cadre, et Broutille ignorera ce qui y ressemble.
- Une tortue déjà partie ne se nomme plus sur la vidéo : corrigez sa visite dans l'historique.

> Si `visites.csv` est ouvert dans Excel, une correction est refusée avec un message : fermez Excel, puis recommencez. Les nouvelles visites, elles, attendent et ne sont pas perdues.

---

## 9. Mes tortues

### La fiche d'une tortue

Ouvrez-la à tout moment :

- double-clic sur la tortue dans **Mes tortues** ;
- clic sur la tortue dans la vidéo en direct, si elle est reconnue ;
- clic sur la photo ou le nom de **Dernière visite** ;
- clic droit sur une visite → **Fiche de…**.

| Onglet | Contenu |
|---|---|
| **Identité** | nom, espèce, sexe, date de naissance (15/03/2019, 03/2019 ou 2019), arrivée à la maison, origine, signes distinctifs, notes. L'âge se calcule seul. **Enregistrer** ou Ctrl+S. |
| **Poids** | pesées et courbe |
| **Photos** | **Album** : vos photos souvenirs, jamais utilisées pour reconnaître. **Vues apprises** : ce que Broutille a retenu. Clic droit : photo de profil, retirer une mauvaise vue. |
| **Carnet** | soins, vermifuge, vétérinaire, hibernation, ponte… datés |

La case *Les apprendre aussi pour la reconnaissance* ajoute aussi les photos à la galerie : seulement si la tortue y est bien visible.

### Clic droit sur une tortue

| Choix | Effet |
|---|---|
| **Fiche complète / Poids / Photos / Carnet** | ouvre la fiche sur cet onglet |
| **Apprendre des photos pour la reconnaissance…** | enrichit la galerie |
| **C'est la même tortue que** | fusionne deux fiches (album, carnet et identité compris) |
| **Supprimer la fiche…** | efface galerie et album ; ses visites restent, sous « Inconnue » |

### Sur le téléphone

1. Cliquez **📱 Téléphone**, puis cochez *Accès depuis le téléphone*.
2. Scannez le QR code avec l'appareil photo du téléphone. Le téléphone doit être sur le même Wi-Fi que le PC.
3. Au premier lancement, Windows demande d'autoriser Python : cochez **Réseaux privés**.
4. Sur le téléphone, ajoutez la page à l'écran d'accueil.

Sur la page :

- le direct, avec le nom des tortues reconnues ;
- les repas du jour et la dernière visite ;
- vos tortues : touchez-en une pour noter une **pesée**, un **soin**, ou ajouter une **photo** prise sur place.

La page est protégée par un code à 6 chiffres et n'est pas visible depuis Internet. **Nouveau code** déconnecte tous les téléphones.

### Alertes, même loin de la maison

Dans la fenêtre **📱 Téléphone**, cochez *Alertes sur le téléphone*, puis :

1. Installez l'appli gratuite **ntfy** (Play Store ou App Store).
2. Touchez **+** et scannez le QR code, ou collez le nom du sujet.
3. Cliquez **Envoyer un test** pour vérifier.

Vous êtes prévenu :

- quand une tortue n'est pas venue depuis le nombre de jours réglé ;
- quand elle a perdu 10 % de son poids ou plus ;
- quand l'image est figée depuis 5 minutes ;
- quand la surveillance s'arrête sur une erreur.

Chaque alerte n'est envoyée qu'une fois par épisode.

Les alertes passent par le service public ntfy.sh. Le nom du sujet, tiré au hasard, est la seule clé : ne le partagez pas.

### Clips verticaux pour Shorts, Reels et TikTok

Après la visite d'une tortue reconnue (15 s au moins), Broutille fait un clip vertical 1080×1920 de 25 s au plus :

- le cadre suit la tortue ;
- son nom et son âge sont incrustés ;
- les écrans « wait… » du lecteur sont coupés.

Il en fait un par tortue toutes les 3 h au plus. Les clips vont dans `partage/clips` (les 60 derniers sont gardés) et sur la page du téléphone, avec un bouton **Télécharger** pour les poster directement.

Pour en faire un à la demande : clic droit sur une visite → **🎬 Clip vertical**. La case *Clip vertical…* de la fenêtre **📱 Téléphone** active ou coupe les clips automatiques.

Si ffmpeg est installé, les clips sont en H.264, le format accepté partout. Sinon ils sont en MPEG-4.

### Plein écran pour un direct YouTube

**📺 Plein écran** (ou F11) montre la vidéo seule, habillée pour le public :

- nom et âge des tortues reconnues ; les douteuses restent sans étiquette ;
- « EN DIRECT », l'heure, les repas du jour ;
- rien de privé : pas de dossier, de réglage ni de chiffre technique.

Diffusez cette fenêtre avec OBS (source *Capture de fenêtre* « Broutille — en direct »).

| Touche | Effet |
|---|---|
| **P** | photo 1920×1080 dans le dossier `partage`, prête pour les réseaux sociaux |
| **Échap**, **F11** ou double-clic | sortir |

Couleurs : **orange** pour une fiche provisoire, **rouge** pour une tortue absente depuis trop longtemps.

La case *Créer une fiche pour une tortue inconnue*, en bas de fenêtre, est décochée d'office. Cochée, chaque inconnue crée une fiche ; pratique au tout début, mais une même tortue vue sous un autre angle peut en créer plusieurs, à fusionner ensuite.

---

## 10. Statistiques et alertes

- **Repas d'aujourd'hui** : temps à table par tortue.
- **📊 Statistiques** : sur 30 jours, visites, temps à table, jours de venue, dernière visite.
- **Repas jour par jour** : cliquez sur une tortue dans **📊 Statistiques**, ou clic droit sur elle dans *Mes tortues* › **Repas sur 30 jours**. Une barre par jour, la moyenne des jours venus en pointillé, un trait rouge sous chaque jour sans visite.
- **Alerte d'absence** : une tortue passe en rouge après 3 jours sans visite (réglable).

### Courbe de poids

Clic droit sur une tortue dans *Mes tortues* › **⚖ Pesées et courbe de poids**.

1. Pesez la tortue, de préférence à jeun et à la même heure (le berceau de pesée imprimé l'empêche de glisser).
2. Tapez le poids en grammes, par exemple `1250`, et une remarque si besoin (« après hibernation »).
3. Cliquez sur **Ajouter**. Une seconde pesée le même jour remplace la première.

La fenêtre montre la courbe, l'écart depuis la pesée précédente, sur 30 jours et sur un an. **Une perte de 10 % ou plus s'affiche en rouge.** Clic droit sur une pesée pour la retirer.

### Fiche pour le vétérinaire

Clic droit sur une tortue › **📄 Fiche pour le vétérinaire (PDF)**, ou le bouton du même nom dans **📊 Statistiques**. Broutille écrit un PDF de deux pages et l'ouvre :

- page 1 : photos de référence, résumé des 30 derniers jours (visites, jours venue, temps à table, plus longue absence, dernier poids), graphique des repas ;
- page 2 : courbe de poids et écarts, dernières visites, photos des dernières visites encore présentes.

Seules les visites où la tortue est reconnue ou confirmée comptent : confirmez les « Zoé ? » avant de faire la fiche. Les durées disent combien de temps elle est restée à la mangeoire, pas ce qu'elle a mangé.

Une tortue qui mange moins ou ne vient plus peut signaler un problème de santé, mais aussi une simple hibernation ou estivation. Broutille attire l'attention ; il ne remplace pas un vétérinaire.

### Comportement

Bouton **🧭 Comportement**. Tout vient du journal des visites, depuis la première : rien à installer. Choisissez la période (30 jours, 90 jours, 1 an, tout).

| Onglet | Ce qu'il montre |
|---|---|
| **Rythme** | les heures où chaque tortue mange (case plus claire = plus de temps à table), son heure d'arrivée moyenne et sa régularité (± minutes) |
| **Réseau social** | qui mange avec qui : un trait par paire, plus épais quand elles sont souvent ensemble ; le rond grossit avec le temps à table |
| **Dominance** | qui fait partir qui : une tortue arrive, l'autre s'en va dans la minute. Classement de la plus dominante à la moins dominante |
| **Déplacements** | sur une photo de la mangeoire, les endroits où chaque tortue passe son temps ; la distance parcourue (en longueurs de carapace) et la part du temps en mouvement ; pour chaque paire : temps au contact, « l'une sur l'autre » (monte ou coup de bélier), poursuites et qui suit qui. Positions notées depuis la version 1.2 seulement |
| **Santé** | les 7 derniers jours comparés aux 30 d'avant ; en rouge : mange deux fois moins, ne vient plus depuis 3 jours alors qu'elle venait presque tous les jours, ou arrive 2 h plus tôt ou plus tard |

- Seules les visites **nommées** comptent : plus vous confirmez de visites, plus l'analyse est juste.
- Les deux premières semaines, les chiffres restent des tendances (la fenêtre le signale).
- La dominance est un indice : une tortue part aussi parce qu'elle a fini. Elle devient parlante avec des dizaines de rencontres.

Toutes les visites sont dans `visites.csv`, lisible par Excel. Fermez-le après consultation pour permettre les corrections.

---

## 11. Réglages

| Réglage | Effet | Par défaut |
|---|---|---|
| Langue | interface, page du téléphone, alertes, graphiques et fiche PDF, en 13 langues ; appliquée au prochain démarrage | langue de Windows (anglais si elle n'est pas traduite) |
| Dossier des visites | où tout est rangé | `Vidéos\Broutille` |
| Signaler une tortue absente | alerte rouge | 3 jours |
| Effacer les clips après | ménage automatique | 60 jours |
| Taille maximale du dossier | ménage automatique | 20 Go |
| Démarrer à l'ouverture | surveillance automatique | non |
| Lancer Broutille au démarrage de Windows | raccourci dans le dossier Démarrage ; la surveillance démarre seule | non |
| Ouvrir d'abord ce programme | ouvert avant la surveillance, au démarrage de Windows ; Broutille attend sa fenêtre jusqu'à 2 min, puis 15 s que le direct s'affiche | EZVIZ Studio si la source est une fenêtre |
| L'ouvrir sans droits administrateur | permet la relance automatique du direct | non |
| Image figée : relancer le direct | double-clic sur le bouton montré avec **📍** | non |
| Sauvegarde quotidienne dans | une archive par jour (journal, fiches, pesées, galeries ; pas les clips), les 7 dernières gardées | vide : pas de sauvegarde |
| Rappeler de peser une tortue après | une tortue jamais pesée, ou pesée il y a plus longtemps, passe en orange avec ⚖ dans *Mes tortues* | 30 jours |
| Espèces présentes | candidates pour l'espèce | radiée, sillonnée |
| Oublier les « Pas une tortue » | annule ces marquages | — |

Le curseur **Exigence pour nommer une tortue**, en bas de fenêtre :

- trop de fausses identités : montez-le ;
- trop d'« Inconnue » alors que votre galerie est fournie : baissez-le un peu.

Le ménage ne touche jamais au journal ni aux galeries des tortues.

**Sauvegarde** : choisissez un dossier sur une clé USB, un autre disque ou OneDrive. Broutille y écrit `Broutille_AAAA-MM-JJ.zip` une fois par jour, dès l'ouverture puis toutes les heures s'il manque celui du jour, et garde les 7 derniers. Pour restaurer : Broutille fermé, ouvrez l'archive et copiez son contenu dans le dossier des visites. Une clé débranchée ne bloque rien : le message « Sauvegarde impossible » s'affiche et Broutille réessaie l'heure suivante.

**Démarrage avec Windows et EZVIZ Studio** : EZVIZ Studio demande les droits administrateur, donc Windows peut afficher sa fenêtre de confirmation au démarrage : acceptez-la. Si EZVIZ ne relance pas le direct de lui-même, cliquez sur le bouton ▶ de la caméra ; Broutille voit la vidéo dès qu'elle bouge.

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
| Fenêtre : image noire, ou « aucune image » | fenêtre réduite, ou ancienne capture (paquet `windows-capture` absent) avec la fenêtre cachée | ne pas réduire la fenêtre ; relancer `installer.bat`, ou garder la fenêtre visible |
| Fenêtre : image figée | le lecteur a arrêté le direct (EZVIZ Studio le fait au bout d'un moment) | relancer le direct dans le lecteur |
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
