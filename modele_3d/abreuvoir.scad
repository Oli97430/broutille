// ============================================================
//  BROUTILLE — abreuvoir en forme de tortue, vue de dessus
//  La cuvette est la carapace, décorée du motif en étoiles de la radiata.
//  - eau peu profonde et bords en pente : une tortue boit la tête dans
//    l'eau et peut s'y noyer si elle ne ressort pas ; ici elle remonte
//    d'où qu'elle vienne
//  - nervures en relief dans la cuvette et sur la rampe : décor et
//    prise pour les griffes sur du plastique mouillé
//  - base large et basse, 2 pattes en diagonale pour les piquets de la
//    mangeoire (broutille_piquet.stl) : une sulcata ne le renverse pas
//  - fond plein, sans trou : il garde l'eau
//
//  Une seule pièce, à plat, sans supports, pour un plateau de 256 x 256 mm.
//  Impression ASA : voir GUIDE.md, § Abreuvoir.
//  Repère : X = axe de la tortue, tête en X+, Z = haut.
// ============================================================

piece = "abreuvoir"; // [abreuvoir, assemblage]

/* [Cuvette] */
h_rim     = 18;   // hauteur du bord : 14 mm d'eau au plus, sans danger même pour un juvénile
fond      = 4;    // épaisseur sous l'eau
a_base    = 108;  // demi-longueur et demi-largeur de la base : ronde comme une radiata
b_base    = 100;
a_rim     = 78;   // bord extérieur
b_rim     = 70;
a_bassin  = 72;   // ouverture de la cuvette
b_bassin  = 64;
a_plat    = 48;   // fond plat de la cuvette
b_plat    = 40;

/* [Relief] */
relief    = 1.2;  // hauteur des nervures
n_rayons  = 28;   // nervures de la rampe
n_cuvette = 16;   // nervures de la cuvette

/* [Pattes et piquets] */
patte_r = 24;
patte_h = 8;
passage = 22;     // même trou que les auges

$fn = 96;

// ------------------------------------------------------------
module ellipse(a, b) { scale([a, b]) circle(1); }
module niveau(a, b, z) { translate([0, 0, z]) linear_extrude(0.01) ellipse(a, b); }
function point(a, b, t, z) = [a*cos(t), b*sin(t), z];

// nervure en relief entre deux points d'une surface : bout arrondi, rien de coupant
module nervure(p, q, d = 2.8) {
    hull() {
        translate(p) sphere(d = d, $fn = 10);
        translate(q) sphere(d = d, $fn = 10);
    }
}

module corps() {
    hull() {
        niveau(a_base, b_base, 0);
        niveau(a_base, b_base, 1.2);
        niveau(a_rim + 1.5, b_rim + 1.5, h_rim - 1);
        niveau(a_rim, b_rim, h_rim);
    }
}

module bassin() {
    hull() {
        niveau(a_plat, b_plat, fond);
        niveau(a_plat + 8, b_plat + 8, fond + 4);
        niveau(a_bassin, b_bassin, h_rim + 0.1);
    }
}

// écaille de la dossière : hexagone et étoile à six branches, comme une radiata
module ecaille(r, l = 1.7) {
    difference() {
        circle(r, $fn = 6);
        circle(r - l, $fn = 6);
    }
    for (a = [30 : 60 : 330]) rotate(a) translate([0, -l/2 + 0.2]) square([r*0.72, l - 0.4]);
}

module motif_fond() {
    translate([0, 0, fond - 0.01]) linear_extrude(relief + 0.01)
        intersection() {
            ellipse(a_plat - 1, b_plat - 1);
            union() {
                ecaille(15);
                // nid d'abeille : voisines décalées, jamais tournées, pour que les côtés se touchent
                for (a = [30 : 60 : 330]) translate([26*cos(a), 26*sin(a)]) ecaille(15);
            }
        }
}

// tête, queue et quatre pattes : plus basses que le bord, ce sont aussi des marches
module tete() {
    intersection() {           // posée à plat : rien sous le plateau d'impression
        hull() {
            translate([a_base - 18, 0, 0]) scale([1, 1.1, 0.3]) sphere(r = 24, $fn = 48);
            translate([a_base + 2, 0, 0]) scale([0.72, 0.72, 0.42]) sphere(r = 22, $fn = 48);
        }
        translate([0, -60, 0]) cube([200, 120, 40]);
    }
}

module queue() {
    hull() {
        translate([-a_base + 6, 0, 0]) cylinder(r = 11, h = 7);
        translate([-a_base - 10, 0, 0]) cylinder(r = 2.5, h = 3);
    }
}

function pattes() = [[72, 98], [-72, -98], [72, -98], [-72, 98]];

module patte(p, percee) {
    difference() {
        hull() {
            translate([p[0], p[1], 0]) cylinder(r = patte_r, h = patte_h);
            translate([p[0]*0.8, p[1]*0.62, 0]) cylinder(r = patte_r, h = patte_h);
        }
        if (percee) translate([p[0], p[1], -1]) cylinder(d = passage, h = patte_h + 2);
    }
}

module griffes(p) {     // trois griffes sur les pattes sans piquet
    s = p[1] > 0 ? 1 : -1;
    for (i = [-1, 0, 1]) translate([p[0] + i*13, p[1] + s*(17 - abs(i)*3), patte_h - 0.2])
        scale([1, 1, 0.5]) sphere(r = 4.5, $fn = 16);
}

module abreuvoir() {
    difference() {
        union() {
            corps();
            tete();
            queue();
            for (i = [0 : 3]) patte(pattes()[i], i < 2);
            for (i = [2, 3]) griffes(pattes()[i]);
            // écailles marginales : rayons en relief sur la rampe, ils ne touchent pas l'eau
            for (i = [0 : n_rayons - 1]) {
                t = (i + 0.5)*360/n_rayons;
                // la rampe est droite : le début du rayon est à 25 % de sa hauteur
                nervure(point(a_base - 8, b_base - 8, t, 1.2 + 0.26*(h_rim - 2.2)), point(a_rim + 2.5, b_rim + 2.5, t, h_rim - 1.5));
            }
        }
        // on recreuse la cuvette après coup : les nervures ne doivent pas y déborder
        bassin();
        // yeux
        for (s = [-1, 1]) translate([a_base + 3, s*9, 8]) sphere(r = 2.6, $fn = 24);
    }
    motif_fond();
    // rayons de la cuvette : la prise pour remonter
    for (i = [0 : n_cuvette - 1]) {
        t = (i + 0.5)*360/n_cuvette;
        nervure(point(a_plat + 2, b_plat + 2, t, fond + 0.2), point(a_bassin - 1.6, b_bassin - 1.6, t, h_rim - 0.9), 2.6);
    }
}

// ------------------------------------------------------------
if (piece == "abreuvoir") abreuvoir();
else {
    color("SlateGray") abreuvoir();
    %translate([0, 0, -1]) cube([420, 340, 2], center = true);
}
