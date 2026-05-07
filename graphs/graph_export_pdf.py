"""
@author  : Philippe PETIT
@version : 2.0.0
@description : Module d'export PDF — Rapport complet d'artificialisation par commune.
               Version restructurée : pages modulaires, grammaire CEREMA respectée,
               logo assets/logo.png, graphiques Plotly, tableaux, métriques ZAN.
"""

import io
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

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

MARGIN = 1.8 * cm
M2_HA = 10_000.0


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
    if v is None:
        return "N/D"
    return f"{v:,.{dec}f} ha".replace(",", " ").replace(".", ",")


def _fm2(v, dec=1):
    if v is None:
        return "N/D"
    return f"{v:,.{dec}f} m²".replace(",", " ").replace(".", ",")


def _fpct(v, dec=1):
    if v is None:
        return "N/D"
    return f"{v:.{dec}f} %".replace(".", ",")


def _fval(v, unit="", dec=1):
    if v is None:
        return "N/D"
    return f"{v:.{dec}f} {unit}".replace(".", ",").strip()


def _safe_to_int(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def _safe_to_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# ─────────────────────────────────────────────────────────────────
#  CALCULS (grammaire CEREMA)
# ─────────────────────────────────────────────────────────────────

def _extraire_flux(ligne: pd.Series) -> dict:
    """
    Flux indexés par année d'arrivée (art11xxx12 → flux[2012]).
    Catégories CEREMA : habitat, activité, mixte, route, ferroviaire, inconnu.
    """
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


def _totaux(flux: dict) -> dict:
    """
    Totaux par période, alignés sur la grammaire CEREMA.
    - 2009-2024 : flux[2010..2024]
    - 2011-2020 : flux[2012..2021]
    - 2021-2024 : flux[2022..2024]
    """
    periodes = {
        "2009-2024": range(2010, 2025),
        "2011-2020": range(2012, 2022),
        "2021-2024": range(2022, 2025),
    }
    cats = ["activite", "habitat", "mixte", "route", "ferroviaire", "inconnu", "total"]
    return {
        lbl: {c: sum(flux.get(a, {}).get(c, 0) for a in ans) for c in cats}
        for lbl, ans in periodes.items()
    }


def _ratios(ligne: pd.Series, flux: dict, totaux: dict, coeff_reduction: float = 0.5) -> dict:
    """
    Calcul des ratios A3‑C + enveloppe ZAN, alignés sur la grammaire.
    coeff_reduction : fraction de réduction appliquée à la décennie de référence.
    """
    m2ha = M2_HA

    pop15 = _safe(ligne.get("pop15", 0))
    pop21 = _safe(ligne.get("pop21", 0))
    pop_moy = (pop15 + pop21) / 2 if (pop15 + pop21) > 0 else None

    men15 = _safe(ligne.get("men15", 0))
    men21 = _safe(ligne.get("men21", 0))
    delta_men = men21 - men15

    emp15 = _safe(ligne.get("emp15", 0))
    emp21 = _safe(ligne.get("emp21", 0))
    delta_emp = emp21 - emp15

    surf = _safe(ligne.get("surfcom2024", 0))

    ct  = totaux["2009-2024"]["total"]
    c20 = totaux["2011-2020"]["total"]
    c24 = totaux["2021-2024"]["total"]

    r = {}
    r["pop15"] = pop15
    r["pop21"] = pop21
    r["men15"] = men15
    r["men21"] = men21
    r["emp15"] = emp15
    r["emp21"] = emp21
    r["delta_men"] = delta_men
    r["delta_emp"] = delta_emp
    r["coeff_reduction"] = coeff_reduction

    r["m2_hab_total"]      = ct  / pop21   if pop21   > 0 else None
    r["m2_hab_ref"]        = c20 / pop_moy if pop_moy else None
    r["m2_hab_zan"]        = c24 / pop21   if pop21   > 0 else None
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

    env = c20 * (1.0 - coeff_reduction)
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
        fig.add_trace(go.Bar(
            name=label,
            x=annees,
            y=[flux[a][cat] / M2_HA for a in annees],
            marker_color=col
        ))
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
    fig.update_xaxes(gridcolor="#E5E7EB")
    fig.update_yaxes(gridcolor="#E5E7EB")
    return _plotly_to_png(fig, width, height)


def _fig_donut(totaux, width=340, height=300):
    cats   = ["habitat", "activite", "mixte", "route", "ferroviaire", "inconnu"]
    labels = ["Habitat", "Activité", "Mixte", "Route", "Ferroviaire", "Inconnu"]
    cols   = ["#3B82F6", "#F59E0B", "#8B5CF6", "#6B7280", "#EC4899", "#D1D5DB"]
    vals   = [totaux["2009-2024"][c] / M2_HA for c in cats]
    fig = go.Figure(go.Pie(
        labels=labels,
        values=vals,
        hole=0.5,
        marker=dict(colors=cols, line=dict(color="white", width=2)),
        textinfo="label+percent"
    ))
    fig.update_layout(
        height=height, showlegend=False,
        title="Répartition par catégorie (2009–2024)",
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=10, r=10, t=50, b=10)
    )
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
            "threshold": {
                "line": {"color": "#EF4444", "width": 4},
                "thickness": 0.75,
                "value": 100,
            },
        },
        title={"text": "Enveloppe ZAN utilisée", "font": {"size": 12}},
    ))
    fig.update_layout(
        height=height,
        paper_bgcolor="white",
        margin=dict(l=20, r=20, t=40, b=10)
    )
    return _plotly_to_png(fig, width, height)


