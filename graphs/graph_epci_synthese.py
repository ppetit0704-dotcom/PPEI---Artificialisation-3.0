"""
@author  : Philippe PETIT
@version : 1.0.0
@description : Module d'agrégation intercommunale — Onglet Synthèse EPCI.
               Tableau par catégorie agrégé + graphiques barres empilées et donut.
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st

from graphs.graph_epci_general import (
    agreger_epci,
    agreger_flux_annuels,
    _REF_SUFFIXES,
    _ZAN_SUFFIXES,
    _fha,
    _fpct,
    _fint,
)


# ─────────────────────────────────────────────────────────────────
#  CONSTANTES
# ─────────────────────────────────────────────────────────────────

CATEGORIES = [
    ("habitat",     "Habitat",      "#3B82F6"),
    ("activite",    "Activité",     "#F59E0B"),
    ("mixte",       "Mixte",        "#8B5CF6"),
    ("route",       "Route",        "#6B7280"),
    ("ferroviaire", "Ferroviaire",  "#EC4899"),
    ("inconnu",     "Inconnu",      "#D1D5DB"),
]


# ─────────────────────────────────────────────────────────────────
#  GRAPHIQUES
# ─────────────────────────────────────────────────────────────────

def _graph_barres(flux: dict) -> go.Figure:
    """Barres empilées annuelles agrégées."""
    annees = sorted(flux.keys())
    fig    = go.Figure()

    for key, label, col in CATEGORIES:
        vals = [flux[a][key] / 10_000 for a in annees]
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
        font=dict(color="#CCCCCC"),
        height=400,
        margin=dict(l=50, r=20, t=60, b=50),
        hovermode="x unified",
    )
    return fig


def _graph_donut(agg: dict) -> go.Figure:
    """Donut de répartition par catégorie."""
    labels = [label for _, label, _ in CATEGORIES]
    values = [agg["totaux"][key]["total"] / 10_000 for key, _, _ in CATEGORIES]
    colors = [col for _, _, col in CATEGORIES]

    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.52,
        marker=dict(colors=colors, line=dict(color="white", width=2)),
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>%{value:.2f} ha<br>%{percent}<extra></extra>",
    ))
    fig.update_layout(
        title="Répartition totale par catégorie",
        height=380,
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=50, b=10),
    )
    return fig


def _hex_to_rgba(hex_color: str, alpha: float = 0.5) -> str:
    """Convertit un hex #RRGGBB en rgba(r,g,b,alpha) pour Plotly."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _graph_evolution_periodes(agg: dict) -> go.Figure:
    """Comparaison référence vs ZAN par catégorie."""
    labels_cat = [label for _, label, _ in CATEGORIES]
    vals_ref   = [agg["totaux"][key]["ref"] / 10_000 for key, _, _ in CATEGORIES]
    vals_zan   = [agg["totaux"][key]["zan"] / 10_000 for key, _, _ in CATEGORIES]
    cols       = [col for _, _, col in CATEGORIES]
    cols_light = [_hex_to_rgba(c, 0.45) for c in cols]   # version transparente en rgba

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
        font=dict(color="#CCCCCC"),
        height=360,
        margin=dict(l=50, r=20, t=60, b=40),
    )
    return fig


# ─────────────────────────────────────────────────────────────────
#  TABLEAU RÉCAPITULATIF
# ─────────────────────────────────────────────────────────────────

def _tableau_recap(agg: dict) -> pd.DataFrame:
    m2ha = 10_000
    rows = []
    for key, label, _ in CATEGORIES:
        tot  = agg["totaux"][key]["total"] / m2ha
        ref  = agg["totaux"][key]["ref"]   / m2ha
        zan  = agg["totaux"][key]["zan"]   / m2ha
        conso_tot = agg["conso_tot_ha"]
        pct  = tot / conso_tot * 100 if conso_tot > 0 else 0
        # Évolution rythme : (zan/4) vs (ref/10) en %
        r_ref = ref / 10 if ref > 0 else 0
        r_zan = zan / 4  if zan > 0 else 0
        evol  = ((r_zan - r_ref) / r_ref * 100) if r_ref > 0 else None
        rows.append({
            "Catégorie":       label,
            "Total 2009-2024": f"{tot:.2f} ha".replace(".", ","),
            "2011-2020 (réf.)":f"{ref:.2f} ha".replace(".", ","),
            "2021-2024 (ZAN)": f"{zan:.2f} ha".replace(".", ","),
            "Part totale":     f"{pct:.1f} %".replace(".", ","),
            "Évol. rythme":    (
                f"{evol:+.1f} %".replace(".", ",") if evol is not None else "N/D"
            ),
        })

    # Ligne TOTAL
    conso_tot = agg["conso_tot_ha"]
    conso_ref = agg["conso_ref_ha"]
    conso_zan = agg["conso_zan_ha"]
    r_ref_tot = conso_ref / 10 if conso_ref > 0 else 0
    r_zan_tot = conso_zan / 4  if conso_zan > 0 else 0
    evol_tot  = ((r_zan_tot - r_ref_tot) / r_ref_tot * 100) if r_ref_tot > 0 else None

    rows.append({
        "Catégorie":        "TOTAL",
        "Total 2009-2024":  f"{conso_tot:.2f} ha".replace(".", ","),
        "2011-2020 (réf.)": f"{conso_ref:.2f} ha".replace(".", ","),
        "2021-2024 (ZAN)":  f"{conso_zan:.2f} ha".replace(".", ","),
        "Part totale":      "100,0 %",
        "Évol. rythme":     (
            f"{evol_tot:+.1f} %".replace(".", ",") if evol_tot is not None else "N/D"
        ),
    })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────
