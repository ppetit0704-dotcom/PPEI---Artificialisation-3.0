"""
@author  : Philippe PETIT
@version : 1.0.0
@description : Module d'export PDF — Rapport complet d'artificialisation par commune.
               Génère un PDF multi-pages professionnel intégrant graphiques Plotly,
               tableaux, métriques ZAN et identité de la commune.
"""

import io
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    Image,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import KeepTogether

# ─────────────────────────────────────────────────────────────────
#  PALETTE & CONSTANTES
# ─────────────────────────────────────────────────────────────────

W, H = A4  # 595 x 842 pts

C_DARK    = colors.HexColor("#0F1C2E")
C_PRIMARY = colors.HexColor("#1565C0")
C_ACCENT  = colors.HexColor("#10B981")
C_WARN    = colors.HexColor("#F97316")
C_DANGER  = colors.HexColor("#EF4444")
C_LIGHT   = colors.HexColor("#F1F5F9")
C_MID     = colors.HexColor("#94A3B8")
C_WHITE   = colors.white
C_HAB     = colors.HexColor("#3B82F6")
C_ACT     = colors.HexColor("#F59E0B")
C_ROUTE   = colors.HexColor("#6B7280")
C_MIXTE   = colors.HexColor("#8B5CF6")

MARGIN = 1.8 * cm


# ─────────────────────────────────────────────────────────────────
#  UTILITAIRES
# ─────────────────────────────────────────────────────────────────

def _safe(val, default=0.0):
    try:
        v = float(val)
        return v if not np.isnan(v) else default
    except (TypeError, ValueError):
        return default


def _fha(v, dec=2):
    if v is None: return "N/D"
    # \u202f (espace fine insécable) non supporté par Helvetica → espace normale
    return f"{v:,.{dec}f} ha".replace(",", " ").replace(".", ",")


def _fm2(v, dec=0):
    if v is None: return "N/D"
    return f"{v:,.{dec}f} m2".replace(",", " ").replace(".", ",")


def _fpct(v, dec=1):
    if v is None: return "N/D"
    return f"{v:.{dec}f} %".replace(".", ",")


def _fval(v, unit="", dec=1):
    if v is None: return "N/D"
    return f"{v:.{dec}f} {unit}".replace(".", ",").strip()


# ─────────────────────────────────────────────────────────────────
#  CALCULS (identiques à graph_ratios.py — version autonome)
# ─────────────────────────────────────────────────────────────────

def _extraire_flux(ligne):
    cats = {"act": "activite", "hab": "habitat", "mix": "mixte",
            "rou": "route",   "fer": "ferroviaire", "inc": "inconnu"}
    flux = {}
    for debut in range(9, 24):
        an_fin = debut + 1
        annee  = 2000 + an_fin
        flux[annee] = {}
        for code, label in cats.items():
            col = f"art{debut:02d}{code}{an_fin:02d}"
            flux[annee][label] = _safe(ligne.get(col, 0))
        flux[annee]["total"] = sum(flux[annee].values())
    return flux


def _totaux(flux):
    """
    Calcule les totaux par période.
    IMPORTANT — correspondance avec load_data.py / graph_analyse.py :
      Le flux est indexé par l'année d'ARRIVÉE : art11xxx12 → flux[2012]
      - Référence (indices 3-12 de load_data) : flux[2012] … flux[2021] → range(2012, 2022)
      - ZAN      (indices 13-15 de load_data) : flux[2022] … flux[2024] → range(2022, 2025)
    """
    periodes = {
        "2009-2024": range(2010, 2025),
        "2011-2020": range(2012, 2022),   # ← corrigé (était range(2011, 2021))
        "2021-2024": range(2022, 2025),   # ← corrigé (était range(2021, 2025))
    }
    cats = ["activite", "habitat", "mixte", "route", "ferroviaire", "inconnu", "total"]
    return {
        lbl: {c: sum(flux.get(a, {}).get(c, 0) for a in ans) for c in cats}
        for lbl, ans in periodes.items()
    }


