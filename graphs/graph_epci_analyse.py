"""
@author  : Philippe PETIT
@version : 1.0.0
@description : Module d'agrégation intercommunale — Onglet Analyse & Tendances EPCI.
               Courbes historiques + observées + projection ZAN à l'échelle CC.
               Même logique que graph_analyse.py mais sur données agrégées.
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st

from graphs.graph_epci_general import (
    agreger_epci,
    agreger_flux_annuels,
    _fha,
    _fpct,
)


# ─────────────────────────────────────────────────────────────────
#  CONSTANTES — identiques à graph_analyse.py
# ─────────────────────────────────────────────────────────────────

ANNEES_HISTO = list(range(2011, 2021))   # indices 3-12  → flux[2012]…flux[2021]
ANNEES_OBS   = [2022, 2023, 2024]        # indices 13-15 → flux[2022]…flux[2024]
ANNEES_PROJ  = list(range(2025, 2031))   # projection 2025-2030

CATEGORIES = {
    "activite":    ("Activité",    "#E63946"),
    "habitat":     ("Habitat",     "#2A9D8F"),
    "mixte":       ("Mixte",       "#E9C46A"),
    "inconnu":     ("Inconnu",     "#A8DADC"),
    "route":       ("Route",       "#457B9D"),
    "ferroviaire": ("Ferroviaire", "#6D6875"),
}

TRAJECTOIRES = [
    (0.625, "62,5 %",                       "MediumVioletRed"),
    (0.620, "62,0 %",                       "MediumVioletRed"),
    (0.615, "61,5 %",                       "MediumVioletRed"),
    (0.610, "61,0 %",                       "MediumVioletRed"),
    (0.607, "60,7 % (Proposition SRADDET)", "MediumVioletRed"),
    (0.605, "60,5 %",                       "DeepPink"),
    (0.600, "60,0 %",                       "DeepPink"),
    (0.575, "57,5 %",                       "Tomato"),
    (0.550, "55,0 %",                       "Tomato"),
    (0.525, "52,5 %",                       "Tomato"),
    (0.500, "50,0 %",                       "Olive"),
    (0.475, "47,5 %",                       "Olive"),
    (0.450, "45,0 %",                       "Olive"),
    (0.425, "42,5 %",                       "MediumSeaGreen"),
    (0.400, "40,0 %",                       "MediumSeaGreen"),
    (0.375, "37,5 %",                       "PaleGreen"),
]
DEFAULT_INDEX = 10


# ─────────────────────────────────────────────────────────────────
#  UTILITAIRES
# ─────────────────────────────────────────────────────────────────

def _serie_histo(flux: dict, cat: str) -> list:
    """Valeurs annuelles en ha pour 2012-2021 (référence)."""
    return [flux.get(a, {}).get(cat, 0) / 10_000 for a in range(2012, 2022)]


def _serie_obs(flux: dict, cat: str) -> list:
    """Valeurs annuelles en ha pour 2022-2024 (ZAN observé)."""
    return [flux.get(a, {}).get(cat, 0) / 10_000 for a in range(2022, 2025)]


def _projection(serie_obs: list, coeff: float, n: int = 6) -> list:
    """Projette 2025-2030 au rythme moyen observé × (1 - coeff)."""
    if not serie_obs or sum(serie_obs) == 0:
        return [0.0] * n
    rythme = sum(serie_obs) / len(serie_obs)
    return [round(rythme * (1.0 - coeff), 3)] * n


def _total_histo(flux: dict) -> float:
    return sum(
        flux.get(a, {}).get(cat, 0) / 10_000
        for a in range(2012, 2022)
        for cat in CATEGORIES
    )


def _total_obs(flux: dict) -> float:
    return sum(
        flux.get(a, {}).get(cat, 0) / 10_000
        for a in range(2022, 2025)
        for cat in CATEGORIES
    )


# ─────────────────────────────────────────────────────────────────
#  CARDS
# ─────────────────────────────────────────────────────────────────

def _badge(col, label, value, sub, color):
    col.markdown(
        f"""
        <div style="
            background-color:{color};
            padding:15px; border-radius:10px;
            text-align:center;">
            <div style="font-size:13px;color:white;margin-bottom:4px;">{label}</div>
            <div style="font-size:19px;color:white;font-weight:700;">{value}</div>
            <div style="font-size:11px;color:rgba(255,255,255,0.75);margin-top:4px;">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_cards(total_histo, objectif, total_obs, coeff):
    reste   = max(objectif - total_obs, 0.0)
    pct_obs = total_obs / objectif * 100 if objectif > 0 else 0.0
    c1, c2, c3, c4 = st.columns(4)
    _badge(c1, "📅 Référence CC 2011-2020",
           f"{total_histo:.2f} ha".replace(".", ","),
           "Base de calcul agrégée", "#1565C0")
    _badge(c2, "🎯 Objectif CC 2021-2030",
           f"{objectif:.2f} ha".replace(".", ","),
           f"Réduction de {coeff*100:.1f} % appliquée".replace(".", ","), "#045211")
    _badge(c3, "📊 Consommé CC 2021-2024",
           f"{total_obs:.2f} ha".replace(".", ","),
           f"{pct_obs:.1f} % de l'objectif atteint".replace(".", ","), "#4C0452")
    _badge(c4, "⚠️ Reste CC 2025-2030",
           f"{reste:.2f} ha".replace(".", ","),
           "Sur 6 années restantes", "#F54927")


