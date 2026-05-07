"""
Module d'export PDF — Rapport complet d'artificialisation par SCoT.
S'appuie sur les utilitaires du module commune (graph_export_pdf.py).
"""

import io
from datetime import datetime

import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
)

# Import des utilitaires du module COMMUNE
from graphs.graph_export_pdf import (
    W,
    H,
    MARGIN,
    M2_HA,
    _make_styles,
    _extraire_flux,
    _totaux,
    _ratios,
    _fig_flux,
    _fig_donut,
    _fig_jauge,
    _fig_projection,
    _fig_tendance,
    _metric_table,
    _data_table,
    _zan_badge,
    _img_from_bytes,
    _HeaderFooterCanvas,
    _on_cover,
    _on_page,
    _fha,
    _fm2,
    _fpct,
    _fval,
)

# Fonction d’agrégation SCoT (à adapter au bon module si besoin)
from .graph_epci_general import agreger_epci as agreger_scot


# ─────────────────────────────────────────────────────────────
#  AGRÉGATION DES FLUX SCoT
# ─────────────────────────────────────────────────────────────

def _extraire_flux_scot(scot_df: pd.DataFrame) -> dict:
    """
    Agrège les flux de toutes les communes du SCoT.
    Retourne un dict flux[année][categorie] = m²
    """
    cats = {
        "act": "activite",
        "hab": "habitat",
        "mix": "mixte",
        "rou": "route",
        "fer": "ferroviaire",
        "inc": "inconnu",
    }

    flux = {}

    for debut in range(9, 24):  # 2009 → 2023
        an_fin = debut + 1
        annee = 2000 + an_fin

        flux[annee] = {label: 0.0 for label in cats.values()}
        flux[annee]["total"] = 0.0

        for _, row in scot_df.iterrows():
            for code, label in cats.items():
                col = f"art{debut:02d}{code}{an_fin:02d}"
                raw = row.get(col, 0)
                try:
                    val = float(raw)
                except (TypeError, ValueError):
                    val = 0.0
                flux[annee][label] += val
                flux[annee]["total"] += val

    return flux


# ─────────────────────────────────────────────────────────────
#  PAGES SCoT
# ─────────────────────────────────────────────────────────────

def page_couverture_scot(ligne_scot: pd.Series, scot_df, styles):
    story = []
    story.append(NextPageTemplate("Body"))
    story.append(Spacer(1, H * 0.44))

    scot_nom = str(scot_df["scot"].iloc[0])

    story.append(Paragraph("Observatoire de l'artificialisation", styles["CoverSub"]))
    story.append(Spacer(1, 0.3 * MARGIN))

    story.append(Paragraph(scot_nom, styles["CoverTitle"]))
    story.append(Spacer(1, 0.4 * MARGIN))

    story.append(Paragraph(
        "Rapport d'artificialisation à l'échelle du SCoT",
        styles["CoverSub"]
    ))
    story.append(Spacer(1, 0.8 * MARGIN))

    story.append(Paragraph(
        f"Rapport généré le {datetime.now().strftime('%d/%m/%Y')}  |  Données CEREMA 2009–2024",
        styles["CoverInfo"]
    ))

    story.append(PageBreak())
    return story


def page_identite_scot(scot_df: pd.DataFrame, styles):
    story = []
    story.append(Paragraph("1 · Identité du SCoT", styles["SectionTitle"]))
    story.append(Spacer(1, 0.25 * MARGIN))

    scot_nom = str(scot_df["scot"].iloc[0])

    communes = sorted(scot_df["idcomtxt"].dropna().unique())
    deps      = sorted(scot_df["iddeptxt"].dropna().unique())
    regions   = sorted(scot_df["idregtxt"].dropna().unique())
    epcis     = sorted(scot_df["epci24txt"].dropna().unique())

    headers = ["Élément", "Valeur"]
    rows = [
        ["SCoT", scot_nom],
        ["Communes", ", ".join(communes)],
        ["EPCI", ", ".join(epcis)],
        ["Départements", ", ".join(deps)],
        ["Régions", ", ".join(regions)],
        ["Nombre de communes", len(communes)],
    ]

    story.append(_data_table(headers, rows, styles))
    story.append(Spacer(1, 0.5 * MARGIN))

    story.append(Paragraph(
        "Ce SCoT regroupe plusieurs communes, EPCI, départements et régions. "
        "Les informations ci‑dessus décrivent son périmètre territorial.",
        styles["Body"]
    ))

    story.append(PageBreak())
    return story