def _fig_projection(r, width=680, height=280):
    env_ha  = r["enveloppe_zan_ha"] or 0
    cons_ha = r["consomme_zan_ha"]  or 0
    rythme  = cons_ha / 4 if cons_ha else 0
    annees  = list(range(2021, 2032))
    cumul   = [min(rythme * i, env_ha * 2) for i in range(len(annees))]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=annees, y=[env_ha] * len(annees),
        name="Enveloppe ZAN max",
        line=dict(color="#EF4444", dash="dash", width=2)
    ))
    fig.add_trace(go.Scatter(
        x=annees, y=cumul,
        name="Projection au rythme actuel",
        line=dict(color="#F97316", width=2)
    ))
    fig.add_trace(go.Scatter(
        x=[2021, 2022, 2023, 2024],
        y=[rythme, rythme*2, rythme*3, cons_ha],
        name="Consommé réel 2021–2024",
        line=dict(color="#10B981", width=3),
        marker=dict(size=7)
    ))
    fig.update_layout(
        height=height,
        title="Projection ZAN jusqu'en 2031",
        xaxis=dict(tickmode="linear", dtick=1),
        yaxis_title="Hectares cumulés",
        legend=dict(orientation="h", y=1.18, font=dict(size=10)),
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=50, r=10, t=60, b=40),
        font=dict(size=11),
    )
    fig.update_xaxes(gridcolor="#E5E7EB")
    fig.update_yaxes(gridcolor="#E5E7EB")
    return _plotly_to_png(fig, width, height)


def _fig_tendance(flux, r, width=700, height=320):
    annees_hist = list(range(2011, 2021))
    annees_obs  = list(range(2021, 2024))
    annees_proj = list(range(2024, 2031))

    # cumul historique
    hist_vals = [flux[a]["total"] / M2_HA for a in annees_hist]
    obs_vals  = [flux[a]["total"] / M2_HA for a in annees_obs]

    rythme_obs = (sum(obs_vals) / len(obs_vals)) if obs_vals else 0
    proj_vals = [rythme_obs * (i+1) for i in range(len(annees_proj))]

    objectif = r["conso_2011_20_ha"] * (1 - r["coeff_reduction"])

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=annees_hist, y=hist_vals,
        name="Historique 2011–2020",
        line=dict(color="#3B82F6", width=2)
    ))

    fig.add_trace(go.Scatter(
        x=annees_obs, y=obs_vals,
        name="Observé 2021–2023",
        line=dict(color="#F97316", width=3, dash="dot")
    ))

    fig.add_trace(go.Scatter(
        x=annees_proj, y=proj_vals,
        name="Projection 2024–2030",
        line=dict(color="#10B981", width=2, dash="dash")
    ))

    fig.add_trace(go.Scatter(
        x=annees_proj,
        y=[objectif] * len(annees_proj),
        name="Objectif 2030",
        line=dict(color="#EF4444", width=2, dash="dash")
    ))

    fig.update_layout(
        height=height,
        title="Tendance ZAN — Historique, Observé, Projection",
        xaxis=dict(tickmode="linear", dtick=1),
        yaxis_title="Hectares",
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=50, r=10, t=60, b=40),
        font=dict(size=11),
    )

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
        borderPadding=(6, 8, 6, 8))
    add("SubTitle",
        fontSize=10, leading=16, textColor=C_WHITE,
        fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=0,
        backColor=colors.HexColor("#1E3A5F"),
        borderPadding=(4, 8, 4, 8))
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
        borderPadding=6, borderRadius=4, spaceAfter=6)
    add("AlertOrange",
        fontSize=9, leading=12, textColor=colors.HexColor("#9A3412"),
        fontName="Helvetica", backColor=colors.HexColor("#FEF3C7"),
        borderPadding=6, spaceAfter=6)
    add("AlertRed",
        fontSize=9, leading=12, textColor=colors.HexColor("#7F1D1D"),
        fontName="Helvetica", backColor=colors.HexColor("#FEE2E2"),
        borderPadding=6, spaceAfter=6)

    return s


