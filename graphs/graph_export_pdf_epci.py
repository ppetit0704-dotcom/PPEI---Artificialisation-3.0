"""
@author  : Philippe PETIT
@version : 1.0.0
@description : Module d'export PDF — Rapport intercommunal d'artificialisation (EPCI/CC).
               Génère un PDF multi-pages professionnel à l'échelle intercommunale,
               réutilisant les helpers graphiques et de mise en page du rapport commune.
"""

import io
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate, Frame, HRFlowable, Image,
    NextPageTemplate, PageBreak, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)

# ── Réutilisation des helpers du rapport commune ─────────────────
from graphs.graph_export_pdf import (
    W, H, MARGIN,
    C_DARK, C_PRIMARY, C_ACCENT, C_WARN, C_DANGER,
    C_LIGHT, C_MID, C_WHITE,
    _fha, _fm2, _fpct, _fval,
    _make_styles, _metric_table, _data_table,
    _img_from_bytes, _plotly_to_png, _HeaderFooterCanvas,
)

# ── Réutilisation de l'agrégation EPCI ───────────────────────────
from graphs.graph_epci_general import (
    agreger_epci,
    agreger_flux_annuels,
    _construire_tableau_communes,
)
from graphs.graph_epci_ratios import calculer_ratios_epci


# ─────────────────────────────────────────────────────────────────
#  UTILITAIRES LOCAUX
# ─────────────────────────────────────────────────────────────────

def _fint(v):
    if v is None: return "N/D"
    try: return f"{int(v):,}".replace(",", " ")
    except: return "N/D"


# ─────────────────────────────────────────────────────────────────
#  GRAPHIQUES PLOTLY → PNG
# ─────────────────────────────────────────────────────────────────

def _fig_flux_epci(flux: dict, width=700, height=320) -> bytes:
    cats   = ["habitat","activite","mixte","route","ferroviaire","inconnu"]
    labels = ["Habitat","Activité","Mixte","Route","Ferroviaire","Inconnu"]
    cols   = ["#3B82F6","#F59E0B","#8B5CF6","#6B7280","#EC4899","#D1D5DB"]
    annees = sorted(flux.keys())
    fig = go.Figure()
    for cat, label, col in zip(cats, labels, cols):
        fig.add_trace(go.Bar(
            name=label, x=annees,
            y=[flux[a][cat] / 10_000 for a in annees],
            marker_color=col,
        ))
    fig.update_layout(
        barmode="stack", height=height,
        title="Flux annuels agrégés CC (ha/an)",
        xaxis=dict(tickmode="linear", dtick=1, tickangle=-45),
        yaxis_title="Hectares",
        legend=dict(orientation="h", y=1.18),
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=50, r=10, t=60, b=50), font=dict(size=11),
    )
    fig.update_xaxes(gridcolor="#E5E7EB")
    fig.update_yaxes(gridcolor="#E5E7EB")
    return _plotly_to_png(fig, width, height)


def _fig_donut_epci(agg: dict, width=340, height=300) -> bytes:
    cats   = ["habitat","activite","mixte","route","ferroviaire","inconnu"]
    labels = ["Habitat","Activité","Mixte","Route","Ferroviaire","Inconnu"]
    cols   = ["#3B82F6","#F59E0B","#8B5CF6","#6B7280","#EC4899","#D1D5DB"]
    vals   = [agg["totaux"][c]["total"] / 10_000 for c in cats]
    fig = go.Figure(go.Pie(
        labels=labels, values=vals, hole=0.5,
        marker=dict(colors=cols, line=dict(color="white", width=2)),
        textinfo="label+percent",
    ))
    fig.update_layout(
        height=height, showlegend=False,
        title="Répartition par catégorie",
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=10, r=10, t=50, b=10),
    )
    return _plotly_to_png(fig, width, height)


def _fig_top10(df_communes: pd.DataFrame, width=700, height=300) -> bytes:
    top = df_communes.nlargest(10, "Conso totale")
    fig = go.Figure(go.Bar(
        x=top["Conso totale"], y=top["Commune"],
        orientation="h", marker_color="#1565C0",
        text=[f"{v:.2f} ha".replace(".", ",") for v in top["Conso totale"]],
        textposition="outside",
    ))
    fig.update_layout(
        title="Top 10 communes — Consommation totale (ha)",
        height=height, plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=130, r=60, t=50, b=30),
        yaxis=dict(autorange="reversed"),
        font=dict(size=10),
    )
    return _plotly_to_png(fig, width, height)


