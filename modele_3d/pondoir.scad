// ============================================================
//  BROUTILLE — pondoir : cadre de sable sans fond
//  - 4 coins identiques en L, liés par des clés en papillon verticales
//    qui descendent par le haut : un carré de 440 mm, sans vis
//  - sans fond : posé sur le sol, ou enfoncé (100 mm conseillés),
//    rempli de sable jusqu'en haut
//  - repères de profondeur gravés à l'intérieur, tous les 2 cm depuis
//    le haut : on note à quelle profondeur sont les œufs
//  - rampe douce (20°) accrochée sur le bord, pour entrer
//  - couvercle grillagé en 4 quarts : alvéoles de 12 mm, rebord qui
//    descend autour du cadre, et 4 piquets qui traversent couvercle et
//    pattes du cadre : un renard ou un rat ne le soulève pas
//  - une oreille par quart, pour écrire la date ou piquer une
//    étiquette de jardin
//
//  Pièces (variable piece), toutes déjà orientées, sans supports :
//    coin (x4), cle (x4), couvercle (x4, imprimé à l'envers),
//    cle_couvercle (x8), rampe (x1)
//    assemblage : vue d'ensemble
//  Repère : centre du cadre en X = Y = 0, Z = haut, bas du cadre en Z = 0.
// ============================================================

piece = "assemblage"; // [coin, cle, couvercle, cle_couvercle, rampe, assemblage]

/* [Cadre] */
cote     = 440;   // côté extérieur du cadre
H        = 160;   // hauteur du cadre
e        = 6;     // épaisseur de paroi
hors_sol = 60;    // hauteur au-dessus du sol, cadre enfoncé : règle la rampe

/* [Repères de profondeur] */
pas_rep  = 20;    // un repère tous les 2 cm, mesuré depuis le haut
rep_l    = 50;    // longueur d'un trait

/* [Clés du cadre] */
cl_col   = 8;     // largeur au joint
cl_bout  = 14;    // largeur au bout
cl_l     = 10;    // demi-longueur
jeu      = 0.25;

/* [Pattes] */
passage  = 22;
patte_r  = 16;
patte_h  = 8;
patte_o  = 13;    // centre du trou, depuis le coin extérieur, sur chaque axe

/* [Couvercle] */
tc       = 5;     // épaisseur
maille   = 12;    // ouverture d'une alvéole, de sommet à sommet : 12 au plus
barre    = 3;
reb_h    = 15;    // rebord qui descend autour du cadre
reb_e    = 3;
reb_jeu  = 1;
kc_col   = 6.5;     // clés du couvercle : col, bout, demi-longueur
kc_bout  = 10;
kc_l     = 9;
kc_p     = 3.2;   // profondeur des logements ; la clé fait 3 mm

/* [Étiquette] */
et_l     = 21;    // fente pour une étiquette de jardin de 20 mm
et_e     = 2.4;

/* [Rampe] */
pente    = 20;    // angle de la montée
larg_r   = 110;   // largeur de la rampe

$fn = 48;

use <broutille.scad>   // piquet(), pour la vue d'ensemble

// ------------------------------------------------------------
So  = cote/2;                       // demi-côté extérieur
Si  = So - e;                       // face intérieure
yb  = So + 5;                       // axe des clés du cadre
pc  = So + patte_o;                 // centre des pattes, sur chaque axe
n_rep = floor((H - 10)/pas_rep);
Tq  = So + reb_jeu + reb_e;         // bord extérieur d'un quart de couvercle

assert(maille <= 12, "alvéoles de 12 mm au plus");
assert(pc + patte_r <= 250, "coin trop grand pour le plateau");
assert(hors_sol >= 20 && hors_sol <= 90, "rampe prévue pour 20 à 90 mm hors sol");

// queue d'aronde, vue de dessus : col sur x = 0, bout en x = l
module aronde2d(c, b, l, j = 0) {
    polygon([[-1, -c/2 - j], [0, -c/2 - j], [l + j, -b/2 - j], [l + j, b/2 + j], [0, c/2 + j], [-1, c/2 + j]]);
}
module papillon2d(c, b, l) {
    polygon([[-l, -b/2], [0, -c/2], [l, -b/2], [l, b/2], [0, c/2], [-l, b/2]]);
}

