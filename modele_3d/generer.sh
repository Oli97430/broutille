#!/bin/bash
# Génère tous les STL et les aperçus : bash modele_3d/generer.sh
cd "$(dirname "$0")"
command -v openscad >/dev/null || { echo "OpenSCAD introuvable"; exit 1; }
mkdir -p stl apercus
for piece in auge piquet; do
    openscad -o "stl/broutille_$piece.stl" -D "piece=\"$piece\"" broutille.scad 2>&1 | grep -E "ERROR|WARNING|Simple:|Volumes" | sed "s/^/$piece: /" &
done
openscad -o stl/broutille_abreuvoir.stl abreuvoir.scad 2>&1 | grep -E "ERROR|WARNING|Simple:|Volumes" | sed "s/^/abreuvoir: /" &
wait
openscad -o apercus/broutille_ensemble.png -D 'piece="assemblage"' --imgsize=1400,900 \
    --camera=0,0,40,55,0,25,1900 --projection=p --colorscheme=Tomorrow broutille.scad 2>/dev/null
openscad -o apercus/broutille_auge.png -D 'piece="auge"' --imgsize=1000,800 \
    --camera=0,0,25,50,0,30,620 --projection=p --colorscheme=Tomorrow broutille.scad 2>/dev/null
openscad -o apercus/broutille_piquet.png -D 'piece="piquet"' --imgsize=1000,500 \
    --camera=0,0,8,50,0,20,420 --projection=p --colorscheme=Tomorrow broutille.scad 2>/dev/null
openscad -o apercus/broutille_abreuvoir.png -D 'piece="abreuvoir"' --imgsize=1300,1000 \
    --camera=0,0,10,48,0,25,560 --projection=p --colorscheme=Tomorrow abreuvoir.scad 2>/dev/null
# abri-cachette : petit d'une pièce, moyen et grand en 4 quarts, 4 pattes rapportées (environ 10 min)
openscad -o stl/broutille_abri_petit.stl -D 'taille="petit"' abri.scad 2>&1 | grep -E "ERROR|WARNING|Volumes" | sed "s/^/abri petit: /" &
openscad -o stl/broutille_abri_patte.stl -D 'piece="patte"' abri.scad 2>&1 | grep -E "ERROR|WARNING|Volumes" | sed "s/^/abri patte: /" &
for t in moyen grand; do for q in 0 1 2 3; do
    openscad -o "stl/broutille_abri_${t}_quart$q.stl" -D "taille=\"$t\"" -D 'piece="quart"' -D "quart=$q" abri.scad 2>&1 | grep -E "ERROR|WARNING|Volumes" | sed "s/^/abri $t $q: /" &
done; done
wait
openscad -o apercus/broutille_abri.png -D 'taille="petit"' -D 'piece="assemblage"' --imgsize=1300,1000 \
    --camera=0,0,40,58,0,35,620 --projection=p --colorscheme=Tomorrow abri.scad 2>/dev/null
openscad -o apercus/broutille_abri_dessous.png -D 'taille="moyen"' -D 'piece="assemblage"' --imgsize=1300,1000 \
    --camera=0,0,60,140,0,200,900 --projection=p --colorscheme=Tomorrow abri.scad 2>/dev/null
# accessoires : pierre à griffes, rampe (bordure de 60 mm), berceau de pesée (environ 2 min)
openscad -o stl/broutille_pierre.stl pierre.scad 2>&1 | grep -E "ERROR|WARNING|Volumes" | sed "s/^/pierre: /" &
openscad -o stl/broutille_rampe.stl rampe.scad 2>&1 | grep -E "ERROR|WARNING|Volumes" | sed "s/^/rampe: /" &
for t in juvenile adulte; do
    openscad -o "stl/broutille_pesee_$t.stl" -D "taille=\"$t\"" pesee.scad 2>&1 | grep -E "ERROR|WARNING|Volumes" | sed "s/^/pesee $t: /" &
done
wait
openscad -o apercus/broutille_pierre.png --imgsize=1300,1000 \
    --camera=0,0,0,50,0,25,560 --projection=p --colorscheme=Tomorrow pierre.scad 2>/dev/null
openscad -o apercus/broutille_rampe.png -D 'piece="assemblage"' --imgsize=1300,1000 \
    --camera=150,0,30,60,0,215,700 --projection=p --colorscheme=Tomorrow rampe.scad 2>/dev/null
openscad -o apercus/broutille_pesee.png -D 'taille="adulte"' -D 'piece="assemblage"' --imgsize=1300,1000 \
    --camera=0,0,0,55,0,25,620 --projection=p --colorscheme=Tomorrow pesee.scad 2>/dev/null
# serre à juvéniles, pondoir, mangeoire suspendue (environ 5 min)
for p in panneau poteau_angle poteau_droit couvercle tourniquet; do
    openscad -o "stl/broutille_serre_$p.stl" -D "piece=\"$p\"" serre.scad 2>&1 | grep -E "ERROR|WARNING|Volumes" | sed "s/^/serre $p: /" &
done
for p in coin cle couvercle cle_couvercle rampe; do
    openscad -o "stl/broutille_pondoir_$p.stl" -D "piece=\"$p\"" pondoir.scad 2>&1 | grep -E "ERROR|WARNING|Volumes" | sed "s/^/pondoir $p: /" &
done
for p in ratelier pied rehausse; do
    openscad -o "stl/broutille_suspendue_$p.stl" -D "piece=\"$p\"" mangeoire_suspendue.scad 2>&1 | grep -E "ERROR|WARNING|Volumes" | sed "s/^/suspendue $p: /" &
done
wait
openscad -o apercus/broutille_serre.png -D 'piece="assemblage"' --imgsize=1300,1000 \
    --camera=250,125,60,55,0,25,1300 --projection=p --colorscheme=Tomorrow serre.scad 2>/dev/null
openscad -o apercus/broutille_pondoir.png -D 'piece="assemblage"' --imgsize=1300,1000 \
    --camera=0,0,120,58,0,20,1500 --projection=p --colorscheme=Tomorrow pondoir.scad 2>/dev/null
openscad -o apercus/broutille_pondoir_reperes.png -D 'piece="coin"' --imgsize=1300,1000 \
    --camera=120,120,80,60,0,225,500 --projection=p --colorscheme=Tomorrow pondoir.scad 2>/dev/null
openscad -o apercus/broutille_suspendue.png -D 'piece="assemblage"' --imgsize=1300,1000 \
    --camera=0,0,90,62,0,25,800 --projection=p --colorscheme=Tomorrow mangeoire_suspendue.scad 2>/dev/null
openscad -o apercus/broutille_suspendue_pieds.png -D 'piece="assemblage_pieds"' --imgsize=1300,1000 \
    --camera=0,0,110,62,0,25,850 --projection=p --colorscheme=Tomorrow mangeoire_suspendue.scad 2>/dev/null
