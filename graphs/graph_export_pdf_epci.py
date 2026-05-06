"""
@author  : Philippe PETIT
@version : 2.0.0
@description : Export PDF intercommunal — version dynamique alignée sur agreger_epci().
"""

import pandas as pd
import plotly.io as pio
import streamlit as st
import plotly.graph_objects as go

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
#  GRAPHIQUES (réutilisés dans le PDF)
# ───────────────────────────────────────────────────────────────

def _graph_barres(flux: dict) -> go.Figure:
    annees = sorted(flux.keys())
    fig = go.Figure()

    for key, label, col in CATEGORIES:
        vals = [(flux[a].get(key, 0.0) / M2_HA) for a in annees]
        fig.add_trace(go.Bar(
            name=label,
            x=annees,
            y=vals,
            marker_color=col,
        ))

    fig.update_layout(
        barmode="stack",
        title="Consommation annuelle agrégée (ha/an)",
        height=380,
        margin=dict(l=40, r=20, t=60, b=40),
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def _graph_donut(totaux_cat: dict) -> go.Figure:
    labels = [label for _, label, _ in CATEGORIES]
    values = [totaux_cat[k] / M2_HA for k, _, _ in CATEGORIES]
    colors = [col for _, _, col in CATEGORIES]

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.52,
        marker=dict(colors=colors),
        textinfo="label+percent",
    ))
    fig.update_layout(
        title="Répartition totale par catégorie (2009–2024)",
        height=360,
        margin=dict(l=20, r=20, t=60, b=20),
        showlegend=False,
    )
    return fig


# ───────────────────────────────────────────────────────────────
#  RENDU PRINCIPAL — EXPORT PDF
# ───────────────────────────────────────────────────────────────

def rendu_export_pdf_epci(communes: pd.DataFrame, struct: dict):
    """
    Export PDF EPCI — version premium.
    Produit un rendu HTML propre, stylé, imprimable en PDF via le navigateur.
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

    st.markdown(f"## 📄 Export PDF — {nom_epci}")
    st.caption("Le document ci-dessous est optimisé pour une impression PDF (Ctrl+P → Enregistrer en PDF).")
    st.divider()

    # ───────────────────────────────────────────────────────────
    #  PAGE DE GARDE
    # ───────────────────────────────────────────────────────────

    st.markdown(f"""
    <div style="padding:40px; border:2px solid #ccc; border-radius:12px; margin-bottom:40px;">
        <h1 style="text-align:center; margin-bottom:0;">Synthèse intercommunale</h1>
        <h2 style="text-align:center; margin-top:5px; color:#555;">{nom_epci}</h2>
        <p style="text-align:center; margin-top:30px; font-size:18px;">
            Tableau de bord de l'artificialisation — Export PDF<br>
            Version 3.0 — Données agrégées automatiquement
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ───────────────────────────────────────────────────────────
    #  MÉTRIQUES PRINCIPALES
    # ───────────────────────────────────────────────────────────

    st.markdown("### 📦 Indicateurs principaux")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Consommation totale 2009–2024", _fmt_ha(agg["totaux"]["total"]))
    c2.metric("Référence 2011–2020",           _fmt_ha(agg["totaux"]["ref"]))
    c3.metric("ZAN 2021–2024",                 _fmt_ha(agg["totaux"]["zan"]))
    c4.metric("% territoire artificialisé",    _fmt_pct(agg.get("pct_artificialise")))

    st.divider()

    # ───────────────────────────────────────────────────────────
    #  TABLEAU PAR CATÉGORIE
    # ───────────────────────────────────────────────────────────

    st.markdown("### 🗂️ Détail par catégorie")

    rows = []
    for key, label, _ in CATEGORIES:
        rows.append({
            "Catégorie": label,
            "Total 2009–2024": _fmt_ha(totaux_cat[key]),
            "2011–2020 (réf.)": _fmt_ha(totaux_ref_cat[key]),
            "2021–2024 (ZAN)": _fmt_ha(totaux_zan_cat[key]),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    # ───────────────────────────────────────────────────────────
    #  GRAPHIQUES
    # ───────────────────────────────────────────────────────────

    st.markdown("### 📈 Graphiques")

    col_g, col_d = st.columns([2, 1])
    with col_g:
        st.plotly_chart(_graph_barres(flux), use_container_width=True)
    with col_d:
        st.plotly_chart(_graph_donut(totaux_cat), use_container_width=True)

    st.divider()

    # ───────────────────────────────────────────────────────────
    #  FIN DU DOCUMENT
    # ───────────────────────────────────────────────────────────

    st.markdown("""
    <div style="text-align:center; margin-top:60px; color:#777;">
        <p>Document généré automatiquement — Tableau de bord artificialisation V3.0</p>
    </div>
    """, unsafe_allow_html=True)