// ------------------------------------------------------------
//  Coin : imprimé debout, tel qu'il est posé
// ------------------------------------------------------------
module section_paroi() {            // dans le plan (épaisseur, z), haut en demi-rond
    translate([0, 0]) square([e, H - e/2]);
    translate([e/2, H - e/2]) circle(d = e);
}
// une branche : la paroi le long de X, de x = jeu au coin, et son bossage
module branche() {
    translate([0, Si, 0]) rotate([90, 0, 90]) linear_extrude(So) section_paroi();
    translate([0, Si, 0]) cube([16, yb + 11 - Si, H]);
}
// repères : traits en V (dessous plat, dessus incliné : rien en surplomb)
// et chiffres gravés ; face en y = 0, matière en y > 0, lisible depuis y < 0
module reperes() {
    for (k = [1 : n_rep]) {
        z = H - k*pas_rep;
        translate([-rep_l/2, 0, 0]) rotate([90, 0, 90]) linear_extrude(rep_l)
            polygon([[-0.01, z], [0.8, z], [-0.01, z + 1.6]]);
        translate([rep_l/2 + 3, 0.6, z]) rotate([90, 0, 0]) linear_extrude(1)
            text(k == 1 ? str(k*pas_rep/10, " cm") : str(k*pas_rep/10), size = 7, valign = "bottom",
                 font = "Liberation Sans:style=Bold");
    }
}
module coin() {
    difference() {
        union() {
            branche();
            multmatrix([[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, 1, 0]]) branche();   // seconde branche, symétrique
            translate([Si + e/2, Si + e/2, H - e/2]) sphere(d = e);
            hull() {
                translate([pc, pc, 0]) cylinder(r = patte_r, h = patte_h);
                translate([Si, Si, 0]) cube([e, e, patte_h]);
            }
        }
        // mortaises des clés, ouvertes en haut et en bas
        translate([0, yb, -1]) linear_extrude(H + 2) aronde2d(cl_col, cl_bout, cl_l, jeu);
        translate([yb, 0, -1]) linear_extrude(H + 2) rotate(90) mirror([0, 1]) aronde2d(cl_col, cl_bout, cl_l, jeu);
        translate([pc, pc, -1]) cylinder(d = passage, h = patte_h + 2);
        // repères, au milieu de chaque branche
        translate([So/2 + 10, Si, 0]) reperes();
        translate([Si, So/2 - 10, 0]) rotate(-90) reperes();
        // les deux coins voisins se touchent à 2 x jeu près
        translate([-1, -1, -1]) cube([1 + jeu, So + 40, H + 2]);
        translate([-1, -1, -1]) cube([So + 40, 1 + jeu, H + 2]);
    }
}

// clé papillon du cadre : imprimée couchée, le grand axe à la verticale
module cle() { translate([0, 0, cl_l]) rotate([0, -90, 0]) linear_extrude(H - 1) papillon2d(cl_col, cl_bout, cl_l); }
module cle_couvercle() { linear_extrude(3) papillon2d(kc_col - 0.3, kc_bout - 0.3, kc_l - 0.2); }

