"""
@author  : Philippe PETIT
@version : 2.0.0
@description : Synthèse intercommunale — version dynamique alignée sur agreger_epci().
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

def _compute_totaux_par_categorie(flux: dict) -> tuple[dict, dict, dict]:
    """
    Calcule, à partir de agg["flux"], les totaux par catégorie :
      - total 2009–2024
      - ref 2011–2020
      - ZAN 2021–2024
    """
    totaux = {k: 0.0 for k, _, _ in CATEGORIES}
    totaux_ref = {k: 0.0 for k, _, _ in CATEGORIES}
    totaux_zan = {k: 0.0 for k, _, _ in CATEGORIES}

    annees = sorted(flux.keys())
    for an in annees:
        try:
            a = int(an)
        except Exception:
            # Si jamais les années sont des strings non numériques, on les ignore
            continue

        for key, _, _ in CATEGORIES:
            val = flux.get(an, {}).get(key, 0.0) or 0.0
            totaux[key] += val
            if 2011 <= a <= 2020:
                totaux_ref[key] += val
            if 2021 <= a <= 2024:
                totaux_zan[key] += val

    return totaux, totaux_ref, totaux_zan


def _fmt_ha(m2: float) -> str:
    ha = m2 / M2_HA
    return f"{ha:.2f} ha".replace(".", ",")


def _fmt_pct(x: float | None) -> str:
    if x is None:
        return "N/D"
    return f"{x:.1f} %".replace(".", ",")


# ───────────────────────────────────────────────────────────────
#  GRAPHIQUES
# ───────────────────────────────────────────────────────────────

def _graph_barres(flux: dict) -> go.Figure:
    annees = sorted(flux.keys())
    fig = go.Figure()

    for key, label, col in CATEGORIES:
        vals = [(flux[a].get(key, 0.0) / M2_HA) for a in annees]
        fig.add_trace(go.Bar(
            name=label, x=annees, y=vals,
            marker_color=col,
            hovertemplate=f"<b>{label}</b><br>Année : %{{x}}<br>%{{y:.2f}} ha<extra></extra>",
        ))

    fig.update_layout(
        barmode="stack",
        title="Consommation foncière annuelle agrégée (ha/an)",
        xaxis=dict(title="Année", tickmode="linear", dtick=1, tickangle=-45),
        yaxis=dict(title="Hectares"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        height=400,
        margin=dict(l=50, r=20, t=60, b=50),
        hovermode="x unified",
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


def _graph_donut(totaux_par_cat: dict) -> go.Figure:
    labels = [label for _, label, _ in CATEGORIES]
    values = [totaux_par_cat[key] / M2_HA for key, _, _ in CATEGORIES]
    colors = [col for _, _, col in CATEGORIES]

    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.52,
        marker=dict(colors=colors, line=dict(color="white", width=2)),
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>%{value:.2f} ha<br>%{percent}<extra></extra>",
    ))
    fig.update_layout(
        title="Répartition totale par catégorie (2009–2024)",
        height=380,
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=50, b=10),
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


def _graph_evolution_periodes(totaux_ref_cat: dict, totaux_zan_cat: dict) -> go.Figure:
    labels_cat = [label for _, label, _ in CATEGORIES]
    vals_ref   = [totaux_ref_cat[key] / M2_HA for key, _, _ in CATEGORIES]
    vals_zan   = [totaux_zan_cat[key] / M2_HA for key, _, _ in CATEGORIES]
    cols       = [col for _, _, col in CATEGORIES]

    cols_light = []
    for c in cols:
        h = c.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        cols_light.append(f"rgba({r},{g},{b},0.45)")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="2011-2020 (réf.)", x=labels_cat, y=vals_ref,
        marker_color=cols_light,
        marker_line=dict(color=cols, width=1.5),
    ))
    fig.add_trace(go.Bar(
        name="2021-2024 (ZAN)", x=labels_cat, y=vals_zan,
        marker_color=cols,
    ))
    fig.update_layout(
        barmode="group",
        title="Comparaison Référence 2011-2020 vs ZAN 2021-2024 (ha)",
        yaxis_title="Hectares",
        legend=dict(orientation="h", y=1.12),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        height=360,
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
#  TABLEAU RÉCAPITULATIF
# ───────────────────────────────────────────────────────────────

def _tableau_recap(
    totaux_cat: dict,
    totaux_ref_cat: dict,
    totaux_zan_cat: dict,
    conso_tot_m2: float,
    conso_ref_m2: float,
    conso_zan_m2: float,
) -> pd.DataFrame:
    rows = []

    for key, label, _ in CATEGORIES:
        tot  = totaux_cat[key]      / M2_HA
        ref  = totaux_ref_cat[key]  / M2_HA
        zan  = totaux_zan_cat[key]  / M2_HA
        part = (totaux_cat[key] / conso_tot_m2 * 100) if conso_tot_m2 > 0 else 0.0

        # Rythmes annuels moyens
        r_ref = (totaux_ref_cat[key] / 10.0) / M2_HA if totaux_ref_cat[key] > 0 else 0.0
        r_zan = (totaux_zan_cat[key] / 4.0)  / M2_HA if totaux_zan_cat[key] > 0 else 0.0
        evol  = ((r_zan - r_ref) / r_ref * 100) if r_ref > 0 else None

        rows.append({
            "Catégorie":        label,
            "Total 2009-2024":  f"{tot:.2f} ha".replace(".", ","),
            "2011-2020 (réf.)": f"{ref:.2f} ha".replace(".", ","),
            "2021-2024 (ZAN)":  f"{zan:.2f} ha".replace(".", ","),
            "Part totale":      _fmt_pct(part),
            "Évol. rythme":     (f"{evol:+.1f} %".replace(".", ",") if evol is not None else "N/D"),
        })

    # Ligne TOTAL
    conso_tot_ha = conso_tot_m2 / M2_HA
    conso_ref_ha = conso_ref_m2 / M2_HA
    conso_zan_ha = conso_zan_m2 / M2_HA

    r_ref_tot = (conso_ref_m2 / 10.0) / M2_HA if conso_ref_m2 > 0 else 0.0
    r_zan_tot = (conso_zan_m2 / 4.0)  / M2_HA if conso_zan_m2 > 0 else 0.0
    evol_tot  = ((r_zan_tot - r_ref_tot) / r_ref_tot * 100) if r_ref_tot > 0 else None

    rows.append({
        "Catégorie":        "TOTAL",
        "Total 2009-2024":  f"{conso_tot_ha:.2f} ha".replace(".", ","),
        "2011-2020 (réf.)": f"{conso_ref_ha:.2f} ha".replace(".", ","),
        "2021-2024 (ZAN)":  f"{conso_zan_ha:.2f} ha".replace(".", ","),
        "Part totale":      "100,0 %",
        "Évol. rythme":     (f"{evol_tot:+.1f} %".replace(".", ",") if evol_tot is not None else "N/D"),
    })

    return pd.DataFrame(rows)



# ───────────────────────────────────────────────────────────────
#  RENDU PRINCIPAL
# ───────────────────────────────────────────────────────────────

def rendu_synthese_epci(communes: pd.DataFrame, struct: dict):
    """
    Vue Synthèse EPCI — agrégation dynamique alignée sur agreger_epci().
    """
    if communes.empty:
        st.warning("Aucune donnée disponible pour cette intercommunalité.")
        return

    agg = agreger_epci(communes, struct)
    flux = agg["flux"]

    # Totaux globaux (m2)
    conso_tot_m2 = agg["totaux"]["total"]
    conso_ref_m2 = agg["totaux"]["ref"]
    conso_zan_m2 = agg["totaux"]["zan"]

    # Totaux par catégorie (m2)
    totaux_cat, totaux_ref_cat, totaux_zan_cat = _compute_totaux_par_categorie(flux)

    ligne0 = communes.iloc[0]
    nom_epci = ligne0.get("epci24txt", "Intercommunalité")

    st.markdown(f"## 📐 Synthèse — {nom_epci}")
    st.divider()

    # ── Métriques principales ─────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Consommation totale 2009-2024", _fmt_ha(conso_tot_m2))
    c2.metric("Référence 2011-2020",           _fmt_ha(conso_ref_m2))
    c3.metric("ZAN 2021-2024",                 _fmt_ha(conso_zan_m2))
    c4.metric("% territoire artificialisé",    _fmt_pct(agg.get("pct_artificialise")))

    st.divider()

    # ── Tableau récapitulatif ────────────────────────────────
    st.markdown("### 🗂️ Détail par catégorie de destination")
    st.caption(
        "Évol. rythme = variation du rythme annuel moyen entre 2011-2020 et 2021-2024. "
        "Valeur négative = bonne trajectoire ✅"
    )
    df_recap = _tableau_recap(
        totaux_cat,
        totaux_ref_cat,
        totaux_zan_cat,
        conso_tot_m2,
        conso_ref_m2,
        conso_zan_m2,
    )
    st.dataframe(
        df_recap,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Évol. rythme": st.column_config.TextColumn(
                "Évol. rythme",
                help="Variation du rythme annuel moyen (2021-2024 vs 2011-2020)",
            )
        },
    )

    st.divider()

    # ── Graphiques ───────────────────────────────────────────
    st.markdown("### 📈 Visualisations")

    col_g, col_d = st.columns([2, 1])
    with col_g:
        st.plotly_chart(_graph_barres(flux), use_container_width=True)
    with col_d:
        st.plotly_chart(_graph_donut(totaux_cat), use_container_width=True)

    st.plotly_chart(_graph_evolution_periodes(totaux_ref_cat, totaux_zan_cat), use_container_width=True)
    


