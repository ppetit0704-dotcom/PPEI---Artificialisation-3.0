"""
@module  : graphs/graph_synthese.py
@author  : Philippe PETIT
@version : 1.0.0
@description : Graphiques de synthèse de l'artificialisation
"""

import plotly.graph_objects as go
import streamlit as st

# ─── Palette couleurs par catégorie ─────────────────────────────────────────
COULEURS = {
    "Activité":     "#E07B39",
    "Habitat":      "#4A90D9",
    "Mixte":        "#7BC67E",
    "Inconnu":      "#A0A0A0",
    "Route":        "#C0392B",
    "Ferroviaire":  "#8E44AD",
}

CATEGORIES = ["Activité", "Habitat", "Mixte", "Inconnu", "Route", "Ferroviaire"]
KEYS       = ["activity", "habitat", "mixte", "inconnu", "route", "ferroviaire"]

# Correspondance index → année réelle
INDEX_TO_YEAR = {
    3: 2011, 4: 2012, 5: 2013, 6: 2014, 7: 2015,
    8: 2016, 9: 2017, 10: 2018, 11: 2019, 12: 2020,
    13: 2021, 14: 2022, 15: 2023,
}


def _m2_to_ha(valeur):
    """Convertit des m² en hectares en gérant les chaînes, None, etc."""
    if valeur is None:
        return 0.0
    if isinstance(valeur, (int, float)):
        return round(valeur / 10_000, 2)
    if isinstance(valeur, str):
        v = valeur.replace(",", ".").strip()
        try:
            return round(float(v) / 10_000, 2)
        except ValueError:
            return 0.0
    return 0.0



def _fmt(valeur):
    """Formate un nombre avec séparateur de milliers (espace)."""
    return f"{valeur:,.2f}".replace(",", " ").replace(".", ",")


# ─── Graphique 1 : Barres empilées par année ────────────────────────────────

def graph_barres_annuelles(donnees: dict) -> go.Figure:
    """
    Barres empilées : consommation annuelle par catégorie (en ha).
    """
    annees = list(INDEX_TO_YEAR.values())

    fig = go.Figure()

    for label, key in zip(CATEGORIES, KEYS):
        d = donnees[key]
        valeurs = [_m2_to_ha(d.get(idx, 0)) for idx in INDEX_TO_YEAR.keys()]

        fig.add_trace(go.Bar(
            name=label,
            x=annees,
            y=valeurs,
            marker_color=COULEURS[label],
            hovertemplate=f"<b>{label}</b><br>Année : %{{x}}<br>Surface : %{{y:,.2f}} ha<extra></extra>",
        ))

    fig.update_layout(
        barmode="stack",
        title="Consommation foncière annuelle par catégorie (ha)",
        xaxis=dict(title="Année", tickmode="linear", dtick=1),
        yaxis=dict(title="Surface (ha)"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#CCCCCC"),
        margin=dict(l=50, r=20, t=60, b=50),
        hovermode="x unified",
    )

    return fig


# ─── Graphique 2 : Camembert par catégorie (total) ──────────────────────────
def graph_camembert(donnees: dict) -> go.Figure:
    """
    Camembert : répartition totale par catégorie (en ha).
    """
    labels = []
    values = []

    for label, key in zip(CATEGORIES, KEYS):
        # Conversion robuste des valeurs AVANT sum()
        total_m2 = sum(
            float(str(v).replace(",", ".") or 0)
            for v in donnees[key].values()
        )
        total_ha = _m2_to_ha(total_m2)

        if total_ha > 0:
            labels.append(label)
            values.append(total_ha)

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        marker=dict(colors=[COULEURS[l] for l in labels]),
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>Surface : %{value:,.2f} ha<br>Part : %{percent}<extra></extra>",
        hole=0.35,
    ))

    fig.update_layout(
        title="Répartition totale par catégorie (ha)",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#CCCCCC"),
        legend=dict(orientation="v", x=1.0, y=0.5),
        margin=dict(l=20, r=20, t=60, b=20),
    )

    return fig


# ─── Rendu Streamlit complet ─────────────────────────────────────────────────

def rendu_graph_synthese(donnees: dict):
    """
    Affiche les deux graphiques de synthèse dans Streamlit.
    """
    st.markdown("#### 📊 Visualisation graphique")

    col1, col2 = st.columns([2, 1])

    with col1:
        fig_barres = graph_barres_annuelles(donnees)
        st.plotly_chart(fig_barres, use_container_width=True)

    with col2:
        fig_camembert = graph_camembert(donnees)
        st.plotly_chart(fig_camembert, use_container_width=True)