def _fig_jauge_epci(r: dict, width=340, height=240) -> bytes:
    pct = r["pct_enveloppe_utilisee"] or 0
    col = "#EF4444" if pct >= 100 else ("#F97316" if pct >= 70 else "#10B981")
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=pct,
        number={"suffix": " %", "font": {"size": 30}},
        gauge={
            "axis": {"range": [0, 120]},
            "bar":  {"color": col},
            "steps": [
                {"range": [0,  70], "color": "#DCFCE7"},
                {"range": [70,100], "color": "#FEF3C7"},
                {"range": [100,120],"color": "#FEE2E2"},
            ],
            "threshold": {"line": {"color": "#EF4444", "width": 4},
                          "thickness": 0.75, "value": 100},
        },
        title={"text": "Enveloppe ZAN CC utilisée", "font": {"size": 12}},
    ))
    fig.update_layout(
        height=height, paper_bgcolor="white",
        margin=dict(l=20, r=20, t=40, b=10),
    )
    return _plotly_to_png(fig, width, height)


def _fig_projection_epci(r: dict, width=680, height=260) -> bytes:
    env_ha  = r["enveloppe_zan_ha"] or 0
    cons_ha = r["consomme_zan_ha"]  or 0
    rythme  = cons_ha / 4
    annees  = list(range(2021, 2032))
    cumul   = [min(rythme * i, env_ha * 2) for i in range(len(annees))]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=annees, y=[env_ha]*len(annees),
        name="Enveloppe ZAN max",
        line=dict(color="#EF4444", dash="dash", width=2)))
    fig.add_trace(go.Scatter(x=annees, y=cumul,
        name="Projection au rythme actuel",
        line=dict(color="#F97316", width=2)))
    fig.add_trace(go.Scatter(x=[2021,2022,2023,2024],
        y=[rythme, rythme*2, rythme*3, cons_ha],
        name="Consommé réel 2021-2024",
        line=dict(color="#10B981", width=3), marker=dict(size=7)))
    fig.update_layout(
        height=height, title="Projection ZAN CC jusqu'en 2031",
        xaxis=dict(tickmode="linear", dtick=1),
        yaxis_title="Hectares cumulés",
        legend=dict(orientation="h", y=1.18, font=dict(size=10)),
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=50, r=10, t=60, b=40), font=dict(size=11),
    )
    fig.update_xaxes(gridcolor="#E5E7EB")
    fig.update_yaxes(gridcolor="#E5E7EB")
    return _plotly_to_png(fig, width, height)


def _fig_zan_communes(df_communes: pd.DataFrame, width=700, height=None) -> bytes:
    """Barres horizontales % enveloppe ZAN par commune."""
    df = df_communes.dropna(subset=["% enveloppe"]).sort_values("% enveloppe")
    if height is None:
        height = max(280, len(df) * 22)
    cols = [
        "#EF4444" if v >= 100 else "#F97316" if v >= 70 else "#10B981"
        for v in df["% enveloppe"]
    ]
    fig = go.Figure(go.Bar(
        x=df["% enveloppe"], y=df["Commune"],
        orientation="h", marker_color=cols,
        text=[f"{v:.1f} %".replace(".", ",") for v in df["% enveloppe"]],
        textposition="outside",
    ))
    fig.add_vline(x=100, line=dict(color="#EF4444", dash="dash", width=2))
    fig.update_layout(
        title="% Enveloppe ZAN utilisée par commune",
        height=height, plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=130, r=80, t=50, b=30),
        yaxis=dict(autorange="reversed"),
        font=dict(size=9),
    )
    return _plotly_to_png(fig, width, height)


# ─────────────────────────────────────────────────────────────────
#  BADGE ZAN EPCI
# ─────────────────────────────────────────────────────────────────

def _zan_badge_epci(pct, styles):
    if pct is None:
        return Paragraph("⚪ Données insuffisantes.", styles["Body"])
    if pct >= 100:
        return Paragraph(
            f"🔴  ENVELOPPE ZAN CC DÉPASSÉE — {_fpct(pct)} du quota intercommunal utilisé. "
            "Une révision urgente des PLU/PLUi est nécessaire.", styles["AlertRed"])
    if pct >= 70:
        return Paragraph(
            f"🟠  VIGILANCE ZAN CC — {_fpct(pct)} de l'enveloppe intercommunale utilisée "
            "en seulement 4 ans. Le rythme collectif doit être réduit.", styles["AlertOrange"])
    return Paragraph(
        f"🟢  SITUATION ZAN CC SATISFAISANTE — {_fpct(pct)} de l'enveloppe utilisée. "
        "La CC est en bonne trajectoire pour respecter l'objectif 2031.", styles["AlertGreen"])