# ─────────────────────────────────────────────────────────────────
#  COMPOSANTS DE PAGE
# ─────────────────────────────────────────────────────────────────

def _metric_table(items, styles):
    """
    items = list of (label, value, unit) tuples.
    """
    n = len(items)
    col_w = (W - 2 * MARGIN) / n

    header_row = [Paragraph(lbl, styles["MetricLabel"]) for lbl, _, _ in items]
    value_row  = [Paragraph(f"<b>{val}</b>", styles["MetricValue"]) for _, val, _ in items]
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
    usable = W - 2 * MARGIN
    if col_widths is None:
        col_widths = [usable / len(headers)] * len(headers)

    header_style = ParagraphStyle(
        "TH", fontSize=8, fontName="Helvetica-Bold",
        textColor=C_WHITE, alignment=TA_CENTER
    )
    cell_style   = ParagraphStyle(
        "TD", fontSize=8, fontName="Helvetica",
        textColor=C_DARK, alignment=TA_CENTER
    )

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
            "Une révision urgente de la stratégie foncière est nécessaire.",
            styles["AlertRed"]
        )
    if pct >= 70:
        return Paragraph(
            f"🟠  VIGILANCE ZAN — {_fpct(pct)} de l'enveloppe utilisée en 4 ans seulement. "
            "Le rythme actuel doit impérativement être réduit.",
            styles["AlertOrange"]
        )
    return Paragraph(
        f"🟢  SITUATION ZAN SATISFAISANTE — {_fpct(pct)} de l'enveloppe utilisée. "
        "La commune est en bonne voie pour respecter l'objectif 2031.",
        styles["AlertGreen"]
    )


def _img_from_bytes(data: bytes, width_cm: float, height_cm: float) -> Image:
    buf = io.BytesIO(data)
    return Image(buf, width=width_cm * cm, height=height_cm * cm)


# ─────────────────────────────────────────────────────────────────
#  PAGE TEMPLATES (header/footer)
# ─────────────────────────────────────────────────────────────────

class _HeaderFooterCanvas:
    def __init__(self, nom_commune, code_insee, date_str):
        self.nom   = nom_commune
        self.code  = code_insee
        self.date  = date_str

    def draw_header(self, canvas, doc):
        canvas.saveState()

        BAND_TOP = H - 0.2 * cm
        BAND_BOT = H - 1.5 * cm
        BAND_H   = BAND_TOP - BAND_BOT
        TEXT_Y   = BAND_BOT + BAND_H * 0.3

        LOGO_W   = 1.6 * cm
        LOGO_X   = MARGIN
        TITLE_X  = MARGIN + LOGO_W + 0.3 * cm

        canvas.setFillColor(colors.HexColor("#F8FAFC"))
        canvas.rect(0, BAND_BOT, W, BAND_H, fill=1, stroke=0)

        canvas.setFillColor(C_PRIMARY)
        canvas.rect(MARGIN, BAND_BOT, W - 2 * MARGIN, 0.06 * cm, fill=1, stroke=0)

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

        canvas.setFont("Helvetica-Bold", 7.5)
        canvas.setFillColor(C_PRIMARY)
        canvas.drawString(TITLE_X, TEXT_Y, "Tableau de bord artificialisation communale")

        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(C_MID)
        canvas.drawRightString(
            W - MARGIN, TEXT_Y,
            f"{self.code} — {self.nom}  |  {self.date}"
        )

        canvas.restoreState()

    def draw_footer(self, canvas, doc):
        canvas.saveState()
        canvas.setFillColor(C_MID)
        canvas.rect(MARGIN, 1.1 * cm, W - 2 * MARGIN, 0.04 * cm, fill=1, stroke=0)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(C_MID)
        canvas.drawString(
            MARGIN, 0.75 * cm,
            "Source : CEREMA — Données NAF 2009-2024  |  Loi Climat & Résilience 2021"
        )
        canvas.drawRightString(W - MARGIN, 0.75 * cm, f"Page {doc.page}")
        canvas.restoreState()


