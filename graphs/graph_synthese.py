"""
@module  : graphs/graph_synthese.py
@author  : Philippe PETIT
@version : 3.4.0
@description : Graphiques de synthèse de l'artificialisation
               Version dynamique basée sur les suffixes CEREMA
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


# ─────────────────────────────────────────────────────────────────────────────
#  UTILITAIRES
# ─────────────────────────────────────────────────────────────────────────────

def _m2_to_ha(valeur):
    try:
        return round(float(str(valeur).replace(",", ".")) / 10_000, 2)
    except Exception:
        return 0.0


def _build_flux_structure(donnees):
    """
    Construit la structure dynamique des flux à partir des suffixes CEREMA.
    On ignore automatiquement les flux < 2011.
    """

    suffixes = donnees["suffixes_ref"] + donnees["suffixes_zan"]

    # On filtre les flux avant 2011
    suffixes = [(a, b) for (a, b) in suffixes if int(a) >= 11]

    # Année = 2000 + int(a)
    years = [2000 + int(a) for (a, b) in suffixes]

    # Labels flux : "2011–2012"
    flux_labels = [f"{2000+int(a)}–{2000+int(b)}" for (a, b) in suffixes]

    # Indices internes (3,4,5...) utilisés dans donnees["habitat"]
    # On doit retrouver l’index correspondant à chaque suffixe
    indices = []
    for (a, b) in suffixes:
        # On cherche l’index interne où se trouve artAA...BB
        for idx, val in donnees["habitat"].items():
            if isinstance(idx, int):
                # On reconstruit la clé attendue
                key = f"art{a}hab{b}"
                # Si la valeur existe dans la ligne, c’est le bon index
                if key in donnees["habitat"]:
                    pass
        # Mais lire_les_donnees remplit les flux dans l’ordre :
        # index 3 = premier suffixe
        # index 4 = deuxième suffixe
        # etc.
        # Donc on peut simplement faire :
        indices = list(range(3, 3 + len(suffixes)))

    return indices, years, flux_labels


# ─────────────────────────────────────────────────────────────────────────────
#  GRAPHIQUE 1 : Barres empilées annuelles
# ─────────────────────────────────────────────────────────────────────────────

def graph_barres_annuelles(donnees: dict) -> go.Figure:

    indices, years, flux_labels = _build_flux_structure(donnees)

    fig = go.Figure()

    for label, key in zip(CATEGORIES, KEYS):
        d = donnees[key]
        valeurs = [_m2_to_ha(d.get(idx, 0)) for idx in indices]

        fig.add_trace(go.Bar(
            name=label,
            x=years,
            y=valeurs,
            customdata=flux_labels,
            marker_color=COULEURS[label],
            hovertemplate=(
                f"<b>{label}</b><br>"
                "Flux : %{customdata}<br>"
                "Année de début : %{x}<br>"
                "Surface : %{y:,.2f} ha"
                "<extra></extra>"
            ),
        ))

    fig.update_layout(
        barmode="stack",
        title="Consommation foncière annuelle par catégorie (ha)",
        xaxis=dict(title="Flux CEREMA (année de début)", tickmode="linear", dtick=1),
        yaxis=dict(title="Surface (ha)"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#CCCCCC"),
        margin=dict(l=50, r=20, t=60, b=50),
        hovermode="x unified",
    )

    return fig


# ─────────────────────────────────────────────────────────────────────────────
#  GRAPHIQUE 2 : Camembert total
# ─────────────────────────────────────────────────────────────────────────────

def graph_camembert(donnees: dict) -> go.Figure:

    labels = []
    values = []

    for label, key in zip(CATEGORIES, KEYS):
        total_m2 = 0.0
        for v in donnees[key].values():
            try:
                total_m2 += float(str(v).replace(",", "."))
            except Exception:
                continue
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


# ─────────────────────────────────────────────────────────────────────────────
#  Rendu Streamlit
# ─────────────────────────────────────────────────────────────────────────────

def rendu_graph_synthese(donnees: dict):

    st.markdown("#### 📊 Visualisation graphique")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.plotly_chart(graph_barres_annuelles(donnees), use_container_width=True)

    with col2:
        st.plotly_chart(graph_camembert(donnees), use_container_width=True)
