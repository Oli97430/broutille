// ============================================================
//  BROUTILLE — mangeoire suspendue : râtelier à légumes
//  - un panier à barreaux ronds tient la verdure au-dessus du sol :
//    les feuilles dépassent entre les barreaux, à hauteur de tête,
//    et restent propres
//  - posé sur 2 piquets de la mangeoire (broutille_piquet.stl) : chaque
//    joue coiffe la tête d'un piquet ; la hauteur se règle en plantant
//    le piquet plus ou moins profond
//  - ou sur ses propres pieds, à la hauteur voulue, avec des
//    rehausses de 40 mm qui s'empilent
//  - barreaux de 7 mm, ronds ; haut des vides en ogive : aucune arête,
//    rien en surplomb à l'impression
//  - fond en alvéoles hexagonales, comme l'écaille d'une radiata :
//    l'eau et les miettes s'en vont
//
//  Pièces (variable piece), toutes déjà orientées, sans supports :
//    ratelier, pied (x2, si pas de piquets), rehausse (x2 par cran de 40 mm)
//    assemblage : sur 2 piquets ; assemblage_pieds : sur ses pieds
//  Repère : X = longueur, Y = largeur, Z = haut.
// ============================================================

piece = "assemblage"; // [ratelier, pied, rehausse, assemblage, assemblage_pieds]

/* [Râtelier] */
long    = 250;    // longueur hors tout, joues comprises
larg    = 90;     // largeur du panier, d'axe à axe des barreaux
haut    = 110;    // hauteur du panier
barreau = 7;      // diamètre des barreaux
ecart   = 20;     // vide visé entre deux barreaux
fond    = 4;      // épaisseur du fond
ogive   = 40;     // pente du haut des vides, depuis la verticale : 45° au plus

/* [Joues] */
tete    = [16, 30, 14];   // tête du piquet : X, Y, hauteur (broutille.scad : piq_s, tete_l, tete_p)
tjeu    = 0.5;            // jeu autour de la tête
joue_e  = 5;              // paroi autour du logement

/* [Pied] */
pied_h  = 60;             // hauteur du dessus du pied (= dessous du râtelier) au-dessus du sol
socle   = [70, 130, 6];
reh_h   = 40;             // une rehausse monte le râtelier de 40 mm

/* [Vue d'ensemble] */
hauteur = 60;     // dessous du râtelier au-dessus du sol

$fn = 32;

use <broutille.scad>   // piquet(), pour la vue d'ensemble

// ------------------------------------------------------------
lg  = [tete[0] + 2*tjeu, tete[1] + 2*tjeu];   // logement de la tête, vu de dessous
jx  = lg[0] + 2*joue_e;              // joue : épaisseur en X
jy  = lg[1] + 2*joue_e;              // largeur en Y
lh  = tete[2] + 1;                   // hauteur droite du logement, avant le toit
appui = lh + tjeu/tan(40);           // la tête touche le toit à cette hauteur
xb  = long/2 - jx;                   // barreaux d'about, et face intérieure des joues
pas = (2*xb)/round(2*xb/(barreau + ecart));
nb  = round(2*xb/pas);
r   = barreau/2;
ha  = (pas/2)/tan(ogive);            // hauteur de l'ogive, d'axe en axe
z_a = haut - r - ha - 4;             // bas du bandeau
x_j = long/2 - jx/2;                 // axe des logements
y_j = jy/2 - 4;                      // barreau d'about contre la joue
na  = max(1, ceil((larg/2 - y_j)/pas - 0.05));   // vides d'un about, pas plus larges que ceux des grands côtés

assert(ogive <= 45, "ogive : 45° au plus depuis la verticale");
assert(long <= 250, "râtelier de 250 mm au plus");
assert(z_a > fond + 30, "râtelier trop bas pour ses barreaux");