def _on_cover(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(C_DARK)
    canvas.rect(0, 0, W, H, fill=1, stroke=0)
    canvas.setFillColor(C_PRIMARY)
    canvas.rect(0, H * 0.38, W, H * 0.62, fill=1, stroke=0)
    canvas.setFillColor(C_ACCENT)
    canvas.rect(0, H * 0.38 - 6, W, 6, fill=1, stroke=0)
    canvas.restoreState()


def _on_page(canvas, doc, hfc: _HeaderFooterCanvas):
    hfc.draw_header(canvas, doc)
    hfc.draw_footer(canvas, doc)


# ─────────────────────────────────────────────────────────────────
#  PAGES
# ─────────────────────────────────────────────────────────────────

def page_couverture(nom_commune, code_insee, dep, region, epci, scot, date_str, styles):
    story = []
    story.append(NextPageTemplate("Cover"))
    story.append(Spacer(1, H * 0.44))

    story.append(Paragraph("Observatoire de l'artificialisation", styles["CoverSub"]))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph(f"{code_insee} · {nom_commune}", styles["CoverTitle"]))
    story.append(Spacer(1, 0.2 * cm))

    story.append(Paragraph(f"{dep} — {region}", styles["CoverSub"]))
    story.append(Spacer(1, 0.6 * cm))

    story.append(Paragraph(f"EPCI : {epci}  |  SCoT : {scot}", styles["CoverInfo"]))
    story.append(Spacer(1, 1.2 * cm))

    story.append(Paragraph(
        f"Rapport généré le {date_str}  |  Données CEREMA 2009–2024",
        styles["CoverInfo"]
    ))

    logo_candidates = [
        Path(__file__).resolve().parent.parent / "assets" / "logo.png",
        Path(__file__).resolve().parent / "assets" / "logo.png",
        Path.cwd() / "assets" / "logo.png",
    ]
    for logo_path in logo_candidates:
        if logo_path.exists():
            story.append(Spacer(1, 1.2 * cm))
            story.append(Image(
                str(logo_path),
                width=3.5 * cm,
                height=3.5 * cm,
                hAlign="CENTER"
            ))
            break

    story.append(PageBreak())
    return story

def page_identite_commune(ligne, styles):
    story = []
    story.append(NextPageTemplate("Body"))
    story.append(Paragraph("1 · Informations générales", styles["SectionTitle"]))
    story.append(Spacer(1, 0.25 * cm))

    code_insee = str(ligne.get("idcom", "-----"))
    nom        = str(ligne.get("idcomtxt", "Commune inconnue"))
    idreg      = str(ligne.get("idreg", ""))      # si dispo
    reg        = str(ligne.get("idregtxt", ""))   # libellé région
    iddep      = str(ligne.get("iddep", ""))      # si dispo
    dep        = str(ligne.get("iddeptxt", ""))   # libellé département
    idepci     = str(ligne.get("epci24", ""))     # si dispo
    epci       = str(ligne.get("epci24txt", ""))  # libellé EPCI
    scot       = str(ligne.get("scot", "N/D"))

    headers = ["Élément", "Valeur"]
    rows = [
        ["Commune",     f"{code_insee} - {nom}"],
        ["Région",      f"{idreg} - {reg}" if idreg else reg],
        ["Département", f"{iddep} - {dep}" if iddep else dep],
        ["EPCI",        f"{idepci} - {epci}" if idepci else epci],
        ["SCoT",        scot],
    ]

    story.append(_data_table(headers, rows, styles))
    story.append(Spacer(1, 0.5 * cm))

    # petit texte contextuel
    story.append(Paragraph(
        "Ces informations administratives situent la commune dans ses cadres "
        "institutionnels (région, département, EPCI, SCoT).",
        styles["Body"]
    ))

    story.append(PageBreak())
    return story


