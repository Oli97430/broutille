"""
Test du graphique des repas et de la fiche PDF, sur un journal fabriqué.

    python tests/test_rapports.py
"""

import random
import shutil
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rapports


def journal_fabrique(fin):
    """Zoé vient 2 jours sur 3 environ, 8 à 25 min ; absente les 4 derniers jours.
    Une autre tortue et une simple proposition ne doivent pas compter."""
    rng = random.Random(3)
    lignes = []
    for k in range(40):
        jour = fin - timedelta(days=k)
        if k < 4 or (k > 4 and rng.random() < 0.35):
            continue
        for v in range(rng.choice((1, 1, 2))):
            lignes.append({"id_visite": f"{jour}_{v}", "date": jour.isoformat(), "heure": f"1{v}:2{v}:00",
                           "duree_s": str(rng.randint(8, 25) * 60), "individu": "Zoé", "id_individu": "zoe",
                           "corrige": "oui" if v else ""})
    lignes.append({"id_visite": "x1", "date": fin.isoformat(), "heure": "09:00:00", "duree_s": "900",
                   "individu": "Inconnue", "id_individu": "", "id_proposition": "zoe"})
    lignes.append({"id_visite": "x2", "date": fin.isoformat(), "heure": "10:00:00", "duree_s": "600",
                   "individu": "Léon", "id_individu": "leon"})
    return lignes


def main():
    resultats = []
    fin = date(2026, 11, 5)
    journal = journal_fabrique(fin)
    series = rapports.repas_par_jour(journal, "zoe", 30, fin)
    attendu = {}
    for l in journal:
        if l.get("id_individu") == "zoe" and date.fromisoformat(l["date"]) > fin - timedelta(days=30):
            attendu[l["date"]] = attendu.get(l["date"], 0) + float(l["duree_s"])
    calcule = {j.isoformat(): s for j, s, n in series if n}
    resultats.append(("30 jours, du plus ancien au plus récent", len(series) == 30 and series[-1][0] == fin
                      and series[0][0] == fin - timedelta(days=29), ""))
    resultats.append(("minutes par jour exactes, proposition et autre tortue ignorées", calcule == attendu,
                      f"{len(calcule)} jours"))
    r = rapports.resume(series)
    resultats.append(("absence actuelle = 4 jours", r["absence_actuelle"] == 4, str(r["absence_actuelle"])))
    resultats.append(("moyenne par jour venu", abs(r["moyenne_s"] - sum(attendu.values()) / len(attendu)) < 1e-6,
                      rapports.duree_lisible(r["moyenne_s"])))

    vide = rapports.repas_par_jour([], "zoe", 30, fin)
    img = rapports.graphique_repas(vide, "vide")
    resultats.append(("graphique sans aucune visite", img.size == (1060, 420), ""))

    d = Path(tempfile.mkdtemp(prefix="broutille_rapport_"))
    galerie = d / "individus" / "zoe"
    galerie.mkdir(parents=True)
    for i in range(4):
        Image.new("RGB", (400, 300), (90 + 30 * i, 120, 60)).save(galerie / f"vue{i}.jpg")
    Image.new("RGB", (220, 180), (150, 120, 80)).save(d / f"{journal[0]['id_visite']}_tortue.jpg")
    pdf = rapports.fiche_veterinaire(d / "fiche.pdf", d, {"nom": "Zoé", "espece": "Tortue radiée"}, "zoe",
                                     journal, fin=fin, galerie=galerie)
    contenu = pdf.read_bytes()
    pages = contenu.count(b"/Type /Page\n") + contenu.count(b"/Type /Page ") + contenu.count(b"/Type /Page>>")
    resultats.append(("PDF écrit, 2 pages", contenu.startswith(b"%PDF") and pages >= 2, f"{len(contenu) // 1024} ko"))
    pdf_vide = rapports.fiche_veterinaire(d / "vide.pdf", d, {"nom": "Léa", "espece": "?"}, "lea", [], fin=fin)
    resultats.append(("PDF d'une tortue sans visite ni photo", pdf_vide.read_bytes().startswith(b"%PDF"), ""))
    resultats.append(("nom de fichier sans caractère interdit",
                      rapports.nom_fichier_fiche({"nom": 'Zoé/"1"'}, fin) == "Fiche Zoé__1_ 2026-11-05.pdf",
                      rapports.nom_fichier_fiche({"nom": 'Zoé/"1"'}, fin)))
    # poids
    pesees = [{"date": "2025-11-01", "g": 1500.0}, {"date": "2026-10-01", "g": 1720.0},
              {"date": "2026-10-20", "g": 1700.0}, {"date": "2026-11-04", "g": 1500.0}]
    b = rapports.bilan_poids(pesees, fin)
    resultats.append(("poids : dernière pesée et écart précédent", b["dernier"]["g"] == 1500 and b["precedente"]["g"] == -200,
                      rapports.ecart_lisible(b["precedente"])))
    resultats.append(("poids : sur 30 jours, depuis la pesée d'avant le 06/10", b["mois"]["date"] == "2026-10-01"
                      and abs(b["mois"]["pct"] + 12.79) < 0.01, rapports.ecart_lisible(b["mois"])))
    resultats.append(("poids : sur un an", b["an"]["date"] == "2025-11-01" and b["an"]["g"] == 0, rapports.ecart_lisible(b["an"])))
    resultats.append(("poids : perte de 10 % signalée", b["alerte"], ""))
    resultats.append(("poids : aucune pesée", rapports.bilan_poids([], fin) is None
                      and rapports.graphique_poids([]).size == (1060, 420), ""))
    resultats.append(("poids lisible", (rapports.poids_lisible(1500), rapports.poids_lisible(420), rapports.poids_lisible(25000)) == ("1 500 g", "420 g", "25,00 kg"), ""))
    pdf_poids = rapports.fiche_veterinaire(d / "poids.pdf", d, {"nom": "Zoé", "espece": "Tortue radiée", "pesees": pesees},
                                           "zoe", journal, fin=fin, galerie=galerie)
    resultats.append(("PDF avec la courbe de poids", pdf_poids.read_bytes().startswith(b"%PDF"), ""))

    # registre : pesées enregistrées, remplacées le même jour, fusionnées
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from broutille_cam import Registre
    reg = Registre(d / "registre_essai")
    a, z = reg.creer("A", "Tortue radiée"), reg.creer("B", "Tortue radiée")
    reg.ajouter_pesee(a, "2026-11-01", 1200)
    reg.ajouter_pesee(a, "2026-11-01", 1210, "même jour")
    reg.ajouter_pesee(z, "2026-10-01", 1100)
    refus = False
    try:
        reg.ajouter_pesee(a, "2026-11-02", 0)
    except ValueError:
        refus = True
    reg.fusionner(z, a)
    relu = Registre(d / "registre_essai").pesees(a)
    resultats.append(("registre : même jour remplacé, poids nul refusé, fusion, relecture",
                      refus and [p["g"] for p in relu] == [1100.0, 1210.0], str(relu)))

    if "--garder" in sys.argv:
        print("fichiers :", d)
    else:
        shutil.rmtree(d, ignore_errors=True)

    ok = True
    for nom, reussi, detail in resultats:
        print(("OK   " if reussi else "RATÉ ") + nom, "—", detail)
        ok &= bool(reussi)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