// ------------------------------------------------------------
//  Râtelier : imprimé fond sur le plateau
// ------------------------------------------------------------
module alveoles2d(w, l) {
    rr = 5; a = rr*sqrt(3) + 3; dy = a*sqrt(3)/2;
    for (j = [-ceil(l/dy) : ceil(l/dy)], i = [-ceil(w/a) : ceil(w/a)]) {
        x = (i + (abs(j) % 2)/2)*a; y = j*dy;
        if (abs(x) <= w/2 - rr && abs(y) <= l/2 - rr) translate([x, y]) rotate(30) circle(rr, $fn = 6);
    }
}
// bandeau entre deux points (axes de barreaux), dessous en ogive
module bandeau(p, q) {
    d = norm(q - p); a = atan2(q[1] - p[1], q[0] - p[0]);
    translate([p[0], p[1], 0]) rotate(a) difference() {
        translate([0, -r, z_a]) cube([d, barreau, haut - r - z_a]);
        // vide en ogive : côtés à 'ogive' degrés de la verticale
        translate([0, r + 1, 0]) rotate([90, 0, 0]) linear_extrude(barreau + 2)
            polygon([[0, z_a - 1], [d, z_a - 1], [d, z_a], [d/2, z_a + (d/2)/tan(ogive)], [0, z_a]]);
    }
    // main courante ronde
    hull() { translate([p[0], p[1], haut - r]) sphere(r); translate([q[0], q[1], haut - r]) sphere(r); }
}
module ratelier() {
    yb = larg/2;
    pts_l = [for (i = [0 : nb]) -xb + i*pas];
    difference() {
        union() {
            // fond, sous les barreaux
            translate([0, 0, 0]) linear_extrude(fond) difference() {
                offset(r) square([2*xb, 2*yb], center = true);
                alveoles2d(2*xb - 10, 2*yb - 10);
            }
            // barreaux des grands côtés
            for (x = pts_l, s = [-1, 1]) translate([x, s*yb, 0]) cylinder(r = r, h = haut - r);
            for (s = [-1, 1], i = [0 : nb - 1]) bandeau([pts_l[i], s*yb], [pts_l[i + 1], s*yb]);
            // abouts : entre le barreau d'angle et la joue, des vides au même pas que les
            // grands côtés (sinon ecart ne les réduit pas : 21 mm restent 21 mm)
            for (sx = [-1, 1], sy = [-1, 1], i = [0 : na - 1]) {
                p0 = yb - i*(yb - y_j)/na; p1 = yb - (i + 1)*(yb - y_j)/na;
                bandeau([sx*xb, sy*p0], [sx*xb, sy*p1]);
                translate([sx*xb, sy*p1, 0]) cylinder(r = r, h = haut - r);   // le dernier arrondit l'angle de la joue
            }
            // joues
            for (s = [-1, 1]) translate([s*x_j, 0, 0]) linear_extrude(haut)
                offset(r = 3) square([jx - 6, jy - 6], center = true);
        }
        for (s = [-1, 1]) translate([s*x_j, 0, 0]) logement();
    }
}

// logement de la tête, ouvert dessous : droit sur lh, puis toit en croupe
// à 40° de la verticale ; la tête s'appuie par ses arêtes sur le toit
module logement() {
    hull() {
        translate([0, 0, -1]) linear_extrude(lh + 1) square(lg, center = true);
        translate([0, 0, lh + (lg[0]/2)/tan(40)]) linear_extrude(0.01) square([0.01, lg[1] - lg[0]], center = true);
    }
}

// ------------------------------------------------------------
//  Pied : socle percé pour 2 piquets, colonne de la section d'une tête
//  de piquet ; le haut de la colonne entre dans le logement de la joue
// ------------------------------------------------------------
module colonne(h) { linear_extrude(h) offset(r = 1) square([tete[0] - 2, tete[1] - 2], center = true); }
module pied() {
    difference() {
        union() {
            linear_extrude(socle[2]) offset(r = 10) square([socle[0] - 20, socle[1] - 20], center = true);
            colonne(pied_h + appui);
            // goussets à 45°, hors des trous du socle
            hg = min(40, pied_h - 10);
            for (a = [0, 180]) rotate(a) hull() {
                translate([tete[0]/2 - 1, -3, socle[2] - 0.01]) cube([1, 6, hg]);
                translate([socle[0]/2 - 4, -3, socle[2] - 0.01]) cube([1, 6, 1]);
            }
            for (a = [90, 270]) rotate(a) hull() {
                translate([tete[1]/2 - 1, -3, socle[2] - 0.01]) cube([1, 6, hg/2]);
                translate([tete[1]/2 + 3, -3, socle[2] - 0.01]) cube([1, 6, 1]);
            }
        }
        for (s = [-1, 1]) translate([0, s*45, -1]) cylinder(d = 22, h = socle[2] + 2);
    }
}
// rehausse : coiffe un pied (ou une tête de piquet), et porte une nouvelle tête
module rehausse() {
    difference() {
        linear_extrude(reh_h) offset(r = 3) square([jx - 6, jy - 6], center = true);
        logement();
    }
    translate([0, 0, reh_h - 0.01]) colonne(appui + 0.01);
}

// ------------------------------------------------------------
module piquet_plante(x, z_haut) {   // dessus de la tête en z_haut
    color("DimGray") translate([x, 0, z_haut]) rotate([0, 90, 0]) piquet();
}
if      (piece == "ratelier") ratelier();
else if (piece == "pied")     pied();
else if (piece == "rehausse") rehausse();
else if (piece == "assemblage") {
    translate([0, 0, hauteur]) color("SlateGray") ratelier();
    for (s = [-1, 1]) piquet_plante(s*x_j - tete[0]/2, hauteur + appui);
    color("ForestGreen") translate([0, 0, hauteur + fond + 30]) scale([1.5, 0.7, 0.5]) sphere(r = 60);
    %translate([0, 0, -1]) cube([500, 300, 2], center = true);
} else {
    // un pied nu d'un côté, un pied et une rehausse de l'autre : vue éclatée
    translate([0, 0, pied_h + reh_h + 30]) color("SlateGray") ratelier();
    for (s = [-1, 1]) translate([s*x_j, 0, 0]) color("DimGray") pied();
    color("LightSlateGray") translate([x_j, 0, pied_h]) rehausse();
    color("ForestGreen") translate([0, 0, pied_h + reh_h + 60 + fond]) scale([1.5, 0.7, 0.5]) sphere(r = 60);
    %translate([0, 0, -1]) cube([500, 300, 2], center = true);
}