def _ratios(ligne, flux, totaux, coeff_reduction=0.5):
    """
    coeff_reduction : fraction de réduction appliquée à la décennie de référence.
    Ex : 0.5 = réduction de 50 % (loi Climat), 0.607 = SRADDET Occitanie, etc.
    L'enveloppe ZAN = conso_2011-2020 × (1 - coeff_reduction).
    """
    m2ha = 10_000
    pop15 = _safe(ligne.get("pop15", 0));  pop21 = _safe(ligne.get("pop21", 0))
    pop_moy = (pop15 + pop21) / 2 if (pop15 + pop21) > 0 else None
    men15 = _safe(ligne.get("men15", 0));  men21 = _safe(ligne.get("men21", 0))
    delta_men = men21 - men15
    emp15 = _safe(ligne.get("emp15", 0));  emp21 = _safe(ligne.get("emp21", 0))
    delta_emp = emp21 - emp15
    surf = _safe(ligne.get("surfcom2024", 0))

    ct  = totaux["2009-2024"]["total"]
    c20 = totaux["2011-2020"]["total"]
    c24 = totaux["2021-2024"]["total"]

    r = {}
    r["pop15"] = pop15; r["pop21"] = pop21
    r["men15"] = men15; r["men21"] = men21
    r["emp15"] = emp15; r["emp21"] = emp21
    r["delta_men"] = delta_men; r["delta_emp"] = delta_emp
    r["coeff_reduction"] = coeff_reduction   # ← mémorisé pour les textes du PDF

    r["m2_hab_total"]      = ct  / pop21   if pop21   > 0 else None
    r["m2_hab_ref"]        = c20 / pop_moy if pop_moy else None
    r["rythme_m2_hab_ref"] = r["m2_hab_ref"] / 10 if r["m2_hab_ref"] else None
    r["rythme_m2_hab_zan"] = (c24 / pop21) / 4    if pop21 > 0        else None

    hab_2020 = totaux["2011-2020"]["habitat"]
    r["m2_hab_par_menage"] = hab_2020 / delta_men if delta_men > 0 else None
    r["ha_hab_par_menage"] = r["m2_hab_par_menage"] / m2ha if r["m2_hab_par_menage"] else None
    r["part_habitat"]      = totaux["2009-2024"]["habitat"] / ct * 100 if ct > 0 else 0
    r["part_activite"]     = totaux["2009-2024"]["activite"] / ct * 100 if ct > 0 else 0
    r["part_route"]        = totaux["2009-2024"]["route"]    / ct * 100 if ct > 0 else 0
    ha_hab                 = totaux["2009-2024"]["habitat"] / m2ha
    r["densite_resid"]     = delta_men / ha_hab if ha_hab > 0 else None

    act = totaux["2009-2024"]["activite"]
    r["m2_act_par_emploi"] = act / delta_emp if delta_emp > 0 else None
    r["ha_act_par_emploi"] = r["m2_act_par_emploi"] / m2ha if r["m2_act_par_emploi"] else None
    r["ratio_hab_act"]     = totaux["2009-2024"]["habitat"] / act if act > 0 else None

    r["surf_com_ha"]           = surf / m2ha
    r["pct_artificialise"]     = ct  / surf * 100 if surf > 0 else None
    r["pct_artificialise_ref"] = c20 / surf * 100 if surf > 0 else None

    # ── Enveloppe ZAN : basée sur le coefficient utilisateur ──────
    env = c20 * (1.0 - coeff_reduction)   # m²  (ex: ×0.5 si −50 %, ×0.393 si −60.7 %)
    r["enveloppe_zan_ha"]       = env / m2ha
    r["consomme_zan_ha"]        = c24 / m2ha
    r["restant_zan_ha"]         = (env - c24) / m2ha
    r["pct_enveloppe_utilisee"] = c24 / env * 100 if env > 0 else None
    r["solde_zan_annuel_ha"]    = r["restant_zan_ha"] / 7 if r["restant_zan_ha"] else None

    rythme_zan = c24 / 4
    restant    = env - c24
    r["annees_avant_epuisement"] = (
        restant / rythme_zan if rythme_zan > 0 and restant > 0
        else (0 if restant <= 0 else 99)
    )
    r["score_zan"] = max(0, 100 - (r["pct_enveloppe_utilisee"] or 0))

    r["conso_tot_ha"]     = ct  / m2ha
    r["conso_2011_20_ha"] = c20 / m2ha
    r["conso_2021_24_ha"] = c24 / m2ha

    return r


# ─────────────────────────────────────────────────────────────────
#  GRAPHIQUES PLOTLY → PNG bytes
# ─────────────────────────────────────────────────────────────────

def _plotly_to_png(fig, width=700, height=320) -> bytes:
    return fig.to_image(format="png", width=width, height=height, scale=2)


def _fig_flux(flux, width=700, height=320):
    annees = sorted(flux.keys())
    cats   = ["habitat", "activite", "mixte", "route", "ferroviaire", "inconnu"]
    labels = ["Habitat", "Activité", "Mixte", "Route", "Ferroviaire", "Inconnu"]
    cols   = ["#3B82F6", "#F59E0B", "#8B5CF6", "#6B7280", "#EC4899", "#D1D5DB"]
    fig = go.Figure()
    for cat, label, col in zip(cats, labels, cols):
        fig.add_trace(go.Bar(name=label, x=annees,
                             y=[flux[a][cat] / 10_000 for a in annees],
                             marker_color=col))
    fig.update_layout(
        barmode="stack", height=height,
        title="Flux annuels de consommation foncière (ha/an)",
        xaxis=dict(tickmode="linear", dtick=1, tickangle=-45),
        yaxis_title="Hectares",
        legend=dict(orientation="h", y=1.15),
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=50, r=10, t=60, b=50),
        font=dict(size=11),
    )
    fig.update_xaxes(gridcolor="#E5E7EB"); fig.update_yaxes(gridcolor="#E5E7EB")
    return _plotly_to_png(fig, width, height)


def _fig_donut(totaux, width=340, height=300):
    cats   = ["habitat", "activite", "mixte", "route", "ferroviaire", "inconnu"]
    labels = ["Habitat", "Activité", "Mixte", "Route", "Ferroviaire", "Inconnu"]
    cols   = ["#3B82F6", "#F59E0B", "#8B5CF6", "#6B7280", "#EC4899", "#D1D5DB"]
    vals   = [totaux["2009-2024"][c] / 10_000 for c in cats]
    fig = go.Figure(go.Pie(labels=labels, values=vals, hole=0.5,
                           marker=dict(colors=cols, line=dict(color="white", width=2)),
                           textinfo="label+percent"))
    fig.update_layout(height=height, showlegend=False,
                      title="Répartition par catégorie",
                      plot_bgcolor="white", paper_bgcolor="white",
                      margin=dict(l=10, r=10, t=50, b=10))
    return _plotly_to_png(fig, width, height)


def _fig_jauge(r, width=340, height=260):
    pct = r["pct_enveloppe_utilisee"] or 0
    col = "#EF4444" if pct >= 100 else ("#F97316" if pct >= 70 else "#10B981")
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=pct,
        number={"suffix": " %", "font": {"size": 30}},
        gauge={
            "axis": {"range": [0, 120]},
            "bar": {"color": col},
            "steps": [
                {"range": [0, 70],   "color": "#DCFCE7"},
                {"range": [70, 100], "color": "#FEF3C7"},
                {"range": [100, 120],"color": "#FEE2E2"},
            ],
            "threshold": {"line": {"color": "#EF4444", "width": 4},
                          "thickness": 0.75, "value": 100},
        },
        title={"text": "Enveloppe ZAN utilisée", "font": {"size": 12}},
    ))
    fig.update_layout(height=height, paper_bgcolor="white",
                      margin=dict(l=20, r=20, t=40, b=10))
    return _plotly_to_png(fig, width, height)


