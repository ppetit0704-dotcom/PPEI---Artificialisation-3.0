"""
@author  : Philippe PETIT
@version : 2.0.0
@description : Analyse intercommunale — tendances, rythmes annuels, évolutions.
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


def _fmt_ha(m2):
    return f"{m2 / M2_HA:.2f} ha".replace(".", ",")


def _fmt_pct(x):
    if x is None:
        return "N/D"
    return f"{x:.1f} %".replace(".", ",")


# ───────────────────────────────────────────────────────────────
#  GRAPHIQUES
# ───────────────────────────────────────────────────────────────

def _graph_tendance(flux: dict) -> go.Figure:
    """Graphique des tendances annuelles par catégorie."""
    annees = sorted(flux.keys())
    fig = go.Figure()

    for key, label, col in CATEGORIES:
        vals = [(flux[a].get(key, 0.0) / M2_HA) for a in annees]
        fig.add_trace(go.Scatter(
            name=label,
            x=annees,
            y=vals,
            mode="lines+markers",
            line=dict(color=col, width=3),
            marker=dict(size=6),
            hovertemplate=f"<b>{label}</b><br>Année : %{{x}}<br>%{{y:.2f}} ha<extra></extra>",
        ))

    fig.update_layout(
        title="Tendances annuelles par catégorie (ha/an)",
        xaxis=dict(title="Année", tickmode="linear", dtick=1, tickangle=-45),
        yaxis=dict(title="Hectares"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=420,
        margin=dict(l=50, r=20, t=60, b=50),
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


def _graph_rythmes(totaux_ref_cat, totaux_zan_cat):
    """Comparaison des rythmes annuels moyens ref vs ZAN."""
    labels = [label for _, label, _ in CATEGORIES]
    r_ref = [(totaux_ref_cat[k] / 10) / M2_HA for k, _, _ in CATEGORIES]
    r_zan = [(totaux_zan_cat[k] / 4)  / M2_HA for k, _, _ in CATEGORIES]
    cols = [col for _, _, col in CATEGORIES]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Rythme 2011-2020",
        x=labels,
        y=r_ref,
        marker_color=[f"rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:],16)},0.45)" for c in cols],
        marker_line=dict(color=cols, width=1.5),
    ))
    fig.add_trace(go.Bar(
        name="Rythme 2021-2024",
        x=labels,
        y=r_zan,
        marker_color=cols,
    ))

    fig.update_layout(
        barmode="group",
        title="Comparaison des rythmes annuels moyens (ha/an)",
        yaxis_title="Hectares / an",
        legend=dict(orientation="h", y=1.12),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=380,
        margin=dict(l=50, r=20, t=60, b=40),
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

def rendu_analyse_epci(communes: pd.DataFrame, struct: dict):
    """
    Analyse EPCI — tendances, rythmes, évolutions.
    Compatible avec agreger_epci(communes, struct).
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

    st.markdown(f"## 📈 Analyse & Tendances — {nom_epci}")
    st.divider()

    # ── Tendances annuelles ─────────────────────────────────────
    st.markdown("### 📉 Tendances annuelles par catégorie")
    st.plotly_chart(_graph_tendance(flux), use_container_width=True)

    st.divider()

    # ── Rythmes annuels ─────────────────────────────────────────
    st.markdown("### ⚡ Rythmes annuels moyens (réf. vs ZAN)")
    st.caption("Permet d’identifier les catégories en accélération ou en décélération.")
    st.plotly_chart(_graph_rythmes(totaux_ref_cat, totaux_zan_cat), use_container_width=True)

    st.divider()

    # ── Tableau synthétique ─────────────────────────────────────
    st.markdown("### 🗂️ Synthèse des évolutions par catégorie")

    rows = []
    for key, label, _ in CATEGORIES:
        tot = totaux_cat[key] / M2_HA
        ref = totaux_ref_cat[key] / M2_HA
        zan = totaux_zan_cat[key] / M2_HA

        r_ref = (totaux_ref_cat[key] / 10) / M2_HA
        r_zan = (totaux_zan_cat[key] / 4) / M2_HA
        evol = ((r_zan - r_ref) / r_ref * 100) if r_ref > 0 else None

        rows.append({
            "Catégorie": label,
            "Total 2009-2024": f"{tot:.2f} ha".replace(".", ","),
            "Rythme réf. (ha/an)": f"{r_ref:.2f}".replace(".", ","),
            "Rythme ZAN (ha/an)": f"{r_zan:.2f}".replace(".", ","),
            "Évolution (%)": _fmt_pct(evol),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