// ------------------------------------------------------------
//  Quart de couvercle, en position : plaque de z = 0 à tc, posée sur le cadre
//  rebord et guide d'étiquette vers le bas ; on l'imprime à l'envers
// ------------------------------------------------------------
module alveoles2d(x0, x1) {
    r  = maille/2;
    a  = r*sqrt(3) + barre;
    dy = a*sqrt(3)/2;
    for (j = [0 : ceil((x1 - x0)/dy) + 1], i = [-1 : ceil((x1 - x0)/a) + 1]) {
        x = x0 + r + (i + (j % 2)/2)*a; y = x0 + r + j*dy;
        if (x >= x0 + r && x <= x1 - r && y <= x1 - r) translate([x, y]) rotate(30) circle(r, $fn = 6);
    }
}
oreille = [[90, 150], Tq + 24];      // oreille d'étiquette : de y = 90 à 150, jusqu'à x = Tq + 24
module couvercle_pose() {
    difference() {
        union() {
            linear_extrude(tc) difference() {
                union() {
                    translate([0.5, 0.5]) square([Tq - 0.5, Tq - 0.5]);
                    hull() { translate([pc, pc]) circle(r = patte_r); translate([Tq - 20, Tq - 20]) square(20); }
                    translate([Tq - 1, oreille[0][0]]) square([oreille[1] - Tq + 1, oreille[0][1] - oreille[0][0]]);
                }
                alveoles2d(15, Si - 3);
            }
            // rebord, interrompu au milieu des côtés (bossages des clés)
            translate([So + reb_jeu, 24, -reb_h]) cube([reb_e, Tq - 24, reb_h + 0.01]);
            translate([24, So + reb_jeu, -reb_h]) cube([Tq - 24, reb_e, reb_h + 0.01]);
            // guide de l'étiquette, sous l'oreille
            translate([Tq + 8, (oreille[0][0] + oreille[0][1])/2 - et_l/2 - 3, -14]) cube([et_e + 6, et_l + 6, 14.01]);
        }
        translate([pc, pc, -1]) cylinder(d = passage, h = tc + 2);
        translate([Tq + 11, (oreille[0][0] + oreille[0][1])/2 - et_l/2, -15]) cube([et_e, et_l, tc + 16]);
        // logements des clés, ouverts par le dessus
        for (p = [60, 150]) {
            translate([0, p, tc - kc_p]) linear_extrude(kc_p + 1) aronde2d(kc_col, kc_bout, kc_l, 0.15);
            translate([p, 0, tc - kc_p]) linear_extrude(kc_p + 1) rotate(90) mirror([0, 1]) aronde2d(kc_col, kc_bout, kc_l, 0.15);
        }
    }
}
module couvercle() { translate([0, 0, tc]) mirror([0, 0, 1]) couvercle_pose(); }

// ------------------------------------------------------------
//  Rampe : un profil extrudé, imprimé couché sur le côté
//  x = vers l'extérieur depuis la face du cadre, y = haut ; le crochet
//  coiffe le bord du cadre et descend de 15 mm côté sable
// ------------------------------------------------------------
hs = hors_sol;
Lr = 2 + (hs + 2.5)/tan(pente);
module profil_rampe() {
    polygon([[Lr, 0], [Lr, 1.5], [2, hs + 4], [-e - 4.5, hs + 4], [-e - 4.5, hs - 15], [-e - 0.5, hs - 15],
             [-e - 0.5, hs + 0.5], [0.5, hs + 0.5], [0.5, 0]]);
    // nervures rondes en travers, tous les 14 mm
    for (s = [10 : 14 : Lr - 14]) {
        x = Lr - s*cos(pente); y = 1.5 + s*sin(pente);
        translate([x, y] + 0.9*[sin(pente), cos(pente)]) circle(r = 2.5, $fn = 24);
    }
}
module rampe() { linear_extrude(larg_r) profil_rampe(); }

// ------------------------------------------------------------
module assemblage() {
    color("SlateGray") for (a = [0 : 90 : 270]) rotate(a) coin();
    color("DimGray") for (a = [0 : 90 : 270]) rotate(a) translate([0, yb, 0.5]) linear_extrude(H - 1) papillon2d(cl_col, cl_bout, cl_l);
    // couvercle : deux quarts posés, deux levés
    for (a = [0 : 90 : 270]) rotate(a) translate([0, 0, H + (a >= 180 ? 90 : 0)]) {
        color("LightSlateGray") couvercle_pose();
        color("Khaki") translate([Tq + 11, (oreille[0][0] + oreille[0][1])/2 - et_l/2 + 0.5, -10]) cube([1.5, 20, 60]);
    }
    // piquets, à travers couvercle et pattes
    for (a = [0, 90]) rotate(a) color("DimGray") translate([pc + 2.5, pc, H + tc + 14]) rotate([0, 90, 0]) piquet();
    // rampe, côté libre
    color("SlateGray") translate([-So*0.35 + larg_r/2, -So, H - hs]) rotate([0, 0, -90]) rotate([90, 0, 0]) rampe();
    %translate([0, 0, H - hs - 1]) difference() { cube([cote + 500, cote + 500, 2], center = true); cube([cote - 2*e, cote - 2*e, 4], center = true); }
}

// ------------------------------------------------------------
if      (piece == "coin")          coin();
else if (piece == "cle")           cle();
else if (piece == "couvercle")     couvercle();
else if (piece == "cle_couvercle") cle_couvercle();
else if (piece == "rampe")         rampe();
else assemblage();