def page_synthese_scot(r, totaux, styles):
    story = []
    story.append(Paragraph("2 · Synthèse générale", styles["SectionTitle"]))
    story.append(Spacer(1, 0.25 * MARGIN))

    items = [
        ("Conso totale 2009–2024", _fha(r["conso_tot_ha"]), "ha"),
        ("Référence 2011–2020", _fha(r["conso_2011_20_ha"]), "ha"),
        ("ZAN 2021–2024", _fha(r["conso_2021_24_ha"]), "ha"),
        ("% enveloppe utilisée", _fpct(r["pct_enveloppe_utilisee"]), "%"),
    ]
    story.append(_metric_table(items, styles))
    story.append(Spacer(1, 0.4 * MARGIN))

    story.append(_zan_badge(r["pct_enveloppe_utilisee"], styles))
    story.append(PageBreak())
    return story


def page_flux_scot(flux, png_flux, styles):
    story = []
    story.append(Paragraph("3 · Flux annuels (SCoT)", styles["SectionTitle"]))
    story.append(Spacer(1, 0.25 * MARGIN))

    story.append(_img_from_bytes(png_flux, 17, 7))
    story.append(Spacer(1, 0.4 * MARGIN))

    headers = ["Année", "Habitat", "Activité", "Mixte", "Route", "Ferroviaire", "Inconnu", "Total"]
    rows = []
    for an in sorted(flux.keys()):
        f = flux[an]
        rows.append([
            an,
            _fha(f["habitat"] / M2_HA),
            _fha(f["activite"] / M2_HA),
            _fha(f["mixte"] / M2_HA),
            _fha(f["route"] / M2_HA),
            _fha(f["ferroviaire"] / M2_HA),
            _fha(f["inconnu"] / M2_HA),
            _fha(f["total"] / M2_HA),
        ])

    story.append(_data_table(headers, rows, styles))
    story.append(PageBreak())
    return story


def page_categories_scot(totaux, png_donut, styles):
    story = []
    story.append(Paragraph("4 · Répartition par catégories", styles["SectionTitle"]))
    story.append(Spacer(1, 0.25 * MARGIN))

    story.append(_img_from_bytes(png_donut, 9, 7))
    story.append(Spacer(1, 0.4 * MARGIN))

    headers = ["Catégorie", "Surface (ha)", "Part (%)"]
    rows = []
    total = totaux["2009-2024"]["total"] / M2_HA if totaux["2009-2024"]["total"] else 0

    for cat in ["habitat", "activite", "mixte", "route", "ferroviaire", "inconnu"]:
        val = totaux["2009-2024"][cat] / M2_HA
        pct = val / total * 100 if total > 0 else 0
        rows.append([cat.capitalize(), _fha(val), _fpct(pct)])

    story.append(_data_table(headers, rows, styles))
    story.append(PageBreak())
    return story


def page_ratios_scot(r, styles):
    story = []
    story.append(Paragraph("5 · Ratios A3‑C (SCoT)", styles["SectionTitle"]))
    story.append(Spacer(1, 0.25 * MARGIN))

    headers = ["Ratio", "Valeur"]
    rows = [
        ["m² / hab (total)", _fm2(r["m2_hab_total"])],
        ["m² / hab (réf.)", _fm2(r["m2_hab_ref"])],
        ["m² / hab (ZAN)", _fm2(r["m2_hab_zan"])],
        ["ha / hab", _fha(r["ha_hab_par_menage"])],
        ["m² activité / emploi", _fm2(r["m2_act_par_emploi"])],
        ["Densité résidentielle", _fval(r["densite_resid"], "ménages/ha")],
        ["Ratio habitat / activité", _fval(r["ratio_hab_act"])],
    ]

    story.append(_data_table(headers, rows, styles))
    story.append(PageBreak())
    return story