def _fig_projection(r, width=680, height=280):
    env_ha  = r["enveloppe_zan_ha"] or 0
    cons_ha = r["consomme_zan_ha"]  or 0
    rythme  = cons_ha / 4
    annees  = list(range(2021, 2032))
    cumul   = [min(rythme * i, env_ha * 2) for i in range(len(annees))]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=annees, y=[env_ha] * len(annees),
                             name="Enveloppe ZAN max",
                             line=dict(color="#EF4444", dash="dash", width=2)))
    fig.add_trace(go.Scatter(x=annees, y=cumul,
                             name="Projection au rythme actuel",
                             line=dict(color="#F97316", width=2)))
    fig.add_trace(go.Scatter(x=[2021, 2022, 2023, 2024],
                             y=[rythme, rythme*2, rythme*3, cons_ha],
                             name="Consommé réel 2021-2024",
                             line=dict(color="#10B981", width=3),
                             marker=dict(size=7)))
    fig.update_layout(
        height=height, title="Projection ZAN jusqu'en 2031",
        xaxis=dict(tickmode="linear", dtick=1),
        yaxis_title="Hectares cumulés",
        legend=dict(orientation="h", y=1.18, font=dict(size=10)),
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=50, r=10, t=60, b=40),
        font=dict(size=11),
    )
    fig.update_xaxes(gridcolor="#E5E7EB"); fig.update_yaxes(gridcolor="#E5E7EB")
    return _plotly_to_png(fig, width, height)


# ─────────────────────────────────────────────────────────────────
#  STYLES REPORTLAB
# ─────────────────────────────────────────────────────────────────

def _make_styles():
    s = getSampleStyleSheet()
    def add(name, **kw):
        s.add(ParagraphStyle(name=name, **kw))

    add("CoverTitle",
        fontSize=28, leading=34, textColor=C_WHITE,
        fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=6)
    add("CoverSub",
        fontSize=15, leading=20, textColor=colors.HexColor("#93C5FD"),
        fontName="Helvetica", alignment=TA_CENTER, spaceAfter=4)
    add("CoverInfo",
        fontSize=10, leading=14, textColor=colors.HexColor("#CBD5E1"),
        fontName="Helvetica", alignment=TA_CENTER)

    add("SectionTitle",
        fontSize=13, leading=20, textColor=C_WHITE,
        fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=0,
        backColor=C_PRIMARY,
        borderPad=(6, 8, 6, 8))   # haut, droite, bas, gauche
    add("SubTitle",
        fontSize=10, leading=16, textColor=C_WHITE,
        fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=0,
        backColor=colors.HexColor("#1E3A5F"),
        borderPad=(4, 8, 4, 8))
    add("Body",
        fontSize=9, leading=13, textColor=C_DARK,
        fontName="Helvetica", spaceAfter=4)
    add("Caption",
        fontSize=8, leading=11, textColor=C_MID,
        fontName="Helvetica-Oblique", spaceAfter=6, alignment=TA_CENTER)
    add("Footer",
        fontSize=7.5, leading=10, textColor=C_MID,
        fontName="Helvetica", alignment=TA_CENTER)
    add("MetricLabel",
        fontSize=8, leading=10, textColor=C_MID,
        fontName="Helvetica", alignment=TA_CENTER)
    add("MetricValue",
        fontSize=13, leading=16, textColor=C_DARK,
        fontName="Helvetica-Bold", alignment=TA_CENTER)
    add("AlertGreen",
        fontSize=9, leading=12, textColor=colors.HexColor("#166534"),
        fontName="Helvetica", backColor=colors.HexColor("#DCFCE7"),
        borderPad=6, borderRadius=4, spaceAfter=6)
    add("AlertOrange",
        fontSize=9, leading=12, textColor=colors.HexColor("#9A3412"),
        fontName="Helvetica", backColor=colors.HexColor("#FEF3C7"),
        borderPad=6, spaceAfter=6)
    add("AlertRed",
        fontSize=9, leading=12, textColor=colors.HexColor("#7F1D1D"),
        fontName="Helvetica", backColor=colors.HexColor("#FEE2E2"),
        borderPad=6, spaceAfter=6)
    return s


# ─────────────────────────────────────────────────────────────────
#  COMPOSANTS DE PAGE
# ─────────────────────────────────────────────────────────────────

def _metric_table(items, styles):
    """
    items = list of (label, value, unit) tuples — affiche en cartes grises.
    """
    n = len(items)
    col_w = (W - 2 * MARGIN) / n

    header_row = [Paragraph(lbl, styles["MetricLabel"]) for lbl, _, _ in items]
    value_row  = [
        Paragraph(f"<b>{val}</b>", styles["MetricValue"])
        for _, val, _ in items
    ]
    unit_row   = [Paragraph(unit, styles["MetricLabel"]) for _, _, unit in items]

    data = [header_row, value_row, unit_row]
    t = Table(data, colWidths=[col_w] * n, rowHeights=[14, 22, 12])
    t.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), C_LIGHT),
        ("BACKGROUND",  (0, 1), (-1,  1), C_WHITE),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [C_LIGHT, C_WHITE, C_LIGHT]),
        ("LINEABOVE",   (0, 0), (-1,  0), 0.5, C_PRIMARY),
        ("LINEBELOW",   (0, -1), (-1, -1), 0.5, C_MID),
        ("LINEBEFORE",  (1, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0),(-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",(0, 0), (-1, -1), 6),
    ]))
    return t