def page_synthese_generale(r, totaux, styles):
    story = []
    story.append(NextPageTemplate("Body"))
    story.append(Paragraph("1 · Synthèse générale", styles["SectionTitle"]))
    story.append(Spacer(1, 0.25 * cm))

    story.append(Paragraph("Indicateurs clés", styles["SubTitle"]))

    items = [
        ("Conso totale 2009–2024", _fha(r["conso_tot_ha"]), "ha"),
        ("Référence 2011–2020", _fha(r["conso_2011_20_ha"]), "ha"),
        ("ZAN 2021–2024", _fha(r["conso_2021_24_ha"]), "ha"),
        ("% enveloppe utilisée", _fpct(r["pct_enveloppe_utilisee"]), "%"),
    ]
    story.append(_metric_table(items, styles))
    story.append(Spacer(1, 0.4 * cm))

    story.append(_zan_badge(r["pct_enveloppe_utilisee"], styles))
    story.append(PageBreak())
    return story


def page_flux_annuels(flux, png_flux, styles):
    story = []
    story.append(Paragraph("2 · Flux annuels", styles["SectionTitle"]))
    story.append(Spacer(1, 0.25 * cm))

    story.append(_img_from_bytes(png_flux, 17, 7))
    story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph("Tableau des flux annuels (ha)", styles["SubTitle"]))

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


def page_categories(totaux, png_donut, styles):
    story = []
    story.append(Paragraph("3 · Répartition par catégories", styles["SectionTitle"]))
    story.append(Spacer(1, 0.25 * cm))

    story.append(_img_from_bytes(png_donut, 9, 7))
    story.append(Spacer(1, 0.4 * cm))

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


def page_ratios(r, styles):
    story = []
    story.append(Paragraph("4 · Ratios A3‑C", styles["SectionTitle"]))
    story.append(Spacer(1, 0.25 * cm))

    headers = ["Ratio", "Valeur"]
    rows = [
        ["m² / hab (total)", _fm2(r["m2_hab_total"])],
        ["m² / hab (réf.)", _fm2(r["m2_hab_ref"])],
        ["m² / hab (ZAN)", _fm2(r["m2_hab_zan"])],
        ["ha / hab", _fha(r["ha_hab_par_menage"])],
        ["m² activité / emploi", _fm2(r["m2_act_par_emploi"])],
        ["Densité résidentielle", _fval(r["densite_resid"], "ménages/ha")],
        ["Ratio habitat / activité", _fval(r["ratio_hab_act"], "")],
    ]

    story.append(_data_table(headers, rows, styles))
    story.append(PageBreak())
    return story


def page_zan(r, png_jauge, png_proj, styles):
    story = []
    story.append(Paragraph("5 · Trajectoire ZAN", styles["SectionTitle"]))
    story.append(Spacer(1, 0.25 * cm))

    story.append(_img_from_bytes(png_jauge, 9, 6))
    story.append(Spacer(1, 0.5 * cm))

    story.append(_img_from_bytes(png_proj, 17, 6))
    story.append(Spacer(1, 0.5 * cm))

    if r["annees_avant_epuisement"] is not None:
        an_epuis = 2021 + int(r["annees_avant_epuisement"])
        story.append(Paragraph(
            f"Au rythme actuel, l’enveloppe serait épuisée vers {an_epuis}.",
            styles["Body"]
        ))

    story.append(PageBreak())
    return story

