// ============================================================
//  BROUTILLE — la mangeoire qui reconnaît ses tortues
//  Auge au sol pour tortues terrestres (radiata, sulcata...) :
//  - auges basses à mettre bout à bout : autant que de tortues
//  - plantées par 2 piquets imprimés, en diagonale : une sulcata qui
//    pousse ne les déplace pas, une auge ne peut pas pivoter
//  - bord bas et arrondi, flancs rentrants : stable, rien à mordre,
//    à portée d'un juvénile comme d'un adulte
//  - fond percé pour l'eau de pluie ; pas de trémie : verdure, foin
//    et fruits sont posés dans l'auge
//  - la webcam USB reste libre, à distance, en vue large
//
//  Pièces (variable piece) — la plus grande fait 248 mm (plateau 256 x 256 minimum) :
//    auge (x3 conseillé), piquet (x2 par auge)
//    assemblage : vue d'ensemble
//
//  Impression : ASA (soleil) ou PETG, jamais de PLA dehors. 0.2 mm,
//  4 périmètres ; auge 25 % de remplissage, piquet 100 %. Sans supports.
//  Couleur conseillée : gris moyen mat, pour que la tortue ressorte.
//  Repère : X = longueur, Y = largeur, Z = haut.
// ============================================================

piece = "assemblage"; // [assemblage, auge, piquet]

/* [Auge] */
long    = 200;    // longueur à la base : les auges se touchent par la base
larg    = 170;    // largeur à la base
haut    = 50;     // hauteur du bord
fond    = 6;      // épaisseur du fond
rentre  = 8;      // retrait du bord par rapport à la base (flancs rentrants)
bord    = 10;     // largeur du bord
trou_d  = 6;      // drainage

/* [Piquets] */
pattes_x = 60;    // position des pattes le long de l'auge
patte_r  = 18;    // rayon de la patte
patte_h  = 8;     // épaisseur de la patte
passage  = 22;    // trou de la patte : large, un trou imprimé sort toujours un peu plus petit
piq_l    = 240;   // longueur du piquet
piq_s    = 16;    // côté de la section en T
piq_e    = 5;     // épaisseur de la section
tete_l   = 30;    // largeur de la tête : plus large que le trou
tete_p   = 14;    // épaisseur de la tête

$fn = 64;

// ------------------------------------------------------------
module rrect(w, l, r) { offset(r) square([w - 2*r, l - 2*r], center = true); }
module niveau(w, l, r, z) { translate([0, 0, z]) linear_extrude(0.01) rrect(w, l, r); }

y_patte = larg/2 + 21;      // 10 mm de matière entre le trou et la coque
module pattes() {
    for (s = [-1, 1]) translate([s*pattes_x, s*y_patte, 0]) children();
}

module auge() {
    difference() {
        union() {
            // coque : base large, bord arrondi
            hull() {
                niveau(long, larg, 22, 0);
                niveau(long - 2*rentre + 2, larg - 2*rentre + 2, 18, haut - 5);
                niveau(long - 2*rentre, larg - 2*rentre, 17, haut - 1.2);
                niveau(long - 2*rentre - 3, larg - 2*rentre - 3, 15.5, haut);
            }
            // pattes, larges à la racine, et gousset contre la coque pour encaisser la poussée
            for (s = [-1, 1]) {
                hull() {
                    translate([s*pattes_x, s*y_patte, 0]) cylinder(r = patte_r, h = patte_h);
                    translate([s*pattes_x - patte_r - 8, s*(larg/2 - 6) - 2, 0]) cube([2*patte_r + 16, 4, patte_h]);
                }
                hull() {
                    translate([s*pattes_x - 10, s*(larg/2 + 6) - 2, 0]) cube([20, 4, patte_h]);
                    translate([s*pattes_x - 10, s*(larg/2 - rentre - 2) - 2, 0]) cube([20, 4, haut*0.7]);
                }
            }
        }
        // cuvette, évasée : facile à vider et à brosser
        hull() {
            niveau(long - 2*rentre - 2*bord - 22, larg - 2*rentre - 2*bord - 22, 10, fond);
            niveau(long - 2*rentre - 2*bord - 2, larg - 2*rentre - 2*bord - 2, 12, fond + 10);
            niveau(long - 2*rentre - 2*bord + 5, larg - 2*rentre - 2*bord + 5, 13, haut + 0.1);
        }
        // drainage
        for (x = [-50, 0, 50], y = [-36, 0, 36]) translate([x, y, -1]) cylinder(d = trou_d, h = fond + 2);
        // passage des piquets
        pattes() translate([0, 0, -1]) cylinder(d = passage, h = patte_h + 2);
        // nom gravé sur le bord
        translate([0, -72.5, haut - 0.6]) linear_extrude(1)
            text("BROUTILLE", size = 3.5, halign = "center", valign = "center", font = "Liberation Sans:style=Bold");
    }
}

// Piquet en T couché : le plat de la section sur le plateau d'impression, la pointe s'affine
// dans les deux sens pour entrer dans la terre sans fendre.
module piquet() {
    pointe = 80;
    intersection() {
        union() {
            // tête, frappée au maillet
            hull() {
                translate([0, -tete_l/2 + 4, 0]) cube([tete_p, tete_l - 8, piq_s]);
                translate([3, -tete_l/2, 0]) cube([tete_p - 3, tete_l, piq_s - 3]);
            }
            // section en T
            translate([tete_p - 1, -piq_s/2, 0]) cube([piq_l - tete_p + 1, piq_s, piq_e]);
            translate([tete_p - 1, -piq_e/2, 0]) cube([piq_l - tete_p + 1, piq_e, piq_s]);
        }
        // profil de la pointe, vu de dessus
        linear_extrude(piq_s + 1) polygon([[-1, -tete_l/2 - 1], [piq_l - pointe, -tete_l/2 - 1], [piq_l, -1],
                                           [piq_l, 1], [piq_l - pointe, tete_l/2 + 1], [-1, tete_l/2 + 1]]);
        // profil de la pointe, vu de côté
        rotate([90, 0, 0]) linear_extrude(tete_l + 4, center = true)
            polygon([[-1, -1], [piq_l + 1, -1], [piq_l + 1, 1.5], [piq_l - pointe, piq_s + 1], [-1, piq_s + 1]]);
    }
}

// ------------------------------------------------------------
if      (piece == "auge")   auge();
else if (piece == "piquet") translate([-piq_l/2, 0, 0]) piquet();
else {
    for (i = [-1, 0, 1]) translate([i*long, 0, 0]) {
        color("SlateGray") auge();
        // piquets plantés : tête sur la patte, le reste en terre
        pattes() color("DimGray") translate([piq_e/2, 0, patte_h + tete_p]) rotate([0, 90, 0]) piquet();
    }
    // sol : fantôme
    %translate([0, 0, -1]) cube([1000, 620, 2], center = true);
}