def _data_table(headers, rows, styles, col_widths=None):
    """Tableau de données stylisé."""
    usable = W - 2 * MARGIN
    if col_widths is None:
        col_widths = [usable / len(headers)] * len(headers)

    header_style = ParagraphStyle("TH", fontSize=8, fontName="Helvetica-Bold",
                                  textColor=C_WHITE, alignment=TA_CENTER)
    cell_style   = ParagraphStyle("TD", fontSize=8, fontName="Helvetica",
                                  textColor=C_DARK, alignment=TA_CENTER)

    data = [[Paragraph(h, header_style) for h in headers]]
    for row in rows:
        data.append([Paragraph(str(c), cell_style) for c in row])

    t = Table(data, colWidths=col_widths, repeatRows=1)
    row_colors = [colors.HexColor("#F8FAFC"), C_WHITE]
    ts = TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), C_PRIMARY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), row_colors),
        ("LINEBELOW",   (0, 0), (-1, 0), 1, C_PRIMARY),
        ("LINEBELOW",   (0, 1), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0),(-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",(0, 0), (-1, -1), 6),
    ])
    t.setStyle(ts)
    return t


def _zan_badge(pct, styles):
    if pct is None:
        return Paragraph("⚪ Données insuffisantes.", styles["Body"])
    if pct >= 100:
        return Paragraph(
            f"🔴  ENVELOPPE ZAN DÉPASSÉE — {_fpct(pct)} du quota utilisé. "
            "Une révision urgente de la stratégie foncière est nécessaire.", styles["AlertRed"])
    if pct >= 70:
        return Paragraph(
            f"🟠  VIGILANCE ZAN — {_fpct(pct)} de l'enveloppe utilisée en 4 ans seulement. "
            "Le rythme actuel doit impérativement être réduit.", styles["AlertOrange"])
    return Paragraph(
        f"🟢  SITUATION ZAN SATISFAISANTE — {_fpct(pct)} de l'enveloppe utilisée. "
        "La commune est en bonne voie pour respecter l'objectif 2031.", styles["AlertGreen"])


def _img_from_bytes(data: bytes, width_cm: float, height_cm: float) -> Image:
    buf = io.BytesIO(data)
    return Image(buf, width=width_cm * cm, height=height_cm * cm)


# ─────────────────────────────────────────────────────────────────
#  PAGE TEMPLATES (header/footer)
# ─────────────────────────────────────────────────────────────────

class _HeaderFooterCanvas:
    """Mixin pour dessiner l'en-tête et le pied de page sur chaque page (sauf couverture)."""

    def __init__(self, nom_commune, code_insee, date_str):
        self.nom   = nom_commune
        self.code  = code_insee
        self.date  = date_str

    def draw_header(self, canvas, doc):
        canvas.saveState()

        # ── Dimensions ────────────────────────────────────────────
        BAND_TOP    = H - 0.2 * cm    # bord haut de la bande
        BAND_BOT    = H - 1.5 * cm    # bord bas de la bande
        BAND_H      = BAND_TOP - BAND_BOT
        TEXT_Y      = BAND_BOT + BAND_H * 0.3   # ligne de base texte (8pt)

        LOGO_W      = 1.6 * cm        # largeur réservée au logo (fixe)
        LOGO_X      = MARGIN          # coin gauche du logo
        TITLE_X     = MARGIN + LOGO_W + 0.3 * cm  # texte titre commence après logo

        # ── Fond blanc de la bande ────────────────────────────────
        canvas.setFillColor(colors.HexColor("#F8FAFC"))
        canvas.rect(0, BAND_BOT, W, BAND_H, fill=1, stroke=0)

        # ── Trait bleu bas ────────────────────────────────────────
        canvas.setFillColor(C_PRIMARY)
        canvas.rect(MARGIN, BAND_BOT, W - 2 * MARGIN, 0.06 * cm, fill=1, stroke=0)

        # ── Logo (optionnel) ──────────────────────────────────────
        candidates = [
            Path(__file__).resolve().parent.parent / "assets" / "logo.png",
            Path(__file__).resolve().parent / "assets" / "logo.png",
            Path.cwd() / "assets" / "logo.png",
        ]
        for logo_path in candidates:
            if logo_path.exists():
                try:
                    canvas.drawImage(
                        str(logo_path),
                        LOGO_X, BAND_BOT,
                        width=LOGO_W, height=BAND_H,
                        preserveAspectRatio=True,
                        mask="auto",
                    )
                    break
                except Exception:
                    pass

        # ── Titre gauche ──────────────────────────────────────────
        canvas.setFont("Helvetica-Bold", 7.5)
        canvas.setFillColor(C_PRIMARY)
        canvas.drawString(TITLE_X, TEXT_Y,
                          "Tableau de bord artificialisation communale")

        # ── Info commune droite ───────────────────────────────────
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(C_MID)
        canvas.drawRightString(W - MARGIN, TEXT_Y,
                               f"{self.code} — {self.nom}  |  {self.date}")

        canvas.restoreState()

    def draw_footer(self, canvas, doc):
        canvas.saveState()
        canvas.setFillColor(C_MID)
        canvas.rect(MARGIN, 1.1 * cm, W - 2 * MARGIN, 0.04 * cm, fill=1, stroke=0)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(C_MID)
        canvas.drawString(MARGIN, 0.75 * cm,
                          "Source : CEREMA — Données NAF 2009-2024  |  Loi Climat & Résilience 2021")
        canvas.drawRightString(W - MARGIN, 0.75 * cm, f"Page {doc.page}")
        canvas.restoreState()


# ─────────────────────────────────────────────────────────────────
#  GÉNÉRATION DU PDF
# ─────────────────────────────────────────────────────────────────

