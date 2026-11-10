// ============================================================
//  BROUTILLE — serre à juvéniles, en panneaux
//  - parois en panneaux droits qui glissent par le haut dans des
//    poteaux, par une queue d'aronde verticale : aucune vis
//  - modulable : la longueur se règle par le nombre de panneaux
//    (n_long), la largeur fait un panneau
//  - couvercle en alvéoles hexagonales, comme les écailles d'une
//    radiata : 12 mm d'ouverture au plus, ni bec ni patte de chat ne passe
//  - chaque couvercle reçoit une plaque de polycarbonate du commerce,
//    glissée sous 3 rails : elle garde chaleur et humidité
//  - les couvercles sont tenus par un tourniquet sur chaque poteau
//  - chaque poteau a une patte percée de 22 mm pour un piquet de la
//    mangeoire (broutille_piquet.stl)
//
//  Pièces (variable piece), toutes déjà orientées, sans supports :
//    panneau, poteau_angle, poteau_droit, couvercle, tourniquet
//    assemblage : vue d'ensemble
//  Pour n_long panneaux : 2 n_long + 2 panneaux, 4 poteaux d'angle,
//  2 (n_long - 1) poteaux droits, n_long couvercles, 2 n_long + 2 tourniquets.
//  Repère : X = longueur, Y = largeur, Z = haut ; avant de la serre en Y = 0.
// ============================================================

piece  = "assemblage"; // [panneau, poteau_angle, poteau_droit, couvercle, tourniquet, assemblage]
n_long = 2;            // nombre de panneaux sur la longueur

/* [Parois] */
P        = 250;   // pas des poteaux, d'axe à axe ; le couvercle fait P - 1
H        = 150;   // hauteur des parois
e        = 5;     // épaisseur du panneau
bourrelet = 20;   // largeur du pied et du haut du panneau
poteau   = 34;    // section carrée du poteau
qa_col   = 10;    // queue d'aronde : largeur du col
qa_bout  = 16;    // largeur du bout
qa_l     = 8;     // longueur
jeu      = 0.25;  // jeu de l'emboîtement, de chaque côté

/* [Pattes] */
passage  = 22;    // trou du piquet
patte_r  = 19;
patte_h  = 8;

/* [Couvercle] */
maille   = 12;    // ouverture d'une alvéole, de sommet à sommet : 12 au plus
barre    = 3;     // largeur des barres entre alvéoles
tf       = 4;     // épaisseur du couvercle
bande    = 14;    // cadre plein autour des alvéoles
pc       = [240, 238, 4]; // plaque de polycarbonate : largeur, profondeur (sens du glissement), épaisseur
pc_jeu   = 0.5;   // jeu autour de la plaque
levre    = 3;     // avancée de la lèvre des rails au-dessus de la plaque

/* [Tourniquet] */
vis_d    = 3.2;   // avant-trou de la vis 4 x 30
boss_r   = 7.5;   // bossage du poteau, qui centre les couvercles

$fn = 48;

use <broutille.scad>   // piquet(), pour la vue d'ensemble

// ------------------------------------------------------------
T   = P - 1;                      // côté d'un couvercle : 1 mm de jour entre deux
Lw  = P - poteau;                 // longueur de paroi entre deux poteaux
g   = pc[2] + pc_jeu;             // hauteur de la rainure
zr  = tf + g + 1.2*levre;         // dessus des rails ; la lèvre monte à 50°
ox  = (T - pc[0])/2 - pc_jeu;     // face intérieure des rails latéraux
y_b = ox + pc_jeu + pc[1] + 0.6 + 1.2;  // ergot de retenue, devant la plaque
boss_h = zr - 0.3;                // le tourniquet serre le couvercle de 0,3 mm

assert(maille <= 12, "alvéoles de 12 mm au plus");
assert(T <= 250, "couvercle de 250 mm au plus");
assert(ox >= 2, "plaque trop large pour le couvercle");
assert(ox + levre <= bande - 4, "plaque trop étroite : les rails tombent sur les alvéoles");
assert(y_b + 1.2 <= T - 1, "plaque trop profonde pour le couvercle");
assert(Lw + 2*qa_l <= 250, "panneau de 250 mm au plus");

