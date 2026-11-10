// ============================================================
//  BROUTILLE — rampe de marche pour juvénile
//  - franchit une bordure (planche, parpaing, bord de bac) de
//    hauteur réglable, 60 mm par défaut
//  - pente de 22° au plus : un juvénile la monte sans glisser,
//    et la descend sans basculer sur le dos
//  - nervures rondes en travers, tous les 14 mm : prise pour les
//    griffes, rien de coupant
//  - côtés bas et arrondis : la tortue ne tombe pas sur le côté,
//    et reste visible
//  - palier en haut, au niveau de la bordure ; une rampe de chaque
//    côté pour passer dans les deux sens
//  - au-delà de 236 mm, la rampe est coupée en tronçons qui
//    s'emboîtent par une queue d'aronde verticale
//
//  À plat, sans supports, pour un plateau de 256 x 256 mm.
//  Repère : X = montée (pied en X = 0), Y = largeur, Z = haut.
// ============================================================

piece   = "rampe"; // [rampe, assemblage]
troncon = 0;       // quel tronçon, si la rampe est coupée (0 = pied)

/* [Bordure] */
hauteur = 60;     // hauteur de la bordure à franchir, en mm
pente   = 22;     // angle de la montée, 25° au plus

/* [Rampe] */
larg    = 110;    // largeur de passage entre les côtés
pied    = 2;      // épaisseur au pied
palier  = 30;     // palier en haut, contre la bordure
cote_e  = 6;      // épaisseur d'un côté
cote_h  = 12;     // hauteur d'un côté au-dessus de la marche
pas     = 14;     // écart des nervures
nerv_d  = 5;      // diamètre des nervures
nerv_s  = 2;      // saillie des nervures

/* [Tronçons] */
l_max   = 236;    // longueur maximale d'un tronçon, sans la queue d'aronde
jeu     = 0.25;   // jeu de l'emboîtement, de chaque côté
qa_col  = 14;     // largeur du col de la queue d'aronde
qa_bout = 22;     // largeur du bout
qa_l    = 14;     // longueur

$fn = 48;

assert(pente <= 25, "pente trop forte : 25° au plus");
assert(hauteur > pied + 5, "bordure trop basse");

// ------------------------------------------------------------
tp   = tan(pente);
x_h  = (hauteur - pied)/tp;   // fin de la montée
L    = x_h + palier;          // longueur totale
W    = larg + 2*cote_e;       // largeur totale
n    = ceil(L/l_max);         // nombre de tronçons
coupes = [for (k = [0 : n]) k*L/n];
function z_marche(x) = x >= x_h ? hauteur : pied + x*tp;

module corps() {
    rotate([90, 0, 0]) linear_extrude(W, center = true)
        polygon([[0, 0], [L, 0], [L, hauteur], [x_h, hauteur], [0, pied]]);
}

// section d'un côté, dans le plan YZ : droit, dessus en demi-rond
module section_cote(h) {
    translate([-cote_e/2, -200]) square([cote_e, 200 + h - cote_e/2]);
    translate([0, h - cote_e/2]) circle(d = cote_e);
}
module cote(yc) {
    // montée : la section est cisaillée le long de la pente, elle reste verticale
    intersection() {
        multmatrix([[1, 0, 0, 0], [0, 1, 0, yc], [tp, 0, 1, 0], [0, 0, 0, 1]])
            rotate([90, 0, 90]) linear_extrude(x_h) section_cote(pied + cote_h);
        translate([-1, -W, 0]) cube([x_h + 2, 2*W, hauteur + cote_h + 10]);
    }
    // palier
    translate([x_h - 1, yc, 0]) rotate([90, 0, 90]) linear_extrude(palier + 1)
        intersection() { section_cote(hauteur + cote_h); translate([-W, 0]) square([2*W, hauteur + cote_h + 10]); }
}

module nervures() {
    for (x = [8 : pas : x_h - 6])
        translate([x, 0, z_marche(x) + nerv_s - nerv_d/2]) rotate([90, 0, 0])
            cylinder(d = nerv_d, h = larg + 1, center = true);
}

module rampe() {
    corps();
    for (s = [-1, 1]) cote(s*(larg/2 + cote_e/2));
    nervures();
}

// queue d'aronde : vue de dessus, le col sur la coupe, le bout dans le tronçon suivant
module aronde2d(j = 0) {
    polygon([[-1, -qa_col/2 - j], [0, -qa_col/2 - j], [qa_l + j, -qa_bout/2 - j],
             [qa_l + j, qa_bout/2 + j], [0, qa_col/2 + j], [-1, qa_col/2 + j]]);
}
function h_tenon(x) = min(35, z_marche(x) - 6 - qa_bout/2);
module tenon(x) { translate([x - 0.5, 0, 0]) linear_extrude(h_tenon(x)) translate([0.5, 0]) aronde2d(); }
// mortaise : ouverte en dessous et sur la coupe, plafond en toit à 45°, rien à ponter
module mortaise(x) {
    h = h_tenon(x) + 0.4;
    translate([x, 0, 0]) hull() {
        translate([0, 0, -1]) linear_extrude(h + 1) aronde2d(jeu);
        translate([-1, -0.05, h + qa_bout/2 + jeu]) cube([qa_l + jeu + 1, 0.1, 0.01]);
    }
}

module morceau(k) {
    x0 = coupes[k]; x1 = coupes[k + 1];
    translate([-x0, 0, 0]) difference() {
        union() {
            intersection() {
                rampe();
                translate([x0, -W, -1]) cube([x1 - x0, 2*W, hauteur + cote_h + 20]);
            }
            if (k < n - 1) tenon(x1);
        }
        if (k > 0) mortaise(x0);
    }
}

echo(str("rampe : ", round(L), " x ", W, " mm, ", n, " tronçon(s)"));

// ------------------------------------------------------------
if (piece == "rampe") morceau(min(troncon, n - 1));
else {
    for (k = [0 : n - 1]) color(k % 2 ? "SlateGray" : "LightSlateGray")
        translate([coupes[k] + k*6, 0, 0]) morceau(k);
    // la bordure, et la rampe de l'autre côté
    %translate([L + (n - 1)*6, -W, 0]) cube([50, 2*W, hauteur]);
    %translate([2*L + (n - 1)*6 + 50, 0, 0]) mirror([1, 0, 0]) rampe();
}