def generer_rapport_pdf(ligne: pd.Series, coeff_reduction: float = 0.5) -> bytes:
    """
    Génère le rapport PDF complet pour une commune.
    coeff_reduction : coefficient de réduction ZAN choisi par l'utilisateur
                      (ex: 0.5 = loi Climat −50 %, 0.607 = SRADDET Occitanie −60,7 %).
    Retourne les bytes du PDF.
    """
    # ── Préparation des données ────────────────────────────────
    flux   = _extraire_flux(ligne)
    totaux = _totaux(flux)
    r      = _ratios(ligne, flux, totaux, coeff_reduction)   # ← coefficient transmis

    pct_reduction   = coeff_reduction * 100          # ex : 60.7
    facteur_cible   = round(1.0 - coeff_reduction, 3)  # ex : 0.393

    nom_commune = str(ligne.get("idcomtxt", "Commune inconnue"))
    code_insee  = str(ligne.get("idcom", "-----"))
    dep         = str(ligne.get("iddeptxt", ""))
    region      = str(ligne.get("idregtxt", ""))
    epci        = str(ligne.get("epci24txt", ""))
    scot        = str(ligne.get("scot", "N/D"))
    date_str    = datetime.now().strftime("%d/%m/%Y")

    styles = _make_styles()

    # ── Génération des graphiques ──────────────────────────────
    png_flux     = _fig_flux(flux,    width=700, height=320)
    png_donut    = _fig_donut(totaux, width=340, height=280)
    png_jauge    = _fig_jauge(r,      width=340, height=240)
    png_proj     = _fig_projection(r, width=680, height=260)

    # ── Construction du document ───────────────────────────────
    buf = io.BytesIO()
    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=2.0 * cm, bottomMargin=1.8 * cm,
        title=f"Rapport artificialisation — {nom_commune}",
        author="Observatoire artificialisation",
        subject="Analyse ZAN",
        creator="Philippe PETIT",
    )

    # Frames
    frame_cover = Frame(0, 0, W, H, leftPadding=0, rightPadding=0,
                        topPadding=0, bottomPadding=0)
    frame_body  = Frame(MARGIN, 1.8 * cm, W - 2 * MARGIN, H - 3.6 * cm,
                        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)

    hfc = _HeaderFooterCanvas(nom_commune, code_insee, date_str)

    def on_cover(canvas, doc):
        # Fond dégradé simulé (rectangle sombre)
        canvas.setFillColor(C_DARK)
        canvas.rect(0, 0, W, H, fill=1, stroke=0)
        # Bande accent
        canvas.setFillColor(C_PRIMARY)
        canvas.rect(0, H * 0.38, W, H * 0.62, fill=1, stroke=0)
        # Trait accent bas
        canvas.setFillColor(C_ACCENT)
        canvas.rect(0, H * 0.38 - 6, W, 6, fill=1, stroke=0)

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
    story.append(Paragraph("Observatoire de l'artificialisation", styles["CoverSub"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(f"{code_insee} · {nom_commune}", styles["CoverTitle"]))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(f"{dep}  —  {region}", styles["CoverSub"]))
    story.append(Spacer(1, 0.6 * cm))
    story.append(Paragraph(
        f"EPCI : {epci}  |  SCoT : {scot}", styles["CoverInfo"]))
    story.append(Spacer(1, 1.5 * cm))
    story.append(Paragraph(
        f"Rapport généré le {date_str}  |  Données CEREMA 2009-2024",
        styles["CoverInfo"]))
    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # PAGE 2 — SYNTHÈSE GÉNÉRALE
    # ════════════════════════════════════════════════════════════
    story.append(NextPageTemplate("Body"))
    story.append(Paragraph("1 · Synthèse générale", styles["SectionTitle"]))
    story.append(Spacer(1, 0.25 * cm))

    # Carte d'identité
    story.append(Paragraph("Identité de la commune", styles["SubTitle"]))
    id_rows = [
        ["Commune", f"{code_insee} — {nom_commune}"],
        ["Département", dep],
        ["Région", region],
        ["EPCI", epci],
        ["SCoT", scot],
        ["Surface communale", _fha(r["surf_com_ha"], 0)],
        ["Population 2015", f"{int(r['pop15']):,}".replace(",", " ") + " hab."],
        ["Population 2021", f"{int(r['pop21']):,}".replace(",", " ") + " hab."],
    ]
    id_t = Table(id_rows,
                 colWidths=[(W - 2 * MARGIN) * 0.35, (W - 2 * MARGIN) * 0.65])
    id_t.setStyle(TableStyle([
        ("FONTNAME",    (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",    (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE",    (0, 0), (-1, -1), 9),
        ("TEXTCOLOR",   (0, 0), (0, -1), C_PRIMARY),
        ("TEXTCOLOR",   (1, 0), (1, -1), C_DARK),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1),
         [colors.HexColor("#F8FAFC"), C_WHITE]),
        ("LINEBELOW",   (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0),(-1, -1), 5),
        ("LEFTPADDING", (0, 0), (0, -1), 8),
        ("LEFTPADDING", (1, 0), (1, -1), 8),
    ]))
    story.append(id_t)
    story.append(Spacer(1, 0.5 * cm))

    # Métriques principales
    story.append(Paragraph("Indicateurs clés de consommation foncière", styles["SubTitle"]))
    items_main = [
        ("Consommation totale\n2009-2024",   _fha(r["conso_tot_ha"]),  ""),
        ("Décennie de référence\n2011-2020", _fha(r["conso_2011_20_ha"]), ""),
        ("Période ZAN\n2021-2024",           _fha(r["conso_2021_24_ha"]), ""),
        ("% territoire\nartificialisé",      _fpct(r["pct_artificialise"]), ""),
    ]
    story.append(_metric_table(items_main, styles))
    story.append(Spacer(1, 0.3 * cm))

    # Tableau récap par catégorie
    story.append(Paragraph("Détail par catégorie de destination", styles["SubTitle"]))
    cats_lbl = ["Habitat", "Activité", "Mixte", "Route", "Ferroviaire", "Inconnu"]
    cats_key = ["habitat", "activite", "mixte", "route", "ferroviaire", "inconnu"]
    m2ha = 10_000
    recap_rows = []
    for lbl, key in zip(cats_lbl, cats_key):
        tot    = totaux["2009-2024"][key] / m2ha
        ref    = totaux["2011-2020"][key] / m2ha
        zan    = totaux["2021-2024"][key] / m2ha
        pct    = (totaux["2009-2024"][key] / totaux["2009-2024"]["total"] * 100
                  if totaux["2009-2024"]["total"] > 0 else 0)
        recap_rows.append([lbl, _fha(tot), _fha(ref), _fha(zan), _fpct(pct)])

    # Ligne total
    recap_rows.append([
        "TOTAL",
        _fha(r["conso_tot_ha"]),
        _fha(r["conso_2011_20_ha"]),
        _fha(r["conso_2021_24_ha"]),
        "100,0 %",
    ])
    usable = W - 2 * MARGIN
    story.append(_data_table(
        ["Catégorie", "Total 2009-2024", "2011-2020 (réf.)", "2021-2024 (ZAN)", "Part totale"],
        recap_rows,
        styles,
        col_widths=[usable * 0.22, usable * 0.20, usable * 0.20, usable * 0.20, usable * 0.18],
    ))
    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # PAGE 3 — GRAPHIQUES DE FLUX
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph("2 · Évolution temporelle de la consommation", styles["SectionTitle"]))
    story.append(Spacer(1, 0.25 * cm))

    story.append(Paragraph(
        "Le graphique ci-dessous représente les flux annuels de consommation foncière "
        "par catégorie de destination, de 2010 à 2024.", styles["Body"]))
    story.append(Spacer(1, 0.3 * cm))

    img_flux  = _img_from_bytes(png_flux,  16.0, 7.2)
    story.append(img_flux)
    story.append(Paragraph("Figure 1 — Consommation foncière annuelle par catégorie (ha)", styles["Caption"]))
    story.append(Spacer(1, 0.4 * cm))

    # Donut + texte côte à côte
    img_donut = _img_from_bytes(png_donut, 7.5, 6.2)
    texte_donut = [
        Paragraph("Répartition par catégorie", styles["SubTitle"]),
        Spacer(1, 0.2 * cm),
        Paragraph(
            f"Sur la période 2009-2024, l'<b>habitat</b> représente "
            f"<b>{_fpct(r['part_habitat'])}</b> de la consommation totale, "
            f"l'<b>activité économique</b> <b>{_fpct(r['part_activite'])}</b> "
            f"et la <b>voirie</b> <b>{_fpct(r['part_route'])}</b>.", styles["Body"]),
        Spacer(1, 0.3 * cm),
        Paragraph(
            f"La consommation totale de <b>{_fha(r['conso_tot_ha'])}</b> "
            f"représente <b>{_fpct(r['pct_artificialise'])}</b> de la surface communale "
            f"(<b>{_fha(r['surf_com_ha'], 0)}</b>).", styles["Body"]),
    ]
    row_donut = Table(
        [[img_donut, texte_donut]],
        colWidths=[8.0 * cm, (W - 2 * MARGIN - 8.0 * cm)],
    )
    row_donut.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (1, 0), (1, 0), 0.5 * cm),
        ("RIGHTPADDING", (0, 0), (0, 0), 0),
    ]))
    story.append(row_donut)
    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # PAGE 4 — RATIOS
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph("3 · Ratios analytiques", styles["SectionTitle"]))
    story.append(Spacer(1, 0.25 * cm))

    # 3.1 — Foncier / Population
    story.append(Paragraph("3.1 — Foncier & Population", styles["SubTitle"]))
    pop_items = [
        ("m2/habitant\n(total)",       _fm2(r["m2_hab_total"], 0), ""),
        ("m2/habitant\n(2011-2020)",   _fm2(r["m2_hab_ref"],   0), ""),
        ("ha/1 000 hab\n(total)",      _fha(r["ha_par_1000hab"] if "ha_par_1000hab" in r
                                          else (r["conso_tot_ha"] / (r["pop21"] / 1000)
                                                if r["pop21"] > 0 else None), 2), ""),
        ("Rythme 2011-2020\n(m2/hab/an)", _fm2(r["rythme_m2_hab_ref"], 1), ""),
        ("Rythme 2021-2024\n(m2/hab/an)", _fm2(r["rythme_m2_hab_zan"], 1), ""),
    ]
    story.append(_metric_table(pop_items, styles))
    story.append(Spacer(1, 0.3 * cm))

    # 3.2 — Habitat & Ménages
    story.append(Paragraph("3.2 — Habitat & Ménages", styles["SubTitle"]))
    hab_items = [
        ("m2/nouveau ménage\n(2011-2020)", _fm2(r["m2_hab_par_menage"], 0), ""),
        ("ha/nouveau ménage",              _fha(r["ha_hab_par_menage"], 3), ""),
        ("Densité résidentielle",          _fval(r["densite_resid"], "mén/ha", 1), ""),
        ("Part habitat\n/ total",          _fpct(r["part_habitat"]), ""),
    ]
    story.append(_metric_table(hab_items, styles))

    dens = r["densite_resid"]
    if dens is not None:
        if dens >= 20:
            msg = f"✅  Densité résidentielle correcte ({_fval(dens, 'mén/ha', 1)}) — territoire bien valorisé."
            story.append(Paragraph(msg, styles["AlertGreen"]))
        elif dens >= 10:
            msg = f"⚠️  Densité résidentielle moyenne ({_fval(dens, 'mén/ha', 1)}) — étalement modéré."
            story.append(Paragraph(msg, styles["AlertOrange"]))
        else:
            msg = f"🔴  Densité très faible ({_fval(dens, 'mén/ha', 1)}) — fort étalement résidentiel."
            story.append(Paragraph(msg, styles["AlertRed"]))

    story.append(Spacer(1, 0.3 * cm))

    # 3.3 — Activité & Emploi
    story.append(Paragraph("3.3 — Activité économique & Emploi", styles["SubTitle"]))
    act_items = [
        ("m2/emploi créé\n(2015-2021)", _fm2(r["m2_act_par_emploi"], 0), ""),
        ("ha/emploi créé",              _fha(r["ha_act_par_emploi"], 3), ""),
        ("Ratio habitat/activité",       _fval(r["ratio_hab_act"], "x", 2), ""),
        ("Part activité\n/ total",       _fpct(r["part_activite"]), ""),
    ]
    story.append(_metric_table(act_items, styles))

    delta_emp = r["delta_emp"]
    if delta_emp < 0:
        story.append(Paragraph(
            f"⚠️  Perte d'emplois détectée ({int(delta_emp):+d} entre 2015 et 2021) — "
            "interpréter les ratios activité avec prudence.", styles["AlertOrange"]))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # PAGE 5 — ZAN
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph("4 · Indicateurs ZAN — Zéro Artificialisation Nette", styles["SectionTitle"]))
    story.append(Spacer(1, 0.25 * cm))
    story.append(Paragraph(
        f"La loi Climat et Résilience du 22 août 2021 fixe un objectif national de réduction "
        f"de <b>50 %</b> de la consommation foncière sur 2021-2031. "
        f"Le coefficient appliqué ici est celui sélectionné par l'utilisateur : "
        f"<b>−{_fpct(pct_reduction)} (facteur cible : {facteur_cible})</b>, "
        f"conformément aux prescriptions du SRADDET ou du SCoT applicable. "
        f"L'enveloppe ZAN = consommation 2011-2020 × <b>{facteur_cible}</b>. "
        f"Les indicateurs ci-dessous mesurent la trajectoire de la commune au 31/12/2024.",
        styles["Body"]))
    story.append(Spacer(1, 0.3 * cm))

    # Badge alerte
    story.append(_zan_badge(r["pct_enveloppe_utilisee"], styles))
    story.append(Spacer(1, 0.3 * cm))

    # Métriques ZAN
    zan_items = [
        ("Enveloppe ZAN\n2021-2031",     _fha(r["enveloppe_zan_ha"]),    ""),
        ("Consommé\n2021-2024",          _fha(r["consomme_zan_ha"]),     ""),
        ("Solde restant\n2025-2031",     _fha(r["restant_zan_ha"]),      ""),
        ("Capacité annuelle\nrésiduelle",_fha(r["solde_zan_annuel_ha"]), ""),
        ("Enveloppe\nutilisée",          _fpct(r["pct_enveloppe_utilisee"]), ""),
    ]
    story.append(_metric_table(zan_items, styles))
    story.append(Spacer(1, 0.4 * cm))

    # Jauge + projection côte à côte
    img_jauge = _img_from_bytes(png_jauge, 7.5, 5.4)
    img_proj  = _img_from_bytes(png_proj,  9.5, 5.4)
    row_zan = Table(
        [[img_jauge, img_proj]],
        colWidths=[8.0 * cm, W - 2 * MARGIN - 8.0 * cm],
    )
    row_zan.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (1, 0), (1, 0), 0.3 * cm),
        ("RIGHTPADDING", (0, 0), (0, 0), 0),
    ]))
    story.append(row_zan)
    story.append(Paragraph(
        "Figure 2 — Jauge d'utilisation de l'enveloppe ZAN  ·  Figure 3 — Projection 2021-2031",
        styles["Caption"]))
    story.append(Spacer(1, 0.4 * cm))

    # Tableau de synthèse ZAN
    story.append(Paragraph("Tableau de synthèse ZAN", styles["SubTitle"]))
    ans_epuisement = r["annees_avant_epuisement"] or 0
    zan_rows = [
        ["Conso. de référence 2011-2020",
         _fha(r["enveloppe_zan_ha"] / (1.0 - coeff_reduction))],
        [f"Enveloppe ZAN max 2021-2031 (−{_fpct(pct_reduction)})",
         _fha(r["enveloppe_zan_ha"])],
        ["Consommé 2021-2024 (4 ans)",             _fha(r["consomme_zan_ha"])],
        ["Solde disponible 2025-2031",             _fha(r["restant_zan_ha"])],
        ["Capacité annuelle résiduelle",           _fha(r["solde_zan_annuel_ha"])],
        ["% enveloppe utilisée",                   _fpct(r["pct_enveloppe_utilisee"])],
        ["Projection épuisement au rythme actuel",
         f"~{int(2024 + ans_epuisement)}" if ans_epuisement < 50 else "Conforme 2031"],
    ]
    story.append(_data_table(
        ["Indicateur", "Valeur"],
        zan_rows,
        styles,
        col_widths=[usable * 0.65, usable * 0.35],
    ))
    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # PAGE 6 — CONCLUSION & MENTIONS
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph("5 · Conclusion & Recommandations", styles["SectionTitle"]))
    story.append(Spacer(1, 0.25 * cm))

    pct_zan = r["pct_enveloppe_utilisee"] or 0
    if pct_zan >= 100:
        conclusion = (
            f"La commune de <b>{nom_commune}</b> a d'ores et déjà dépassé son enveloppe ZAN autorisée "
            f"pour la décennie 2021-2031 ({_fpct(pct_zan)} du quota consommé en seulement 4 ans). "
            "Une révision urgente des documents d'urbanisme (PLU, PLUi) et un gel de toute nouvelle "
            "autorisation d'artificialisation s'imposent. La commune devra justifier ce dépassement "
            "auprès des instances régionales."
        )
    elif pct_zan >= 70:
        conclusion = (
            f"Avec <b>{_fpct(pct_zan)}</b> de l'enveloppe ZAN consommée en 4 ans, la commune de "
            f"<b>{nom_commune}</b> doit réduire son rythme d'artificialisation de manière significative. "
            "Il est recommandé d'engager une révision du PLU intégrant des objectifs de densification, "
            "de renouvellement urbain et de mobilisation du foncier déjà artificialisé."
        )
    else:
        conclusion = (
            f"La commune de <b>{nom_commune}</b> présente une situation ZAN satisfaisante avec "
            f"<b>{_fpct(pct_zan)}</b> de l'enveloppe utilisée au 31/12/2024. "
            "Pour maintenir cette trajectoire favorable, il convient de poursuivre les efforts "
            "de densification résidentielle et de privilégier le renouvellement urbain "
            "sur toute nouvelle extension."
        )

    story.append(Paragraph(conclusion, styles["Body"]))
    story.append(Spacer(1, 0.5 * cm))

    # Recommandations génériques
    reco = [
        "• Suivre trimestriellement l'évolution de l'enveloppe ZAN restante.",
        "• Intégrer les objectifs ZAN dans le PLU / PLUi lors de la prochaine révision.",
        "• Privilégier les projets de renouvellement urbain et de réhabilitation.",
        "• Densifier les opérations d'habitat (objectif > 20 logements/ha).",
        "• Analyser le potentiel des dents creuses et friches avant toute extension.",
    ]
    for reco_line in reco:
        story.append(Paragraph(reco_line, styles["Body"]))

    story.append(Spacer(1, 1.0 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=C_MID, spaceAfter=8))
    story.append(Paragraph(
        "Rapport généré automatiquement par l'<b>Observatoire de l'artificialisation</b> — "
        f"Philippe PETIT | {date_str}",
        styles["Footer"]))
    story.append(Paragraph(
        "Source des données : CEREMA — Fichier NAF 2009-2024  |  "
        "Référence réglementaire : Loi n° 2021-1104 du 22 août 2021 (Loi Climat et Résilience)",
        styles["Footer"]))

    # ── Build ──────────────────────────────────────────────────
    doc.build(story)
    buf.seek(0)
    return buf.read()