#  RENDU PRINCIPAL — ONGLET SYNTHÈSE EPCI
# ─────────────────────────────────────────────────────────────────

def rendu_synthese_epci(communes: pd.DataFrame, coeff_reduction: float = 0.5):
    """
    Point d'entrée appelé depuis app.py en mode EPCI (vue agrégée).
    communes        : DataFrame des communes membres
    coeff_reduction : coefficient ZAN sélectionné par l'utilisateur
    """
    if communes.empty:
        st.warning("Aucune donnée disponible pour cette CC.")
        return

    ligne0   = communes.iloc[0]
    nom_epci = str(ligne0.get("epci24txt", "Intercommunalité"))

    # ── Agrégation ───────────────────────────────────────────────
    agg  = agreger_epci(communes)
    flux = agreger_flux_annuels(communes)

    pct_red     = coeff_reduction * 100
    facteur     = round(1.0 - coeff_reduction, 3)
    enveloppe   = agg["conso_ref_ha"] * (1.0 - coeff_reduction)
    restant     = enveloppe - agg["conso_zan_ha"]
    pct_env     = agg["conso_zan_ha"] / enveloppe * 100 if enveloppe > 0 else None

    st.markdown(f"## 📐 Synthèse — {nom_epci}")
    st.divider()

    # ── Métriques principales ────────────────────────────────────
    st.markdown("### 📦 Consommation agrégée")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Consommation totale\n2009-2024",  _fha(agg["conso_tot_ha"]))
    c2.metric("Décennie référence\n2011-2020",   _fha(agg["conso_ref_ha"]))
    c3.metric("Période ZAN\n2021-2024",          _fha(agg["conso_zan_ha"]))
    c4.metric("% territoire artificialisé",      _fpct(agg["pct_artificialise"]))

    st.divider()

    # ── ZAN agrégé ───────────────────────────────────────────────
    st.markdown("### ⚡ Bilan ZAN intercommunal")
    st.caption(
        f"Coefficient appliqué : **−{pct_red:.1f} %** (facteur {facteur}) — "
        f"Enveloppe CC = {_fha(agg['conso_ref_ha'])} × {facteur}"
    )

    z1, z2, z3, z4 = st.columns(4)
    z1.metric("Enveloppe ZAN 2021-2031",   _fha(enveloppe))
    z2.metric("Consommé 2021-2024",        _fha(agg["conso_zan_ha"]))
    z3.metric("Solde restant 2025-2031",   _fha(restant),
              delta=f"{restant:+.2f} ha".replace(".", ","),
              delta_color="normal")
    z4.metric("% enveloppe utilisée",      _fpct(pct_env))

    # Alerte ZAN
    if pct_env is not None:
        if pct_env >= 100:
            st.error(f"🔴 Enveloppe ZAN dépassée à l'échelle CC ({_fpct(pct_env)}) — action urgente requise.")
        elif pct_env >= 70:
            st.warning(f"🟠 Vigilance ZAN — {_fpct(pct_env)} de l'enveloppe utilisée en 4 ans.")
        else:
            st.success(f"🟢 Situation ZAN satisfaisante — {_fpct(pct_env)} de l'enveloppe utilisée.")

    st.divider()

    # ── Tableau récapitulatif ─────────────────────────────────────
    st.markdown("### 🗂️ Détail par catégorie de destination")
    st.caption(
        "Évol. rythme = variation du rythme annuel moyen entre 2011-2020 et 2021-2024. "
        "Valeur négative = bonne trajectoire ✅"
    )
    df_recap = _tableau_recap(agg)
    st.dataframe(df_recap, use_container_width=True, hide_index=True,
                 column_config={
                     "Évol. rythme": st.column_config.TextColumn(
                         "Évol. rythme", help="Variation du rythme annuel moyen (2021-2024 vs 2011-2020)"
                     )
                 })

    st.divider()

    # ── Graphiques ───────────────────────────────────────────────
    st.markdown("### 📈 Visualisations")

    # Ligne 1 : barres + donut
    col_g, col_d = st.columns([2, 1])
    with col_g:
        st.plotly_chart(_graph_barres(flux), use_container_width=True)
    with col_d:
        st.plotly_chart(_graph_donut(agg), use_container_width=True)

    # Ligne 2 : comparaison périodes
    st.plotly_chart(_graph_evolution_periodes(agg), use_container_width=True)