// queue d'aronde, vue de dessus : col sur x = 0, bout en x = qa_l
module aronde2d(j = 0) {
    polygon([[-1, -qa_col/2 - j], [0, -qa_col/2 - j], [qa_l + j, -qa_bout/2 - j],
             [qa_l + j, qa_bout/2 + j], [0, qa_col/2 + j], [-1, qa_col/2 + j]]);
}

// ------------------------------------------------------------
//  Panneau : imprimé debout, tel qu'il est posé
//  pied et haut élargis à 20 mm ; le haut porte le couvercle
// ------------------------------------------------------------
module section_panneau() {
    b = bourrelet/2; c = e/2;
    polygon([[-b, 0], [b, 0], [b, 4], [c, 4 + b - c], [c, H - 6 - 1.2*(b - c)], [b, H - 6], [b, H],
             [-b, H], [-b, H - 6], [-c, H - 6 - 1.2*(b - c)], [-c, 4 + b - c], [-b, 4]]);
}
module panneau() {
    rotate([90, 0, 90]) linear_extrude(Lw) section_panneau();
    // montants d'about, qui portent les tenons
    for (x = [0, Lw - 10]) translate([x, -7, 0]) cube([10, 14, H]);
    translate([Lw, 0, 0]) linear_extrude(H) aronde2d();
    linear_extrude(H) mirror([1, 0]) aronde2d();
}

// ------------------------------------------------------------
//  Poteaux : mortaises ouvertes en haut et en bas, le panneau descend dedans
//  angles : directions des mortaises ; dir_patte, d_patte : position de la patte
// ------------------------------------------------------------
module poteau(angles, dir_patte, d_patte) {
    s = poteau/2;
    difference() {
        union() {
            translate([-s, -s, 0]) cube([poteau, poteau, H]);
            translate([0, 0, H - 0.01]) cylinder(r = boss_r, h = boss_h + 0.01);
            hull() {
                rotate(dir_patte) translate([d_patte, 0, 0]) cylinder(r = patte_r, h = patte_h);
                translate([-s, -s, 0]) cube([poteau, poteau, patte_h]);
            }
        }
        for (a = angles) rotate(a) translate([s, 0, -1]) linear_extrude(H + 2) mirror([1, 0]) aronde2d(jeu);
        rotate(dir_patte) translate([d_patte, 0, -1]) cylinder(d = passage, h = patte_h + 2);
        translate([0, 0, H + boss_h - 30]) cylinder(d = vis_d, h = 31, $fn = 16);
    }
}
module poteau_angle() { poteau([0, 90], 225, 28*sqrt(2)); }
module poteau_droit() { poteau([0, 180], 270, poteau/2 + 14); }

// ------------------------------------------------------------
//  Couvercle : imprimé à plat, alvéoles en nid d'abeille
//  rails à gauche, à droite et au fond (y = T) ; la plaque entre par
//  l'avant (y = 0) et passe un ergot de 1,2 mm qui la retient
// ------------------------------------------------------------
module alveoles2d() {
    r  = maille/2;
    a  = r*sqrt(3) + barre;       // entraxe de deux alvéoles voisines
    dy = a*sqrt(3)/2;
    m  = T/2 - bande - r;         // on ne garde que des alvéoles entières
    nx = ceil(T/a) + 1; ny = ceil(T/dy) + 1;
    for (j = [-ny : ny], i = [-nx : nx]) {
        x = (i + (abs(j) % 2)/2)*a; y = j*dy;
        if (abs(x) <= m && abs(y) <= m) translate([T/2 + x, T/2 + y]) rotate(30) circle(r, $fn = 6);
    }
}
module rail2d() {               // section d'un rail : u vers l'intérieur, z vers le haut
    polygon([[0, tf - 0.01], [ox, tf - 0.01], [ox, tf + g], [ox + levre, zr], [0, zr]]);
}
module rail_gauche() { translate([0, T, 0]) rotate([90, 0, 0]) linear_extrude(T) rail2d(); }
module couvercle() {
    difference() {
        union() {
            linear_extrude(tf) difference() { square([T, T]); alveoles2d(); }
            rail_gauche();
            translate([T, 0, 0]) mirror([1, 0, 0]) rail_gauche();
            translate([0, T, 0]) rotate(-90) rail_gauche();          // fond
            // ergot : la plaque le franchit en se cintrant un peu
            translate([ox + levre, T - y_b, tf]) rotate([0, 90, 0]) cylinder(r = 1.2, h = T - 2*(ox + levre), $fn = 16);
        }
        // encoches des coins : le bossage du poteau s'y loge
        for (x = [-0.5, T + 0.5], y = [-0.5, T + 0.5]) translate([x, y, -1]) cylinder(r = boss_r + 1, h = zr + 2);
    }
}

