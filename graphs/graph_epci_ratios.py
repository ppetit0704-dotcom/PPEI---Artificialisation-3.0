"""
@author  : Philippe PETIT
@version : 2.0.0
@description : Ratios intercommunaux — version dynamique alignée sur agreger_epci().
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from graphs.graph_epci_general import agreger_epci


# ───────────────────────────────────────────────────────────────
#  CONSTANTES
# ───────────────────────────────────────────────────────────────

CATEGORIES = [
    ("habitat",     "Habitat",      "#3B82F6"),
    ("activite",    "Activité",     "#F59E0B"),
    ("mixte",       "Mixte",        "#8B5CF6"),
    ("route",       "Route",        "#6B7280"),
    ("ferroviaire", "Ferroviaire",  "#EC4899"),
    ("inconnu",     "Inconnu",      "#D1D5DB"),
]

M2_HA = 10_000.0


# ───────────────────────────────────────────────────────────────
#  OUTILS DE CALCUL
# ───────────────────────────────────────────────────────────────

def _compute_totaux_par_categorie(flux: dict):
    """Retourne (totaux, totaux_ref, totaux_zan) par catégorie."""
    totaux = {k: 0.0 for k, _, _ in CATEGORIES}
    totaux_ref = {k: 0.0 for k, _, _ in CATEGORIES}
    totaux_zan = {k: 0.0 for k, _, _ in CATEGORIES}

    for an, data in flux.items():
        try:
            a = int(an)
        except:
            continue

        for key, _, _ in CATEGORIES:
            val = data.get(key, 0.0) or 0.0
            totaux[key] += val
            if 2011 <= a <= 2020:
                totaux_ref[key] += val
            if 2021 <= a <= 2024:
                totaux_zan[key] += val

    return totaux, totaux_ref, totaux_zan


def _fmt(x):
    if x is None:
        return "N/D"
    return f"{x:.2f}".replace(".", ",")


def _fmt_pct(x):
    if x is None:
        return "N/D"
    return f"{x:.1f} %".replace(".", ",")


# ───────────────────────────────────────────────────────────────
#  GRAPHIQUES
# ───────────────────────────────────────────────────────────────

def _graph_ratio_bar(values: dict, title: str, unit: str):
    """Graphique barres horizontales pour ratios par catégorie."""
    labels = [label for _, label, _ in CATEGORIES]
    vals = [values[k] for k, _, _ in CATEGORIES]
    cols = [col for _, _, col in CATEGORIES]

    fig = go.Figure(go.Bar(
        x=vals,
        y=labels,
        orientation="h",
        marker_color=cols,
        hovertemplate=f"%{{y}}<br>%{{x:.2f}} {unit}<extra></extra>",
    ))

    fig.update_layout(
        title=title,
        xaxis_title=unit,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=420,
        margin=dict(l=120, r=20, t=60, b=40),
    )
    fig.update_layout(
        updatemenus=[
            {
                "type": "buttons",
                "direction": "right",
                "x": 0.5,
                "y": -0.2,
                "showactive": False,
                "buttons": [
                    {
                        "label": "Vue d’ensemble",
                        "method": "relayout",
                        "args": [{"xaxis.autorange": True, "yaxis.autorange": True}]
                    }
                ]
            }
        ]
    )
    return fig


def _graph_ratio_global(agg: dict):
    """Graphique radar des ratios globaux A3‑C."""
    labels = [
        "m² / hab (total)",
        "m² / hab (réf.)",
        "m² / hab (ZAN)",
        "ha / hab",
        "m² activité / emploi",
    ]

    values = [
        agg["m2_hab_total"] or 0,
        agg["m2_hab_ref"] or 0,
        agg["m2_hab_zan"] or 0,
        agg["ha_par_hab"] or 0,
        agg["m2_act_par_emploi"] or 0,
    ]

    fig = go.Figure(go.Scatterpolar(
        r=values,
        theta=labels,
        fill="toself",
        line=dict(color="#3B82F6", width=3),
        marker=dict(size=6),
        hovertemplate="%{theta}<br>%{r:.2f}<extra></extra>",
    ))

    fig.update_layout(
        title="Ratios globaux A3‑C",
        polar=dict(
            radialaxis=dict(visible=True, linewidth=1, gridcolor="#666"),
            angularaxis=dict(rotation=90),
        ),
        showlegend=False,
        height=480,
        margin=dict(l=40, r=40, t=60, b=40),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_layout(
        updatemenus=[
            {
                "type": "buttons",
                "direction": "right",
                "x": 0.5,
                "y": -0.2,
                "showactive": False,
                "buttons": [
                    {
                        "label": "Vue d’ensemble",
                        "method": "relayout",
                        "args": [{"xaxis.autorange": True, "yaxis.autorange": True}]
                    }
                ]
            }
        ]
    )
    return fig


# ───────────────────────────────────────────────────────────────
#  RENDU PRINCIPAL
# ───────────────────────────────────────────────────────────────

def rendu_ratios_epci(communes: pd.DataFrame, struct: dict):
    """
    Ratios EPCI — version dynamique alignée sur agreger_epci().
    """
    if communes.empty:
        st.warning("Aucune donnée disponible pour cette intercommunalité.")
        return

    agg = agreger_epci(communes, struct)
    flux = agg["flux"]

    # Totaux par catégorie
    totaux_cat, totaux_ref_cat, totaux_zan_cat = _compute_totaux_par_categorie(flux)

    ligne0 = communes.iloc[0]
    nom_epci = ligne0.get("epci24txt", "Intercommunalité")

    st.markdown(f"## 📊 Ratios — {nom_epci}")
    st.divider()

    # ───────────────────────────────────────────────────────────
    #  RATIOS GLOBAUX
    # ───────────────────────────────────────────────────────────

    st.markdown("### 📐 Ratios globaux A3‑C")
    st.caption("Ratios calculés à partir des totaux agrégés EPCI (population, emplois, surfaces).")

    st.plotly_chart(_graph_ratio_global(agg), use_container_width=True)

    st.divider()

    # ───────────────────────────────────────────────────────────
    #  RATIOS PAR CATÉGORIE
    # ───────────────────────────────────────────────────────────

    st.markdown("### 🗂️ Ratios par catégorie")

    # m² consommés par catégorie / habitant
    if agg["pop21"] and agg["pop21"] > 0:
        ratio_m2_par_hab = {k: totaux_cat[k] / agg["pop21"] for k, _, _ in CATEGORIES}
    else:
        ratio_m2_par_hab = {k: None for k, _, _ in CATEGORIES}

    st.markdown("#### m² consommés par habitant (2009–2024)")
    st.plotly_chart(
        _graph_ratio_bar(ratio_m2_par_hab, "m² consommés par habitant", "m² / hab"),
        use_container_width=True
    )

    st.divider()

    # ha consommés par catégorie / ha de territoire
    if agg["surf_ha"] and agg["surf_ha"] > 0:
        ratio_ha_par_ha = {k: (totaux_cat[k] / M2_HA) / agg["surf_ha"] * 100
                          for k, _, _ in CATEGORIES}
    else:
        ratio_ha_par_ha = {k: None for k, _, _ in CATEGORIES}

    st.markdown("#### Part du territoire consommée par catégorie (%)")
    st.plotly_chart(
        _graph_ratio_bar(ratio_ha_par_ha, "Part du territoire consommée", "%"),
        use_container_width=True
    )

    st.divider()

    # Tableau récapitulatif
    st.markdown("### 📄 Tableau récapitulatif des ratios")

    rows = []
    for key, label, _ in CATEGORIES:
        rows.append({
            "Catégorie": label,
            "m² / hab": _fmt(ratio_m2_par_hab[key]),
            "% territoire consommé": _fmt_pct(ratio_ha_par_ha[key]),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
