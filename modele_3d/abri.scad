// ============================================================
//  BROUTILLE — abri-cachette en forme de carapace
//  - dôme ovale : jupe droite, épaule arrondie, pente à 45°, dessus plat
//    gravé des écailles en étoile de la radiata
//  - imprimé à l'envers, dessus sur le plateau : toute pente fait 45° ou plus,
//    l'entrée devient une encoche ouverte vers le haut ; aucun support
//  - 4 encoches au pied de la paroi, où se glissent 4 pattes rapportées
//    (piece = "patte", imprimées à plat), percées de 22 mm pour les
//    piquets de la mangeoire ; un piquet ne se plante pas sous le dôme,
//    une patte collée à la paroi ne s'imprime pas à l'envers sans support
//  - au-delà de 245 mm, l'abri est coupé en 4 quarts boulonnés par des
//    nervures intérieures (vis M5 x 16)
//  Repère : X = axe de l'abri, entrée en X+, Z = haut.
// ============================================================

taille = "petit";  // [petit, moyen, grand]
piece  = "abri";   // [abri, quart, patte, assemblage]
quart  = 0;        // 0 à 3 : quel quart (seulement pour les tailles en 4 quarts)

/* [Paroi] */
e       = 4;       // épaisseur
passage = 22;      // trou des pattes : piquet Broutille, sardine ou fer à béton

/* [Pattes rapportées] */
patte_h = 8;       // épaisseur de la patte, posée au sol
patte_r = 18;      // rayon autour du trou
patte_d = 18;      // du trou à la face extérieure de la paroi
enc_l   = 24;      // encoche de la paroi : largeur
enc_h   = patte_h + 1;   //                  hauteur, 1 mm au-dessus de la languette

$fn = 96;

// ------------------------------------------------------------
//  taille : longueur, largeur, hauteur, largeur et hauteur d'entrée ; carapace maximale
//  petit : juvénile jusqu'à 12 cm ; moyen : 20 cm ; grand : 30 cm
// ------------------------------------------------------------
T = taille == "grand" ? [500, 440, 220, 290, 150]
  : taille == "moyen" ? [360, 300, 160, 190, 100]
  :                     [240, 200, 110, 100,  65];
L = T[0]; W = T[1]; H = T[2]; ew = T[3]; eh = T[4];
R  = L/2;
k  = W/L;                    // écrasement en Y : les pentes ne deviennent que plus raides
z1 = 0.1*H;                  // jupe droite
rho = 0.45*H;                // rayon de l'épaule
z45 = z1 + rho*cos(45);
r45 = R - rho + rho*sin(45);
rt  = r45 - (H - z45);       // rayon du dessus plat
en_quarts = L > 245 || W > 245;
assert(rt > 10, "abri trop bas pour sa largeur");

function profil() = concat(
    [[0, -100], [R, -100], [R, z1]],
    [for (p = [88 : -2 : 46]) [R - rho + rho*sin(p), z1 + rho*cos(p)]],
    [[r45, z45], [rt, H], [0, H]]);

module dehors2d()  { polygon(profil()); }
module dedans2d()  { offset(delta = -e) dehors2d(); }
module plein()     { scale([1, k, 1]) rotate_extrude() intersection() { dehors2d(); square([R + 1, H + 1]); } }
module creux()     { scale([1, k, 1]) translate([0, 0, -0.01]) rotate_extrude() intersection() { dedans2d(); translate([0, -1]) square([R, H]); } }

// écailles gravées : 0,8 mm de profondeur, sur le dessus et sur la pente
module ecaille(r) {
    difference() { circle(r, $fn = 6); circle(r - 1.2, $fn = 6); }
    for (a = [0 : 60 : 300]) rotate(a) translate([0, -0.6]) square([r*0.7, 1.2]);
}
module gravures() {
    // dessus : une écaille centrale et six voisines, bord à bord
    intersection() {
        translate([0, 0, H - 0.8]) cylinder(r = rt - 2, h = 2);
        translate([0, 0, H - 0.8]) linear_extrude(2) {
            r = rt*0.36;
            ecaille(r);
            for (a = [30 : 60 : 330]) translate([r*sqrt(3)*cos(a), r*sqrt(3)*sin(a)]) ecaille(r);
        }
    }
    // pente et épaule : écailles marginales
    intersection() {
        rotate_extrude() intersection() { difference() { offset(delta = 1) dehors2d(); offset(delta = -0.8) dehors2d(); } square([R + 2, H + 2]); }
        difference() {
            union() for (i = [0 : 15]) rotate(i*360/16) translate([0, -0.6, z1 + 3]) cube([R + 5, 1.2, H]);
            translate([0, 0, -1]) cylinder(r = rt + 3, h = H + 2);
        }
    }
    // ligne de l'épaule
    intersection() {
        rotate_extrude() intersection() { difference() { offset(delta = 1) dehors2d(); offset(delta = -0.8) dehors2d(); } square([R + 2, H + 2]); }
        translate([0, 0, z45 - 0.6]) cylinder(r = R + 5, h = 1.2);
    }
}