# ─────────────────────────────────────────────────────────────────
#  POINT D'ENTRÉE STREAMLIT
# ─────────────────────────────────────────────────────────────────

def rendu_export_pdf(code_insee: str):
    """Appelé depuis app.py dans l'onglet Export PDF."""
    import streamlit as st

    df = st.session_state.get("df")
    if df is None:
        st.warning("Données non chargées.")
        return

    if not code_insee:
        st.info("Veuillez saisir un code INSEE dans le menu latéral.")
        return

    commune = df[df["idcom"] == code_insee]
    if commune.empty:
        st.warning("Aucune commune trouvée pour ce code INSEE.")
        return

    ligne = commune.iloc[0]
    nom   = ligne.get("idcomtxt", code_insee)

    # ── Récupération du coefficient sélectionné dans l'onglet Analyse ──
    # TRAJECTOIRES identique à graph_analyse.py
    TRAJECTOIRES = [
        (0.625, "62,5 %"), (0.620, "62,0 %"), (0.615, "61,5 %"),
        (0.610, "61,0 %"), (0.607, "60,7 % — Proposition SRADDET Occitanie"),
        (0.605, "60,5 %"), (0.600, "60,0 %"), (0.575, "57,5 %"),
        (0.550, "55,0 %"), (0.525, "52,5 %"), (0.500, "50,0 % — Loi Climat (défaut)"),
        (0.475, "47,5 %"), (0.450, "45,0 %"), (0.425, "42,5 %"),
        (0.400, "40,0 %"), (0.375, "37,5 %"),
    ]
    idx_traj      = st.session_state.get("trajectoire_select", 10)  # défaut 50 %
    coeff_sel     = TRAJECTOIRES[idx_traj][0]
    label_sel     = TRAJECTOIRES[idx_traj][1]
    pct_sel       = coeff_sel * 100
    facteur_cible = round(1.0 - coeff_sel, 3)

    st.markdown("## 📄 Export PDF — Tableau de bord artificialisation communale")
    st.markdown(
        f"Génère un rapport **multi-pages** au format A4 pour la commune "
        f"**{code_insee} — {nom}**, incluant :")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