# ─────────────────────────────────────────────────────────────────
#  GÉNÉRATION DU PDF EPCI
# ─────────────────────────────────────────────────────────────────

def generer_rapport_pdf_epci(communes: pd.DataFrame,
                              coeff_reduction: float = 0.5) -> bytes:
    """
    Génère le rapport PDF intercommunal complet.
    communes        : DataFrame de toutes les communes membres
    coeff_reduction : coefficient ZAN choisi par l'utilisateur
    Retourne les bytes du PDF.
    """
    # ── Données ──────────────────────────────────────────────────
    ligne0    = communes.iloc[0]
    nom_epci  = str(ligne0.get("epci24txt", "Intercommunalité"))
    siret     = str(ligne0.get("epci24", ""))
    dep       = str(ligne0.get("iddeptxt", ""))
    region    = str(ligne0.get("idregtxt", ""))
    scots     = " · ".join(communes["scot"].dropna().unique())
    nb        = len(communes)
    date_str  = datetime.now().strftime("%d/%m/%Y")

    agg       = agreger_epci(communes)
    flux      = agreger_flux_annuels(communes)
    r         = calculer_ratios_epci(agg, coeff_reduction)
    df_tab    = _construire_tableau_communes(communes, coeff_reduction)

    pct_red   = coeff_reduction * 100
    facteur   = round(1.0 - coeff_reduction, 3)
    enveloppe = agg["conso_ref_ha"] * (1.0 - coeff_reduction)
    styles    = _make_styles()
    usable    = W - 2 * MARGIN

    # ── Graphiques ───────────────────────────────────────────────
    png_flux   = _fig_flux_epci(flux,       width=700, height=300)
    png_donut  = _fig_donut_epci(agg,       width=340, height=280)
    png_top10  = _fig_top10(df_tab,         width=700, height=280)
    png_jauge  = _fig_jauge_epci(r,         width=340, height=230)
    png_proj   = _fig_projection_epci(r,    width=680, height=250)
    nb_com_zan = min(nb, 20)   # max 20 communes dans le graphique ZAN
    png_zan_com = _fig_zan_communes(
        df_tab.head(nb_com_zan),
        width=700,
        height=max(260, nb_com_zan * 22),
    )

    # ── Document ─────────────────────────────────────────────────
    buf = io.BytesIO()
    doc = BaseDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=2.2 * cm, bottomMargin=1.8 * cm,
        title="Tableau de bord artificialisation communale — Rapport intercommunal",
        author="Observatoire artificialisation", creator="Philippe PETIT",
    )

    COVER_MARGIN = 2.5 * cm
    frame_cover = Frame(COVER_MARGIN, 0, W - 2*COVER_MARGIN, H,
                        leftPadding=0, rightPadding=0,
                        topPadding=0, bottomPadding=0)
    frame_body  = Frame(MARGIN, 1.8*cm, W-2*MARGIN, H-4.0*cm,
                        leftPadding=0, rightPadding=0,
                        topPadding=0, bottomPadding=0)

    hfc = _HeaderFooterCanvas(nom_epci, siret, date_str)

    def on_cover(canvas, doc):
        canvas.setFillColor(C_DARK)
        canvas.rect(0, 0, W, H, fill=1, stroke=0)
        canvas.setFillColor(C_PRIMARY)
        canvas.rect(0, H*0.38, W, H*0.62, fill=1, stroke=0)
        canvas.setFillColor(C_ACCENT)
        canvas.rect(0, H*0.38-6, W, 6, fill=1, stroke=0)

    def on_page(canvas, doc):
        hfc.draw_header(canvas, doc)
        hfc.draw_footer(canvas, doc)

    doc.addPageTemplates([
        PageTemplate(id="Cover", frames=[frame_cover], onPage=on_cover),
        PageTemplate(id="Body",  frames=[frame_body],  onPage=on_page),
    ])

    story = []

    # ════════════════════════════════════════════════════════════
    # PAGE 1 — COUVERTURE
    # ════════════════════════════════════════════════════════════
    story.append(NextPageTemplate("Cover"))
    story.append(Spacer(1, H * 0.44))
    story.append(Paragraph("Tableau de bord artificialisation communale", styles["CoverSub"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph("Rapport intercommunal", styles["CoverSub"]))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(nom_epci, styles["CoverTitle"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(f"{dep}  —  {region}", styles["CoverSub"]))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(f"SIRET : {siret}  |  {nb} communes membres", styles["CoverInfo"]))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(f"SCoT(s) : {scots}", styles["CoverInfo"]))
    story.append(Spacer(1, 1.2*cm))
    story.append(Paragraph(
        f"Rapport généré le {date_str}  |  Données CEREMA 2009-2024",
        styles["CoverInfo"]))
    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # PAGE 2 — IDENTITÉ CC + MÉTRIQUES
    # ════════════════════════════════════════════════════════════
    story.append(NextPageTemplate("Body"))
    story.append(Paragraph("1 · Identité de l'intercommunalité", styles["SectionTitle"]))
    story.append(Spacer(1, 0.25*cm))

    # Carte identité
    id_rows = [
        ["Nom",              nom_epci],
        ["SIRET",            siret],
        ["Département",      dep],
        ["Région",           region],
        ["SCoT(s)",          scots],
        ["Communes membres", str(nb)],
        ["Surface totale",   _fha(agg["surf_ha"], 0)],
        ["Population 2015",  _fint(agg["pop15"]) + " hab."],
        ["Population 2021",  _fint(agg["pop21"]) + " hab."],
        ["Emplois 2015",     _fint(agg["emp15"])],
        ["Emplois 2021",     _fint(agg["emp21"])],
    ]
    id_t = Table(id_rows, colWidths=[usable*0.32, usable*0.68])
    id_t.setStyle(TableStyle([
        ("FONTNAME",    (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME",    (1,0), (1,-1), "Helvetica"),
        ("FONTSIZE",    (0,0), (-1,-1), 9),
        ("TEXTCOLOR",   (0,0), (0,-1), C_PRIMARY),
        ("TEXTCOLOR",   (1,0), (1,-1), C_DARK),
        ("ROWBACKGROUNDS", (0,0),(-1,-1), [colors.HexColor("#F8FAFC"), C_WHITE]),
        ("LINEBELOW",   (0,0),(-1,-1), 0.3, colors.HexColor("#E2E8F0")),
        ("TOPPADDING",  (0,0),(-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
        ("LEFTPADDING", (0,0),(-1,-1), 8),
    ]))
    story.append(id_t)
    story.append(Spacer(1, 0.4*cm))

    # Métriques agrégées
    story.append(Paragraph("Indicateurs clés agrégés", styles["SubTitle"]))
    story.append(Spacer(1, 0.2*cm))
    items_main = [
        ("Consommation totale\n2009-2024",   _fha(agg["conso_tot_ha"]),  ""),
        ("Décennie référence\n2011-2020",    _fha(agg["conso_ref_ha"]),  ""),
        ("Période ZAN\n2021-2024",           _fha(agg["conso_zan_ha"]),  ""),
        ("% territoire CC\nartificialisé",   _fpct(agg["pct_artificialise"]), ""),
    ]
    story.append(_metric_table(items_main, styles))
    story.append(Spacer(1, 0.4*cm))

    # Tableau communes membres
    story.append(Paragraph("Communes membres — synthèse ZAN", styles["SubTitle"]))
    story.append(Spacer(1, 0.15*cm))

    com_rows = []
    for _, row in df_tab.iterrows():
        pct = row["% enveloppe"]
        emoji = "🔴" if (pct or 0) >= 100 else ("🟠" if (pct or 0) >= 70 else "🟢")
        com_rows.append([
            emoji,
            row["INSEE"],
            row["Commune"],
            f"{row['Conso totale']:.2f} ha".replace(".", ","),
            f"{row['Réf. 2011-2020']:.2f} ha".replace(".", ","),
            f"{row['ZAN 2021-2024']:.2f} ha".replace(".", ","),
            f"{pct:.1f} %".replace(".", ",") if pct is not None else "N/D",
        ])

    story.append(_data_table(
        ["ZAN", "INSEE", "Commune", "Total 2009-2024",
         "Réf. 2011-2020", "ZAN 2021-2024", "% enveloppe"],
        com_rows, styles,
        col_widths=[usable*0.05, usable*0.08, usable*0.27,
                    usable*0.14, usable*0.14, usable*0.14, usable*0.14],
    ))
    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # PAGE 3 — GRAPHIQUES FLUX & RÉPARTITION
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph("2 · Évolution temporelle de la consommation CC", styles["SectionTitle"]))
    story.append(Spacer(1, 0.25*cm))
    story.append(Paragraph(
        "Les graphiques ci-dessous représentent les flux annuels agrégés de toutes les communes "
        "membres, ventilés par catégorie de destination.", styles["Body"]))
    story.append(Spacer(1, 0.3*cm))

    story.append(_img_from_bytes(png_flux, 16.0, 6.8))
    story.append(Paragraph(
        "Figure 1 — Consommation foncière annuelle agrégée CC (ha/an)", styles["Caption"]))
    story.append(Spacer(1, 0.3*cm))

    # Donut + texte
    img_donut = _img_from_bytes(png_donut, 7.5, 6.2)
    cats_lbl = ["Habitat","Activité","Mixte","Route","Ferroviaire","Inconnu"]
    cats_key = ["habitat","activite","mixte","route","ferroviaire","inconnu"]
    recap_rows = []
    for lbl, key in zip(cats_lbl, cats_key):
        tot = agg["totaux"][key]["total"] / 10_000
        ref = agg["totaux"][key]["ref"]   / 10_000
        zan = agg["totaux"][key]["zan"]   / 10_000
        pct = tot / agg["conso_tot_ha"] * 100 if agg["conso_tot_ha"] > 0 else 0
        recap_rows.append([lbl, _fha(tot), _fha(ref), _fha(zan), _fpct(pct)])
    recap_rows.append(["TOTAL",
        _fha(agg["conso_tot_ha"]), _fha(agg["conso_ref_ha"]),
        _fha(agg["conso_zan_ha"]), "100,0 %"])

    tab_recap = _data_table(
        ["Catégorie","Total 2009-2024","2011-2020 (réf.)","2021-2024 (ZAN)","Part"],
        recap_rows, styles,
        col_widths=[usable*0.22, usable*0.20, usable*0.20, usable*0.20, usable*0.18],
    )
    row_mix = Table([[img_donut, tab_recap]],
                    colWidths=[8.0*cm, usable - 8.0*cm])
    row_mix.setStyle(TableStyle([
        ("VALIGN",       (0,0),(-1,-1), "TOP"),
        ("LEFTPADDING",  (1,0),(1,0),   0.4*cm),
        ("RIGHTPADDING", (0,0),(0,0),   0),
    ]))
    story.append(row_mix)
    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # PAGE 4 — TOP 10 & ZAN PAR COMMUNE
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph("3 · Analyse par commune membre", styles["SectionTitle"]))
    story.append(Spacer(1, 0.25*cm))

    story.append(Paragraph("Top 10 communes par consommation totale", styles["SubTitle"]))
    story.append(Spacer(1, 0.15*cm))
    story.append(_img_from_bytes(png_top10, 16.0, 6.2))
    story.append(Paragraph(
        "Figure 2 — Top 10 communes membres par consommation totale (ha)", styles["Caption"]))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("Trajectoire ZAN par commune", styles["SubTitle"]))
    story.append(Spacer(1, 0.15*cm))
    zan_h = max(5.5, min(nb_com_zan * 0.48, 10.0))
    story.append(_img_from_bytes(png_zan_com, 16.0, zan_h))
    story.append(Paragraph(
        f"Figure 3 — % enveloppe ZAN 2021-2031 utilisée par commune "
        f"(coefficient −{pct_red:.1f} %, trait rouge = seuil 100 %)", styles["Caption"]))
    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # PAGE 5 — RATIOS ANALYTIQUES
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph("4 · Ratios analytiques intercommunaux", styles["SectionTitle"]))
    story.append(Spacer(1, 0.25*cm))

    story.append(Paragraph("4.1 — Foncier & Population", styles["SubTitle"]))
    story.append(Spacer(1, 0.15*cm))
    pop_items = [
        ("m2/habitant\n(total)",        _fm2(r["m2_hab_total"], 0),   ""),
        ("m2/habitant\n(2011-2020)",    _fm2(r["m2_hab_ref"],   0),   ""),
        ("Rythme 2011-2020\n(m2/hab/an)", _fm2(r["rythme_m2_hab_ref"], 1), ""),
        ("Rythme 2021-2024\n(m2/hab/an)", _fm2(r["rythme_m2_hab_zan"], 1), ""),
        ("% territoire\nartificialisé", _fpct(r["pct_artificialise"]), ""),
    ]
    story.append(_metric_table(pop_items, styles))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("4.2 — Habitat & Ménages", styles["SubTitle"]))
    story.append(Spacer(1, 0.15*cm))
    hab_items = [
        ("m2/nouveau ménage\n(2011-2020)", _fm2(r["m2_hab_par_menage"], 0), ""),
        ("ha/nouveau ménage",              _fha(r["ha_hab_par_menage"], 3),  ""),
        ("Densité résidentielle",          _fval(r["densite_resid"], "mén/ha", 1), ""),
        ("Part habitat\n/ total",          _fpct(r["part_habitat"]),          ""),
    ]
    story.append(_metric_table(hab_items, styles))

    dens = r["densite_resid"]
    if dens is not None:
        if dens >= 20:
            story.append(Paragraph(
                f"✅  Densité résidentielle CC correcte ({_fval(dens,'mén/ha',1)}) — territoire bien valorisé.",
                styles["AlertGreen"]))
        elif dens >= 10:
            story.append(Paragraph(
                f"⚠️  Densité résidentielle CC moyenne ({_fval(dens,'mén/ha',1)}) — étalement modéré.",
                styles["AlertOrange"]))
        else:
            story.append(Paragraph(
                f"🔴  Densité CC très faible ({_fval(dens,'mén/ha',1)}) — fort étalement résidentiel.",
                styles["AlertRed"]))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("4.3 — Activité économique & Emploi", styles["SubTitle"]))
    story.append(Spacer(1, 0.15*cm))
    act_items = [
        ("m2/emploi créé\n(2015-2021)", _fm2(r["m2_act_par_emploi"], 0), ""),
        ("ha/emploi créé",              _fha(r["ha_act_par_emploi"], 3),  ""),
        ("Ratio habitat/activité",       _fval(r["ratio_hab_act"], "x", 2), ""),
        ("Part activité\n/ total",       _fpct(r["part_activite"]),          ""),
    ]
    story.append(_metric_table(act_items, styles))

    if r["delta_emp"] < 0:
        story.append(Paragraph(
            f"⚠️  Perte d'emplois à l'échelle CC ({int(r['delta_emp']):+d} entre 2015 et 2021) — "
            "interpréter les ratios activité avec prudence.", styles["AlertOrange"]))
    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # PAGE 6 — ZAN INTERCOMMUNAL
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph(
        "5 · Indicateurs ZAN — Zéro Artificialisation Nette", styles["SectionTitle"]))
    story.append(Spacer(1, 0.25*cm))
    story.append(Paragraph(
        f"La loi Climat et Résilience du 22 août 2021 fixe un objectif national de réduction "
        f"de <b>50 %</b> de la consommation foncière sur 2021-2031. "
        f"Le coefficient appliqué ici est : <b>−{pct_red:.1f} % (facteur {facteur})</b>, "
        f"conformément aux prescriptions du SRADDET ou du SCoT applicable. "
        f"L'enveloppe CC = consommation 2011-2020 × <b>{facteur}</b>.",
        styles["Body"]))
    story.append(Spacer(1, 0.2*cm))

    story.append(_zan_badge_epci(r["pct_enveloppe_utilisee"], styles))
    story.append(Spacer(1, 0.25*cm))

    zan_items = [
        ("Enveloppe ZAN\n2021-2031",      _fha(r["enveloppe_zan_ha"]),      ""),
        ("Consommé\n2021-2024",           _fha(r["consomme_zan_ha"]),       ""),
        ("Solde restant\n2025-2031",      _fha(r["restant_zan_ha"]),        ""),
        ("Capacité annuelle\nrésiduelle", _fha(r["solde_zan_annuel_ha"]),   ""),
        ("Enveloppe\nutilisée",           _fpct(r["pct_enveloppe_utilisee"]),""),
    ]
    story.append(_metric_table(zan_items, styles))
    story.append(Spacer(1, 0.3*cm))

    img_jauge = _img_from_bytes(png_jauge, 7.5, 5.2)
    img_proj  = _img_from_bytes(png_proj,  9.5, 5.2)
    row_zan = Table([[img_jauge, img_proj]],
                    colWidths=[8.0*cm, usable - 8.0*cm])
    row_zan.setStyle(TableStyle([
        ("VALIGN", (0,0),(-1,-1), "MIDDLE"),
        ("LEFTPADDING",  (1,0),(1,0), 0.3*cm),
        ("RIGHTPADDING", (0,0),(0,0), 0),
    ]))
    story.append(row_zan)
    story.append(Paragraph(
        "Figure 4 — Jauge ZAN CC  ·  Figure 5 — Projection 2021-2031",
        styles["Caption"]))
    story.append(Spacer(1, 0.3*cm))

    # Tableau synthèse ZAN
    story.append(Paragraph("Tableau de synthèse ZAN intercommunal", styles["SubTitle"]))
    story.append(Spacer(1, 0.15*cm))
    ans = r["annees_avant_epuisement"]
    zan_rows = [
        ["Conso. de référence CC 2011-2020",
         _fha(r["enveloppe_zan_ha"] / (1.0 - coeff_reduction))],
        [f"Enveloppe ZAN max 2021-2031 (−{_fpct(pct_red)})", _fha(r["enveloppe_zan_ha"])],
        ["Consommé 2021-2024 (4 ans)",      _fha(r["consomme_zan_ha"])],
        ["Solde disponible 2025-2031",      _fha(r["restant_zan_ha"])],
        ["Capacité annuelle résiduelle",    _fha(r["solde_zan_annuel_ha"])],
        ["% enveloppe utilisée",            _fpct(r["pct_enveloppe_utilisee"])],
        ["Projection épuisement",
         f"~{int(2024 + ans)}" if ans < 50 else "Conforme 2031 ✓"],
    ]
    story.append(_data_table(
        ["Indicateur", "Valeur"], zan_rows, styles,
        col_widths=[usable*0.65, usable*0.35],
    ))
    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # PAGE 7 — CONCLUSION
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph("6 · Conclusion & Recommandations", styles["SectionTitle"]))
    story.append(Spacer(1, 0.25*cm))

    pct_zan = r["pct_enveloppe_utilisee"] or 0
    nb_rouge  = (df_tab["_alerte"] == "🔴").sum()
    nb_orange = (df_tab["_alerte"] == "🟠").sum()

    if pct_zan >= 100:
        conclusion = (
            f"La Communauté de communes <b>{nom_epci}</b> a dépassé son enveloppe ZAN "
            f"intercommunale ({_fpct(pct_zan)} du quota utilisé en 4 ans). "
            f"{nb_rouge} commune(s) ont individuellement dépassé leur quota. "
            "Une révision coordonnée des PLU/PLUi s'impose en urgence, avec gel immédiat "
            "de tout nouveau projet d'extension urbaine non compensé."
        )
    elif pct_zan >= 70:
        conclusion = (
            f"Avec <b>{_fpct(pct_zan)}</b> de l'enveloppe ZAN intercommunale utilisée en 4 ans, "
            f"la CC <b>{nom_epci}</b> doit réduire significativement son rythme collectif. "
            f"{nb_rouge + nb_orange} commune(s) sont en situation tendue ou dépassée. "
            "Il est recommandé d'engager une révision du PLUi intégrant des objectifs "
            "chiffrés de densification et de renouvellement urbain pour chaque commune."
        )
    else:
        conclusion = (
            f"La CC <b>{nom_epci}</b> présente une situation ZAN satisfaisante à l'échelle "
            f"intercommunale ({_fpct(pct_zan)} de l'enveloppe utilisée). "
            "Pour maintenir cette trajectoire, il convient de poursuivre les efforts "
            "collectifs de densification et de privilégier le renouvellement urbain "
            "sur toute nouvelle extension, en veillant à la solidarité entre communes membres."
        )
    story.append(Paragraph(conclusion, styles["Body"]))
    story.append(Spacer(1, 0.4*cm))

    recos = [
        "• Mettre en place un observatoire intercommunal de suivi de la consommation foncière.",
        "• Inscrire les objectifs ZAN dans le PLUi lors de la prochaine révision.",
        "• Répartir l'enveloppe ZAN entre communes en intégrant les enjeux de solidarité.",
        "• Identifier les gisements de renouvellement urbain (friches, dents creuses).",
        "• Conditionner les autorisations d'urbanisme aux objectifs ZAN communaux.",
        "• Organiser des ateliers de sensibilisation des élus à la sobriété foncière.",
    ]
    for reco in recos:
        story.append(Paragraph(reco, styles["Body"]))

    story.append(Spacer(1, 0.8*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=C_MID, spaceAfter=8))
    story.append(Paragraph(
        "Rapport généré automatiquement par le <b>Tableau de bord artificialisation communale</b> — "
        f"Philippe PETIT | {date_str}", styles["Footer"]))
    story.append(Paragraph(
        "Source : CEREMA — Fichier NAF 2009-2024  |  "
        "Loi n° 2021-1104 du 22 août 2021 (Loi Climat et Résilience)",
        styles["Footer"]))

    doc.build(story)
    buf.seek(0)
    return buf.read()