def page_analyse_tendance(r, totaux, png_tendance, styles):
    story = []

    story.append(Paragraph("6 · Analyse & tendance ZAN", styles["SectionTitle"]))
    story.append(Spacer(1, 0.25 * cm))

    # ─────────────────────────────────────────────
    # 1) Indicateurs clés (comme ton écran Streamlit)
    # ─────────────────────────────────────────────
    ref_ha = r["conso_2011_20_ha"]
    objectif_ha = ref_ha * (1 - r["coeff_reduction"])
    deja_ha = r["consomme_zan_ha"]
    reste_ha = objectif_ha - deja_ha
    reste_ha = max(reste_ha, 0)

    items = [
        ("Référence 2011–2020", _fha(ref_ha), "ha"),
        (f"Objectif 2021–2030 ({int(r['coeff_reduction']*100)} %)", _fha(objectif_ha), "ha"),
        ("Déjà consommé 2021–2023", _fha(deja_ha), "ha"),
        ("Reste disponible 2024–2030", _fha(reste_ha), "ha"),
    ]
    story.append(_metric_table(items, styles))
    story.append(Spacer(1, 0.5 * cm))

    # ─────────────────────────────────────────────
    # 2) Graphique de tendance
    # ─────────────────────────────────────────────
    story.append(_img_from_bytes(png_tendance, 17, 7))
    story.append(Spacer(1, 0.5 * cm))

    # ─────────────────────────────────────────────
    # 3) Analyse automatique
    # ─────────────────────────────────────────────
    rythme_obs = deja_ha / 3 if deja_ha else 0
    rythme_cible = objectif_ha / 10
    depassement = rythme_obs > rythme_cible

    analyse = []

    analyse.append(
        f"• Le rythme observé 2021–2023 est de <b>{_fha(rythme_obs)}</b> par an."
    )
    analyse.append(
        f"• Le rythme cible pour respecter l’objectif est de <b>{_fha(rythme_cible)}</b> par an."
    )

    if depassement:
        analyse.append(
            f"• ⚠️ Au rythme actuel, l’objectif serait dépassé avant 2030."
        )
    else:
        analyse.append(
            f"• 🟢 Le rythme actuel est compatible avec l’objectif ZAN."
        )

    story.append(Paragraph("<br/>".join(analyse), styles["Body"]))
    story.append(PageBreak())

    return story

def page_annexes(flux, totaux, r, styles):
    story = []
    story.append(Paragraph("6 · Annexes", styles["SectionTitle"]))
    story.append(Spacer(1, 0.25 * cm))

    # Totaux par période
    story.append(Paragraph("Totaux par période", styles["SubTitle"]))
    headers = ["Période", "Total (ha)"]
    rows = [
        ["2009–2024", _fha(totaux["2009-2024"]["total"] / M2_HA)],
        ["2011–2020", _fha(totaux["2011-2020"]["total"] / M2_HA)],
        ["2021–2024", _fha(totaux["2021-2024"]["total"] / M2_HA)],
    ]
    story.append(_data_table(headers, rows, styles))
    story.append(Spacer(1, 0.5 * cm))

    story.append(PageBreak())
    return story


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
    flux   = _extraire_flux(ligne)
    totaux = _totaux(flux)
    r      = _ratios(ligne, flux, totaux, coeff_reduction)

    nom_commune = str(ligne.get("idcomtxt", "Commune inconnue"))
    code_insee  = str(ligne.get("idcom", "-----"))
    dep         = str(ligne.get("iddeptxt", ""))
    region      = str(ligne.get("idregtxt", ""))
    epci        = str(ligne.get("epci24txt", ""))
    scot        = str(ligne.get("scot", "N/D"))
    date_str    = datetime.now().strftime("%d/%m/%Y")

    styles = _make_styles()

    png_flux  = _fig_flux(flux,    width=700, height=320)
    png_donut = _fig_donut(totaux, width=340, height=280)
    png_jauge = _fig_jauge(r,      width=340, height=240)
    png_proj  = _fig_projection(r, width=680, height=260)
    png_tendance = _fig_tendance(flux, r, width=700, height=320)

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

    frame_cover = Frame(0, 0, W, H, leftPadding=0, rightPadding=0,
                        topPadding=0, bottomPadding=0)
    frame_body  = Frame(MARGIN, 1.8 * cm, W - 2 * MARGIN, H - 3.6 * cm,
                        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)

    hfc = _HeaderFooterCanvas(nom_commune, code_insee, date_str)

    doc.addPageTemplates([
        PageTemplate(id="Cover", frames=[frame_cover], onPage=_on_cover),
        PageTemplate(id="Body",  frames=[frame_body],
                     onPage=lambda c, d: _on_page(c, d, hfc)),
    ])

    story = []
    story += page_couverture(nom_commune, code_insee, dep, region, epci, scot, date_str, styles)
    story += page_identite_commune(ligne, styles)
    story += page_synthese_generale(r, totaux, styles)
    story += page_flux_annuels(flux, png_flux, styles)
    story += page_categories(totaux, png_donut, styles)
    story += page_ratios(r, styles)
    story += page_zan(r, png_jauge, png_proj, styles)
    story += page_analyse_tendance(r, totaux, png_tendance, styles)
    story += page_annexes(flux, totaux, r, styles)

    doc.build(story)
    return buf.getvalue()