- ✅ Page de couverture personnalisée
- ✅ Fiche d'identité de la commune
- ✅ Tableau de synthèse par catégorie
- ✅ Graphique des flux annuels
        """)
    with col2:
        st.markdown("""
- ✅ Répartition en donut par catégorie
- ✅ 5 familles de ratios analytiques
- ✅ Jauge ZAN + projection 2031
- ✅ Conclusion & recommandations
        """)

    st.divider()

    # ── Affichage du coefficient actif ───────────────────────────────
    st.info(
        f"📐 **Coefficient de réduction ZAN appliqué au rapport : −{pct_sel:.1f} %** "
        f"({label_sel}) — Enveloppe = conso 2011-2020 × {facteur_cible}\n\n"
        f"_Ce coefficient est celui sélectionné dans l'onglet **Analyse & Tendances**. "
        f"Modifiez-le dans cet onglet avant de générer si nécessaire._"
    )

    st.divider()

    if st.button("🚀 Générer le rapport PDF", type="primary", use_container_width=True):
        with st.spinner("Génération en cours… calcul des ratios, rendu des graphiques, mise en page PDF…"):
            try:
                pdf_bytes = generer_rapport_pdf(ligne, coeff_reduction=coeff_sel)
                nom_fichier = (
                    f"rapport_artificialisation_{code_insee}_"
                    f"{datetime.now().strftime('%Y%m%d')}.pdf"
                )
                st.success(f"✅ Rapport généré avec succès ! ({len(pdf_bytes) // 1024} Ko)")
                st.download_button(
                    label="⬇️ Télécharger le rapport PDF",
                    data=pdf_bytes,
                    file_name=nom_fichier,
                    mime="application/pdf",
                    use_container_width=True,
                )
            except Exception as e:
                st.error(f"❌ Erreur lors de la génération : {e}")
                raise