# ─────────────────────────────────────────────────────────────────
#  POINT D'ENTRÉE STREAMLIT
# ─────────────────────────────────────────────────────────────────

def rendu_export_pdf_epci(communes: pd.DataFrame):
    """Appelé depuis app.py en mode EPCI dans l'onglet Export PDF."""
    if communes.empty:
        st.warning("Aucune donnée disponible pour cette CC.")
        return

    ligne0   = communes.iloc[0]
    nom_epci = str(ligne0.get("epci24txt", "Intercommunalité"))
    siret    = str(ligne0.get("epci24", ""))
    nb       = len(communes)

    # Coefficient ZAN
    TRAJECTOIRES = [
        (0.625,"62,5 %"),(0.620,"62,0 %"),(0.615,"61,5 %"),(0.610,"61,0 %"),
        (0.607,"60,7 % — SRADDET Occitanie"),(0.605,"60,5 %"),(0.600,"60,0 %"),
        (0.575,"57,5 %"),(0.550,"55,0 %"),(0.525,"52,5 %"),
        (0.500,"50,0 % — Loi Climat (défaut)"),(0.475,"47,5 %"),(0.450,"45,0 %"),
        (0.425,"42,5 %"),(0.400,"40,0 %"),(0.375,"37,5 %"),
    ]
    idx_traj       = st.session_state.get("trajectoire_select", 10)
    coeff_sel      = TRAJECTOIRES[idx_traj][0]
    label_sel      = TRAJECTOIRES[idx_traj][1]
    pct_sel        = coeff_sel * 100
    facteur        = round(1.0 - coeff_sel, 3)

    st.markdown("## 📄 Export PDF — Rapport intercommunal")
    st.markdown(
        f"Génère un rapport **multi-pages A4** pour la CC "
        f"**{nom_epci}** ({nb} communes membres), incluant :")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
