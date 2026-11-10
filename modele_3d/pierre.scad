// ============================================================
//  BROUTILLE — pierre à griffes, posée près de l'auge
//  - dalle basse aux bords arrondis : la tortue monte dessus sans
//    effort et la quitte sans tomber
//  - dessus rugueux façon ardoise : bosses de 2,5 mm au plus et
//    petites strates ; en marchant, la tortue use ses griffes, et le
//    bec quand elle broute ce qui est posé dessus
//  - aucune arête vive : le relief est un bruit lissé, le bord est
//    un quart de rond
//  - option : 2 pattes percées de 22 mm en diagonale, pour les
//    piquets de la mangeoire (broutille_piquet.stl)
//
//  Une seule pièce, à plat, sans supports, pour un plateau de 256 x 256 mm.
//  Le dessus est une surface calculée (polyèdre) : aucun bloc à la main.
//  Repère : X = longueur, Y = largeur, Z = haut.
// ============================================================

piece  = "pierre"; // [pierre, assemblage]
pattes = true;     // pattes percées pour 2 piquets

/* [Dalle] */
demi_l  = 98;     // demi-longueur : 196 mm de long
demi_w  = 82;     // demi-largeur : 164 mm de large
carre   = 4;      // forme : 2 = ovale, 4 = coussin, plus = rectangle
ep      = 11;     // épaisseur sous le relief
bord    = 3;      // hauteur du chant vertical, au ras du sol
arrondi = 9;      // largeur du quart de rond du bord

/* [Relief] */
relief  = 2.5;    // creux et bosses du dessus, en mm
strates = 3;      // marches de l'ardoise dans le relief
graine  = 7;      // change le tirage du relief

/* [Pattes et piquets] */
patte_r   = 20;
patte_h   = 8;
passage   = 22;   // même trou que les auges
patte_ang = 40;   // position des pattes autour de la dalle
patte_out = 22;   // distance du trou au bord de la dalle

/* [Maillage] */
n_ang = 320;      // points sur le tour

// ------------------------------------------------------------
//  Bruit : hachage, bruit de valeur lissé, somme de 3 octaves
// ------------------------------------------------------------
function frac(x) = x - floor(x);
function hache(i, j) = frac(sin(i*127.1 + j*311.7 + graine*74.7)*43758.5453);
function lisse(t) = t*t*(3 - 2*t);
function bruit(x, y) = let(i = floor(x), j = floor(y), u = lisse(x - i), v = lisse(y - j),
                           a = hache(i, j), b = hache(i + 1, j), c = hache(i, j + 1), d = hache(i + 1, j + 1))
    a + (b - a)*u + (c - a)*v + (a - b - c + d)*u*v;
function fbm(x, y) = (0.35*bruit(x/26, y/26) + 0.40*bruit(x/11 + 17, y/11 + 5) + 0.25*bruit(x/5 + 41, y/5 + 29));
// strates : paliers presque plats, chaque marche montée sur la moitié du palier
function strate(t) = let(q = t*strates, m = frac(q)) (floor(q) + (m < 0.5 ? 0 : lisse((m - 0.5)/0.5)))/strates;
function texture(x, y) = let(t = min(1, max(0, (fbm(x, y) - 0.3)/0.4))) relief*(0.45*t + 0.55*strate(t));

// contour : superellipse ; s = signe, |c|^(2/n)
function sp(c) = (c < 0 ? -1 : 1)*pow(abs(c), 2/carre);
function contour(t) = [demi_l*sp(cos(t)), demi_w*sp(sin(t))];

// épaisseur à la distance d du bord : chant droit puis quart de rond
function chant(d) = d >= arrondi ? ep : bord + (ep - bord)*sqrt(1 - pow(1 - d/arrondi, 2));
function fondu(d) = d >= arrondi + 8 ? 1 : d <= arrondi*0.6 ? 0 : lisse((d - arrondi*0.6)/(arrondi*0.4 + 8));

// anneaux : serrés près du bord, où le profil tourne vite
s_bord = [0, 0.003, 0.008, 0.015, 0.024, 0.035, 0.048, 0.063, 0.08];
s_list = concat(s_bord, [for (s = [0.095 : 0.015 : 0.99]) s]);
anneaux = [for (k = [len(s_list) - 1 : -1 : 0]) 1 - s_list[k]];   // du centre vers le bord
n_ann = len(anneaux);

function sommet(u, t) = let(c = contour(t), r = norm(c), p = u*c, d = (1 - u)*r)
    [p[0], p[1], chant(d) + texture(p[0], p[1])*fondu(d)];

module dalle() {
    centre = [0, 0, ep + texture(0, 0)];
    dessus = [for (i = [0 : n_ann - 1], j = [0 : n_ang - 1]) sommet(anneaux[i], j*360/n_ang)];
    dessous = [for (j = [0 : n_ang - 1]) let(c = contour(j*360/n_ang)) [c[0], c[1], 0]];
    P = concat([centre], dessus, dessous);
    function T(i, j) = 1 + i*n_ang + (j % n_ang);
    function B(j) = 1 + n_ann*n_ang + (j % n_ang);
    F = concat(
        [for (j = [0 : n_ang - 1]) [0, T(0, j + 1), T(0, j)]],
        [for (i = [0 : n_ann - 2], j = [0 : n_ang - 1], f = [0, 1])
            f == 0 ? [T(i, j), T(i, j + 1), T(i + 1, j + 1)] : [T(i, j), T(i + 1, j + 1), T(i + 1, j)]],
        [for (j = [0 : n_ang - 1]) [T(n_ann - 1, j), T(n_ann - 1, j + 1), B(j + 1), B(j)]],
        [[for (j = [0 : n_ang - 1]) B(j)]]);
    polyhedron(points = P, faces = F, convexity = 6);
}

// pattes : en diagonale, trou à patte_out mm du bord
function patte_c(t) = let(c = contour(t), u = c/norm(c)) c + patte_out*u;
angles = [patte_ang, patte_ang + 180];
module pattes_percees() {
    for (t = angles) {
        p = patte_c(t);
        q = contour(t)*0.9;
        difference() {
            hull() {
                translate([p[0], p[1], 0]) cylinder(r = patte_r, h = patte_h, $fn = 64);
                translate([q[0], q[1], 0]) cylinder(r = patte_r, h = patte_h, $fn = 64);
            }
            translate([p[0], p[1], -1]) cylinder(d = passage, h = patte_h + 2, $fn = 64);
        }
    }
}

module pierre() {
    if (pattes) {
        difference() {
            union() { dalle(); pattes_percees(); }
            // le trou traverse aussi le bord de la dalle s'il l'effleure
            for (t = angles) { p = patte_c(t); translate([p[0], p[1], -1]) cylinder(d = passage, h = ep + relief + 2, $fn = 64); }
        }
    }
    else dalle();
}

// ------------------------------------------------------------
if (piece == "pierre") pierre();
else {
    color("SlateGray") pierre();
    %translate([0, 0, -1]) cube([400, 340, 2], center = true);
}