// tourniquet : pivote sur la vis du poteau, et serre les coins des couvercles
module tourniquet() {
    difference() {
        hull() for (s = [-1, 1]) translate([s*22, 0, 0]) cylinder(r = 8, h = 4);
        translate([0, 0, -1]) cylinder(d = 4.5, h = 6, $fn = 24);
    }
}

// ------------------------------------------------------------
module assemblage() {
    // poteaux d'angle
    color("DimGray") {
        translate([0, 0, 0])            poteau_angle();
        translate([n_long*P, 0, 0])     rotate(90)  poteau_angle();
        translate([n_long*P, P, 0])     rotate(180) poteau_angle();
        translate([0, P, 0])            rotate(270) poteau_angle();
        for (i = [1 : 1 : n_long - 1]) {
            translate([i*P, 0, 0]) poteau_droit();
            translate([i*P, P, 0]) rotate(180) poteau_droit();
        }
    }
    color("SlateGray") {
        for (i = [0 : n_long - 1], y = [0, P]) translate([i*P + poteau/2, y, 0]) panneau();
        for (x = [0, n_long*P]) translate([x, poteau/2, 0]) rotate(90) panneau();
    }
    // couvercles : le premier est levé pour montrer la plaque
    for (i = [0 : n_long - 1]) {
        dz = i == 0 ? 70 : 0;
        translate([0, 0, dz]) {
            color("LightSlateGray") translate([i*P + 0.5, P - 0.5, H]) mirror([0, 1, 0]) couvercle();
            color([0.75, 0.9, 1, 0.45]) translate([i*P + 0.5 + ox + pc_jeu, P - 0.5 - (ox + pc_jeu) - pc[1], H + tf]) cube([pc[0], pc[1], pc[2]]);
        }
    }
    color("DimGray") for (i = [1 : n_long], y = [0, P]) translate([i*P, y, H + boss_h]) rotate(45) tourniquet();
    color("DimGray") for (y = [0, P]) translate([0, y, H + boss_h]) rotate(-45) tourniquet();
    // piquets plantés dans les pattes (broutille.scad)
    for (p = concat([[-28, -28], [n_long*P + 28, -28], [n_long*P + 28, P + 28], [-28, P + 28]],
                    [for (i = [1 : 1 : n_long - 1], s = [-1, 1]) [i*P, s < 0 ? -(poteau/2 + 14) : P + poteau/2 + 14]]))
        color("DimGray") translate([p[0] + 2.5, p[1], patte_h + 14]) rotate([0, 90, 0]) piquet();
    %translate([n_long*P/2, P/2, -1]) cube([n_long*P + 300, P + 300, 2], center = true);
}

// ------------------------------------------------------------
if      (piece == "panneau")      translate([qa_l, 0, 0]) panneau();
else if (piece == "poteau_angle") poteau_angle();
else if (piece == "poteau_droit") poteau_droit();
else if (piece == "couvercle")    couvercle();
else if (piece == "tourniquet")   tourniquet();
else assemblage();