- ✅ Couverture intercommunale personnalisée
- ✅ Fiche d'identité CC + métriques agrégées
- ✅ Tableau des communes membres avec alertes ZAN
- ✅ Graphiques flux annuels agrégés
        """)
    with col2:
        st.markdown("""
- ✅ Top 10 communes + trajectoire ZAN par commune
- ✅ Ratios analytiques intercommunaux
- ✅ Bilan ZAN CC — jauge + projection 2031
- ✅ Conclusion & recommandations intercommunales
        """)

    st.divider()
    st.info(
        f"📐 **Coefficient ZAN appliqué : −{pct_sel:.1f} %** ({label_sel}) — "
        f"Enveloppe CC = conso 2011-2020 × {facteur}\n\n"
        "_Modifiez-le dans l'onglet **Analyse & Tendances** si nécessaire._"
    )
    st.divider()

    if st.button("🚀 Générer le rapport PDF intercommunal",
                 type="primary", use_container_width=True):
        with st.spinner(
            f"Génération en cours pour {nb} communes… "
            "agrégation des données, rendu des graphiques, mise en page PDF…"
        ):
            try:
                pdf_bytes = generer_rapport_pdf_epci(communes, coeff_reduction=coeff_sel)
                nom_fichier = (
                    f"rapport_artificialisation_CC_{siret}_"
                    f"{datetime.now().strftime('%Y%m%d')}.pdf"
                )
                st.success(f"✅ Rapport intercommunal généré ! ({len(pdf_bytes)//1024} Ko)")
                st.download_button(
                    label="⬇️ Télécharger le rapport PDF intercommunal",
                    data=pdf_bytes,
                    file_name=nom_fichier,
                    mime="application/pdf",
                    use_container_width=True,
                )
            except Exception as e:
                st.error(f"❌ Erreur : {e}")
                raise