# ─────────────────────────────────────────────────────────────────
#  GRAPHIQUE PRINCIPAL
# ─────────────────────────────────────────────────────────────────

def _build_figure(flux: dict, coeff: float) -> go.Figure:
    fig = go.Figure()

    # ── Total historique ─────────────────────────────────────────
    y_histo_tot = [
        sum(flux.get(a, {}).get(cat, 0) / 10_000 for cat in CATEGORIES)
        for a in ANNEES_HISTO
    ]
    fig.add_trace(go.Scatter(
        x=ANNEES_HISTO, y=y_histo_tot,
        name="Total CC (2011-2020)",
        mode="lines+markers",
        line=dict(color="#ECEFF1", width=3),
        marker=dict(size=6),
    ))

    # ── Total observé ────────────────────────────────────────────
    y_obs_tot = [
        sum(flux.get(a, {}).get(cat, 0) / 10_000 for cat in CATEGORIES)
        for a in ANNEES_OBS
    ]
    fig.add_trace(go.Scatter(
        x=ANNEES_OBS, y=y_obs_tot,
        name="Total CC observé (2022-2024)",
        mode="lines+markers",
        line=dict(color="#ECEFF1", width=3, dash="dot"),
        marker=dict(size=6, symbol="diamond"),
    ))

    # ── Total projeté ────────────────────────────────────────────
    y_proj_tot = _projection(y_obs_tot, coeff, n=6)
    x_proj = [2024] + ANNEES_PROJ
    y_proj = [y_obs_tot[-1]] + y_proj_tot
    fig.add_trace(go.Scatter(
        x=x_proj, y=y_proj,
        name="Total CC projeté (2025-2030)",
        mode="lines+markers",
        line=dict(color="#ECEFF1", width=2, dash="dash"),
        marker=dict(size=5, symbol="diamond-open"),
    ))

    # ── Courbes par catégorie ────────────────────────────────────
    for cat, (label, color) in CATEGORIES.items():
        y_h = _serie_histo(flux, cat)
        fig.add_trace(go.Scatter(
            x=ANNEES_HISTO, y=y_h,
            name=f"{label} (histo)", legendgroup=cat,
            mode="lines+markers",
            line=dict(color=color, width=1.5),
            marker=dict(size=4),
        ))

        y_o = _serie_obs(flux, cat)
        fig.add_trace(go.Scatter(
            x=ANNEES_OBS, y=y_o,
            name=f"{label} (obs.)", legendgroup=cat,
            mode="lines+markers",
            line=dict(color=color, width=1.5, dash="dot"),
            marker=dict(size=4, symbol="diamond"),
            showlegend=False,
        ))

        y_p = _projection(y_o, coeff, n=6)
        fig.add_trace(go.Scatter(
            x=[2024] + ANNEES_PROJ,
            y=[y_o[-1]] + y_p,
            name=f"{label} (proj.)", legendgroup=cat,
            mode="lines+markers",
            line=dict(color=color, width=1.2, dash="dash"),
            marker=dict(size=3, symbol="diamond-open"),
            showlegend=False,
        ))

    # ── Séparateurs verticaux ────────────────────────────────────
    fig.add_vline(x=2021.5,
        line=dict(color="rgba(255,255,255,0.25)", width=1.5, dash="longdash"),
        annotation_text="ZAN →", annotation_position="top right",
        annotation_font=dict(color="rgba(255,255,255,0.5)", size=11))
    fig.add_vline(x=2024.5,
        line=dict(color="rgba(255,165,0,0.3)", width=1.5, dash="dot"),
        annotation_text="Projection →", annotation_position="top right",
        annotation_font=dict(color="rgba(255,165,0,0.6)", size=10))

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15,25,40,0.8)",
        height=540,
        margin=dict(l=60, r=20, t=40, b=60),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.01,
            xanchor="left", x=0, font=dict(size=11),
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(
            title="Année", tickmode="linear", dtick=1,
            tickangle=-45, gridcolor="rgba(255,255,255,0.06)",
        ),
        yaxis=dict(
            title="Consommation agrégée CC (ha)",
            gridcolor="rgba(255,255,255,0.06)", zeroline=False,
        ),
        hovermode="x unified",
    )
    return fig


