#!/bin/bash
# Génère tous les STL et les aperçus : bash modele_3d/generer.sh
cd "$(dirname "$0")"
command -v openscad >/dev/null || { echo "OpenSCAD introuvable"; exit 1; }
mkdir -p stl apercus
for piece in auge piquet; do
    openscad -o "stl/broutille_$piece.stl" -D "piece=\"$piece\"" broutille.scad 2>&1 | grep -E "ERROR|WARNING|Simple:|Volumes" | sed "s/^/$piece: /" &
done
wait
openscad -o apercus/broutille_ensemble.png -D 'piece="assemblage"' --imgsize=1400,900 \
    --camera=0,0,40,55,0,25,1900 --projection=p --colorscheme=Tomorrow broutille.scad 2>/dev/null
openscad -o apercus/broutille_auge.png -D 'piece="auge"' --imgsize=1000,800 \
    --camera=0,0,25,50,0,30,620 --projection=p --colorscheme=Tomorrow broutille.scad 2>/dev/null
openscad -o apercus/broutille_piquet.png -D 'piece="piquet"' --imgsize=1000,500 \
    --camera=0,0,8,50,0,20,420 --projection=p --colorscheme=Tomorrow broutille.scad 2>/dev/null
