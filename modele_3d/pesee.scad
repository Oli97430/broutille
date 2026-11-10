// ============================================================
//  BROUTILLE — berceau de pesée, posé sur une balance de cuisine
//  - cuvette à fond plat et parois raides (60°), lisses : la tortue
//    se pose au fond, ne glisse pas et ne remonte pas le bord
//  - fond à écailles en relief, comme l'abreuvoir : prise pour les
//    pattes, la tortue reste calme au lieu de patiner
//  - dessous plat, d'une pièce : stable sur le plateau de la balance
//  - paroi de 2,4 mm : léger, la balance fait la tare
//  - face avant droite, à l'aplomb du fond : rien ne déborde au-dessus
//    de l'écran de la balance
//  - fond plein : il retient l'urine, fréquente à la pesée
//
//  Une seule pièce, à plat, ouverture vers le haut, sans supports.
//  Repère : Z = haut, face avant (côté écran) en Y-.
// ============================================================

taille = "juvenile"; // [juvenile, adulte]
piece  = "berceau";  // [berceau, assemblage]

/* [Paroi] */
e      = 2.4;     // épaisseur des parois : 6 traits de 0,4 mm
fe     = 2.0;     // épaisseur du fond, sous le relief
angle  = 60;      // pente des parois, au-dessus de 45° : imprimable, et trop raide pour grimper
relief = 1.2;     // saillie des écailles du fond

$fn = 128;

// ------------------------------------------------------------
//  taille : diamètre du fond plat intérieur, hauteur du bord
//  juvénile : carapace jusqu'à 10 cm ; adulte : jusqu'à 20 cm
// ------------------------------------------------------------
T = taille == "adulte" ? [140, 65] : [80, 40];
ri0 = T[0]/2; H = T[1];
ta  = tan(angle);
de  = e/sin(angle);                     // épaisseur mesurée à l'horizontale
function ri(z) = ri0 + (z - fe)/ta;     // rayon intérieur à la hauteur z
function ro(z) = ri(z) + de;            // rayon extérieur
ro0 = ro(0);                            // rayon du dessous, posé sur la balance
yf  = ro0;                              // face avant, tangente au dessous

// section pleine : la cuvette est creusée après la coupe avant, qui laisse ainsi une paroi droite
module profil_plein() {
    rc = de/2; xc = (ri(H) + ro(H))/2;
    polygon(concat([[0, 0], [ro0, 0], [ro(H), H]],
                   [for (a = [10 : 10 : 170]) [xc + rc*cos(a), H + rc*sin(a)]],
                   [[ri(H), H], [0, H]]));
}
module profil_creux() {
    polygon([[-1, fe], [ri0, fe], [ri(H), H], [ri(H), H + 10], [-1, H + 10]]);
}

module coque() {
    difference() {
        intersection() {
            rotate_extrude() profil_plein();
            translate([-200, -yf, -1]) cube([400, 400, H + 10]);
        }
        intersection() {
            rotate_extrude() intersection() { profil_creux(); square([300, 300]); }
            translate([-200, -yf + e, fe - 0.01]) cube([400, 400, H + 20]);
        }
    }
}

// écaille de la dossière : hexagone et étoile, comme l'abreuvoir
module ecaille(r, l = 1.7) {
    difference() { circle(r + 0.1, $fn = 6); circle(r - l, $fn = 6); }   // + 0,1 : voisines qui se chevauchent, pas de bord commun
    for (a = [30 : 60 : 330]) rotate(a) translate([0, -l/2 + 0.2]) square([r*0.72, l - 0.4]);
}
module motif_fond() {
    r = 13; pasx = r*sqrt(3);
    translate([0, 0, fe - 0.01]) linear_extrude(relief + 0.01) intersection() {
        circle(r = ri0 - 1.5);
        translate([-200, -yf + e + 1.5]) square([400, 400]);
        union() for (i = [-6 : 6], j = [-6 : 6])
            translate([i*pasx + (j % 2)*pasx/2, j*1.5*r]) rotate(30) ecaille(r);
    }
}

module berceau() { coque(); motif_fond(); }

echo(str("berceau ", taille, " : dessous Ø ", round(2*ro0), " mm, bord Ø ", round(2*ro(H)), " mm, ", H, " mm de haut"));

// ------------------------------------------------------------
if (piece == "berceau") berceau();
else {
    color("SlateGray") berceau();
    // balance de cuisine schématique : plateau Ø 150 et écran à l'avant
    %translate([0, 0, -6]) cylinder(d = 150, h = 6);
    %translate([-100, -110, -30]) cube([200, 220, 24]);
}