# ─────────────────────────────────────────────────────────────────
#  RENDU PRINCIPAL — ONGLET ANALYSE EPCI
# ─────────────────────────────────────────────────────────────────

def rendu_analyse_epci(communes: pd.DataFrame):
    """
    Point d'entrée appelé depuis app.py en mode EPCI (vue agrégée).
    Le coefficient ZAN est lu depuis st.session_state["trajectoire_select"].
    """
    if communes.empty:
        st.warning("Aucune donnée disponible pour cette CC.")
        return

    ligne0   = communes.iloc[0]
    nom_epci = str(ligne0.get("epci24txt", "Intercommunalité"))

    # ── Agrégation des flux ──────────────────────────────────────
    flux = agreger_flux_annuels(communes)

    st.markdown(f"## 📈 Analyse & Tendances — {nom_epci}")

    # ── Sélecteur trajectoire (partagé avec mode commune) ────────
    labels  = [t[1] for t in TRAJECTOIRES]
    couleurs= [t[2] for t in TRAJECTOIRES]
    valeurs = [t[0] for t in TRAJECTOIRES]

    col_sel, col_info = st.columns([2, 3])
    with col_sel:
        idx = st.selectbox(
            "🎯 Coefficient de réduction (objectif ZAN)",
            options=range(len(TRAJECTOIRES)),
            format_func=lambda i: labels[i],
            index=DEFAULT_INDEX,
            key="trajectoire_select",   # ← même clé que mode commune → partagé !
        )
    coeff   = valeurs[idx]
    couleur = couleurs[idx]

    with col_info:
        st.markdown(
            f"""
            <div style="
                background:rgba(255,255,255,0.04); border-radius:8px;
                padding:0.6rem 1rem; margin-top:1.6rem;
                border-left:3px solid {couleur}; font-size:0.9rem; color:#CFD8DC;">
            Réduction CC : <strong style="color:{couleur};">{coeff*100:.1f} %</strong>
            &nbsp;|&nbsp; Enveloppe = référence CC 2011-2020 &times;
            <strong>{round(1-coeff,3)}</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Calculs ──────────────────────────────────────────────────
    total_histo = _total_histo(flux)
    total_obs   = _total_obs(flux)
    objectif    = round(total_histo * (1.0 - coeff), 2)

    # ── Cards ────────────────────────────────────────────────────
    _render_cards(total_histo, objectif, total_obs, coeff)

    st.divider()

    # ── Graphique ────────────────────────────────────────────────
    fig = _build_figure(flux, coeff)
    st.plotly_chart(fig, use_container_width=True)

    # ── Note de lecture ──────────────────────────────────────────
    st.caption(
        "Données agrégées de toutes les communes membres  ·  "
        "Lignes pleines = historique 2011-2020  ·  "
        "Tirets courts = observé 2022-2024  ·  "
        "Tirets longs = projection 2025-2030 au rythme observé avec réduction appliquée"
    )