// pattes rapportées : une encoche au pied de la paroi, sur sa normale ; la patte y glisse
// une languette, sa collerette bute dehors, le piquet la cloue au sol
angles_pattes = [60, 120, 240, 300];
function pt_paroi(a) = [R*cos(a), R*k*sin(a)];
function normale(a) = atan2(sin(a), k*cos(a));          // direction de la normale de l'ellipse
module encoches() {
    for (a = angles_pattes) translate(pt_paroi(a)) rotate(normale(a))
        translate([-e - 3, -enc_l/2, -1]) cube([e + 5, enc_l, enc_h + 1]);
}
// patte rapportée, en repère local : face extérieure de la paroi en x = 0, dehors en x > 0
module patte() {
    difference() {
        union() {
            hull() {
                translate([patte_d, 0, 0]) cylinder(r = patte_r, h = patte_h, $fn = 64);
                translate([0.3, -17, 0]) cube([4, 34, patte_h]);                   // collerette : bute contre la paroi
            }
            translate([-e - 6, -(enc_l - 1)/2, 0]) cube([e + 6.5, enc_l - 1, patte_h]);   // languette, 6 mm dedans
        }
        translate([patte_d, 0, -1]) cylinder(d = passage, h = patte_h + 2, $fn = 64);
    }
}

module entree() {
    a = eh*0.45;                 // hauteur de la voûte
    translate([0, -ew/2, -1]) cube([R + 60, ew, eh - a + 1]);
    translate([0, 0, eh - a]) scale([1, 1, a/(ew/2)]) rotate([0, 90, 0]) cylinder(r = ew/2, h = R + 60);
}

// nervures de jonction des quarts, sur la face intérieure, et leurs vis
module nervures() {
    intersection() {
        scale([1, k, 1]) rotate_extrude() intersection() {
            difference() { dedans2d(); offset(delta = -15) dedans2d(); }
            square([R, H]);
        }
        union() {
            translate([-R - 10, -5, 0]) cube([2*R + 20, 10, H]);
            translate([-5, -R, 0]) cube([10, 2*R, H]);
        }
    }
}
// points des vis, en (r, z), sur le profil intérieur, 8 mm sous la paroi
// le point de la pente est aux 6/10 de sa longueur : à mi-pente, celui de l'avant tombait dans la voûte de l'entrée du grand
trous_rz = [[R - e - 8, z1*0.9],
            [0.4*r45 + 0.6*rt - (e + 8)*0.707, 0.4*z45 + 0.6*H - (e + 8)*0.707],
            [rt*0.55, H - e - 8]];
module goutte_bas(h) {           // trou couché, pointe vers le bas : en haut une fois l'abri retourné
    rotate([90, 0, 0]) linear_extrude(h, center = true) hull() { circle(d = 5.4, $fn = 32); translate([0, -5.4/2*sqrt(2)]) circle(d = 0.1); }
}
module trous_vis() {
    for (p = trous_rz, s = [-1, 1]) {
        translate([s*p[0], 0, p[1]]) goutte_bas(30);                       // plan y = 0
        translate([0, s*p[0]*k, p[1]]) rotate(90) goutte_bas(30);         // plan x = 0
    }
}

module abri() {
    difference() {
        union() {
            difference() {
                union() { difference() { plein(); scale([1, k, 1]) gravures(); } }
                creux_sauf_nervures();
            }
        }
        entree();
        encoches();
        if (en_quarts) trous_vis();
    }
}
module creux_sauf_nervures() {
    if (en_quarts) difference() {
        creux();
        intersection() {
            union() {
                translate([-R - 10, -5, -1]) cube([2*R + 20, 10, H + 2]);
                translate([-5, -R, -1]) cube([10, 2*R, H + 2]);
            }
            scale([1, k, 1]) rotate_extrude() intersection() { difference() { dedans2d(); offset(delta = -15) dedans2d(); } square([R, H]); }
        }
    }
    else creux();
}

// quart n : 0 = avant gauche (x+, y+), puis dans le sens trigonométrique
module quart(n) {
    sx = (n == 0 || n == 3) ? 1 : -1;
    sy = (n < 2) ? 1 : -1;
    intersection() {
        abri();
        translate([sx > 0 ? 0 : -R - 60, sy > 0 ? 0 : -R - 60, -1]) cube([R + 60, R + 60, H + 2]);
    }
}

// ------------------------------------------------------------
if (piece == "patte") patte();
else if (piece == "abri" && !en_quarts) translate([0, 0, H]) mirror([0, 0, 1]) abri();
else if (piece == "quart" || piece == "abri") translate([0, 0, H]) mirror([0, 0, 1]) quart(quart);
else {
    color("SlateGray") if (en_quarts) for (n = [0 : 3]) translate([0, 0, 0]) quart(n); else abri();
    color("DimGray") for (a = angles_pattes) translate(pt_paroi(a)) rotate(normale(a)) patte();
    %translate([0, 0, -1]) cube([2*R + 200, 2*R*k + 200, 2], center = true);
}