def page_analyse_tendance_scot(r, totaux, png_tendance, styles):
    story = []
    story.append(Paragraph("6 · Analyse & tendance ZAN (SCoT)", styles["SectionTitle"]))
    story.append(Spacer(1, 0.25 * MARGIN))

    ref_ha = r["conso_2011_20_ha"]
    objectif_ha = ref_ha * (1 - r["coeff_reduction"])
    deja_ha = r["consomme_zan_ha"]
    reste_ha = max(objectif_ha - deja_ha, 0)

    items = [
        ("Référence 2011–2020", _fha(ref_ha), "ha"),
        (f"Objectif 2021–2030 ({int(r['coeff_reduction']*100)} %)", _fha(objectif_ha), "ha"),
        ("Déjà consommé 2021–2024", _fha(deja_ha), "ha"),
        ("Reste disponible 2024–2030", _fha(reste_ha), "ha"),
    ]
    story.append(_metric_table(items, styles))
    story.append(Spacer(1, 0.5 * MARGIN))

    story.append(_img_from_bytes(png_tendance, 17, 7))
    story.append(Spacer(1, 0.5 * MARGIN))

    rythme_obs = deja_ha / 4 if deja_ha else 0
    rythme_cible = objectif_ha / 10

    analyse = []
    analyse.append(f"• Rythme observé : <b>{_fha(rythme_obs)}</b> / an.")
    analyse.append(f"• Rythme cible : <b>{_fha(rythme_cible)}</b> / an.")

    if rythme_obs > rythme_cible:
        analyse.append("• ⚠️ Au rythme actuel, l’objectif serait dépassé avant 2030.")
    else:
        analyse.append("• 🟢 Le rythme actuel est compatible avec l’objectif ZAN.")

    story.append(Paragraph("<br/>".join(analyse), styles["Body"]))
    story.append(PageBreak())
    return story


def page_annexes_scot(flux, totaux, r, styles):
    story = []
    story.append(Paragraph("7 · Annexes (SCoT)", styles["SectionTitle"]))
    story.append(Spacer(1, 0.25 * MARGIN))

    headers = ["Période", "Total (ha)"]
    rows = [
        ["2009–2024", _fha(totaux["2009-2024"]["total"] / M2_HA)],
        ["2011–2020", _fha(totaux["2011-2020"]["total"] / M2_HA)],
        ["2021–2024", _fha(totaux["2021-2024"]["total"] / M2_HA)],
    ]
    story.append(_data_table(headers, rows, styles))
    story.append(PageBreak())
    return story


# ─────────────────────────────────────────────────────────────
#  GÉNÉRATION DU PDF SCoT
# ─────────────────────────────────────────────────────────────

def generer_rapport_scot(scot_df: pd.DataFrame, struct, coeff_reduction: float = 0.5) -> bytes:

    # Agrégation SCoT
    ligne_scot = agreger_scot(scot_df, struct)

    # Flux agrégés depuis les communes du SCoT
    flux   = _extraire_flux_scot(scot_df)

    totaux = _totaux(flux)
    r      = _ratios(ligne_scot, flux, totaux, coeff_reduction)

    styles = _make_styles()

    png_flux     = _fig_flux(flux)
    png_donut    = _fig_donut(totaux)
    png_jauge    = _fig_jauge(r)
    png_proj     = _fig_projection(r)
    png_tendance = _fig_tendance(flux, r)

    scot_nom = str(scot_df["scot"].iloc[0])

    buf = io.BytesIO()
    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=2.0 * MARGIN, bottomMargin=1.8 * MARGIN,
        title=f"Rapport SCoT — {scot_nom}",
        author="Observatoire artificialisation",
        subject="Analyse ZAN SCoT",
        creator="Philippe PETIT",
    )

    frame_cover = Frame(0, 0, W, H)
    frame_body  = Frame(MARGIN, 1.8 * MARGIN, W - 2*MARGIN, H - 3.6*MARGIN)

    hfc = _HeaderFooterCanvas(
        nom_commune=scot_nom,
        code_insee="",  # pas de code INSEE pour un SCoT
        date_str=datetime.now().strftime("%d/%m/%Y"),
    )

    doc.addPageTemplates([
        PageTemplate(id="Cover", frames=[frame_cover], onPage=_on_cover),
        PageTemplate(id="Body",  frames=[frame_body], onPage=lambda c,d: _on_page(c,d,hfc)),
    ])

    story = []
    story += page_couverture_scot(ligne_scot, scot_df, styles)
    story += page_identite_scot(scot_df, styles)
    story += page_synthese_scot(r, totaux, styles)
    story += page_flux_scot(flux, png_flux, styles)
    story += page_categories_scot(totaux, png_donut, styles)
    story += page_ratios_scot(r, styles)
    story += page_analyse_tendance_scot(r, totaux, png_tendance, styles)
    story += page_annexes_scot(flux, totaux, r, styles)

    doc.build(story)
    return buf.getvalue()
