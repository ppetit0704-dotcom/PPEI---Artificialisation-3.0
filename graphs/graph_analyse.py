"""
@author : Philippe PETIT
@version : 1.0.0
@description : Onglet Analyse & Tendances — Graphique linéaire + projection + cards
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# =====================================================
# CONSTANTES
# =====================================================

# Années historiques (indices 3–12 → 2011-2020)
ANNEES_HISTO = list(range(2011, 2021))

# Années observées 2021-2023 (indices 13–15)
ANNEES_OBS = [2021, 2022, 2023]

# Années de projection (2024-2030)
ANNEES_PROJ = list(range(2024, 2031))

# Toutes les années de la période 2021-2030
ANNEES_FUTUR = ANNEES_OBS + ANNEES_PROJ

# Catégories
CATEGORIES = {
    "activity":    ("Activité",     "#E63946"),
    "habitat":     ("Habitat",      "#2A9D8F"),
    "mixte":       ("Mixte",        "#E9C46A"),
    "inconnu":     ("Inconnu",      "#A8DADC"),
    "route":       ("Route",        "#457B9D"),
    "ferroviaire": ("Ferroviaire",  "#6D6875"),
}

# Options du selectbox (valeur = coefficient de RÉDUCTION, ex: 0.607 = réduction de 60.7%)
TRAJECTOIRES = [
    (0.625, "62.5 %",                      "MediumVioletRed"),
    (0.620, "62.0 %",                      "MediumVioletRed"),
    (0.615, "61.5 %",                      "MediumVioletRed"),
    (0.610, "61.0 %",                      "MediumVioletRed"),
    (0.607, "60.7 % (Proposition SRRADET)","MediumVioletRed"),
    (0.605, "60.5 %",                      "DeepPink"),
    (0.600, "60.0 %",                      "DeepPink"),
    (0.575, "57.5 %",                      "Tomato"),
    (0.550, "55.0 %",                      "Tomato"),
    (0.525, "52.5 %",                      "Tomato"),
    (0.500, "50.0 %",                      "Olive"),
    (0.475, "47.5 %",                      "Olive"),
    (0.450, "45.0 %",                      "Olive"),
    (0.425, "42.5 %",                      "MediumSeaGreen"),
    (0.400, "40.0 %",                      "MediumSeaGreen"),
    (0.375, "37.5 %",                      "PaleGreen"),
]

# Index par défaut (50.0 %)
DEFAULT_INDEX = 10


# =====================================================
# UTILITAIRES
# =====================================================

def _m2_to_ha(valeur):
    """Convertit m² → ha en gérant les chaînes, None, etc."""
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


def fmt_ha(v):
    return f"{v:,.2f}".replace(",", "\u202f").replace(".", ",")


def fmt_pct(v):
    try:
        return f"{float(v):.1f} %".replace(".", ",")
    except (TypeError, ValueError):
        return "N/A"


# =====================================================
# CALCULS
# =====================================================

def _serie_historique(donnees, key):
    """Retourne les valeurs annuelles en ha pour les années 2011-2020 (indices 3-12)."""
    return [_m2_to_ha(donnees[key][i]) for i in range(3, 13)]


def _serie_observee(donnees, key):
    """Retourne les valeurs annuelles en ha pour 2021-2023 (indices 13-15)."""
    return [_m2_to_ha(donnees[key][i]) for i in range(13, 16)]


def _projection(serie_obs, coeff_reduction, n_proj=7):
    """
    Projette les années 2024-2030 selon le rythme observé 2021-2023,
    en appliquant le coefficient de réduction.

    Le rythme annuel moyen observé (2021-2023) est multiplié par (1 - coeff_reduction).
    """
    if not serie_obs or sum(serie_obs) == 0:
        return [0.0] * n_proj

    rythme_annuel = sum(serie_obs) / len(serie_obs)
    rythme_cible  = rythme_annuel * (1.0 - coeff_reduction)
    return [round(rythme_cible, 2)] * n_proj


def _total_histo(donnees):
    """Total 2011-2020 toutes catégories en ha."""
    return sum(
        _m2_to_ha(donnees[k][i])
        for k in CATEGORIES
        for i in range(3, 13)
    )


def _total_obs(donnees):
    """Total 2021-2023 toutes catégories en ha."""
    return sum(
        _m2_to_ha(donnees[k][i])
        for k in CATEGORIES
        for i in range(13, 16)
    )


def _objectif_total(total_histo, coeff_reduction):
    """Objectif 2021-2030 = total_histo * (1 - coeff_reduction)."""
    return round(total_histo * (1.0 - coeff_reduction), 2)


# =====================================================
# CARDS — style badge (cohérent avec cards.py)
# =====================================================

def _badge_card(col, label, value, sub, color):
    """
    Affiche un badge dans une colonne Streamlit,
    dans le même style que badge() / badgeBlue() de cards.py.
    """
    col.markdown(
        f"""
        <div style="
            background-color:{color};
            padding:15px;
            border-radius:10px;
            text-align:center;
            font-size:16px;
            font-weight:600;">
            <div style="font-size:14px; color:white; margin-bottom:4px;">{label}</div>
            <div style="font-size:20px; color:white; font-weight:700;">{value}</div>
            <div style="font-size:12px; color:rgba(255,255,255,0.75); margin-top:4px;">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_cards(total_histo, objectif, total_obs, coeff_reduction):
    reste   = max(objectif - total_obs, 0.0)
    pct_obs = (total_obs / objectif * 100) if objectif > 0 else 0.0
    pct_red = coeff_reduction * 100

    c1, c2, c3, c4 = st.columns(4)

    _badge_card(c1,
        label="📅 Référence 2011–2020",
        value=f"{fmt_ha(total_histo)} ha",
        sub="Base de calcul",
        color="#1565C0",          # blue
    )
    _badge_card(c2,
        label="🎯 Objectif 2021–2030",
        value=f"{fmt_ha(objectif)} ha",
        sub=f"Réduction de {fmt_pct(pct_red)} appliquée",
        color="#045211",          # darkgreen
    )
    _badge_card(c3,
        label="📊 Déjà consommé 2021–2023",
        value=f"{fmt_ha(total_obs)} ha",
        sub=f"{fmt_pct(pct_obs)} de l'objectif atteint",
        color="#4C0452",          # purple
    )
    _badge_card(c4,
        label="⚠️ Reste disponible 2024–2030",
        value=f"{fmt_ha(reste)} ha",
        sub="Sur 7 années restantes",
        color="#F54927",          # red-orange
    )


# =====================================================
# GRAPHIQUE PRINCIPAL
# =====================================================

def _build_figure(donnees, coeff_reduction):
    fig = go.Figure()

    # ── Courbe totale historique (2011-2020) ─────────────
    total_histo_par_an = [
        sum(_m2_to_ha(donnees[k][i]) for k in CATEGORIES)
        for i in range(3, 13)
    ]
    fig.add_trace(go.Scatter(
        x=ANNEES_HISTO, y=total_histo_par_an,
        name="Total (2011-2020)",
        mode="lines+markers",
        line=dict(color="#ECEFF1", width=3),
        marker=dict(size=6),
    ))

    # ── Courbe totale observée + projetée (2021-2030) ────
    total_obs_par_an = [
        sum(_m2_to_ha(donnees[k][i]) for k in CATEGORIES)
        for i in range(13, 16)
    ]
    total_proj_par_an = _projection(total_obs_par_an, coeff_reduction)

    # Observed (plein)
    fig.add_trace(go.Scatter(
        x=ANNEES_OBS, y=total_obs_par_an,
        name="Total observé (2021-2023)",
        mode="lines+markers",
        line=dict(color="#ECEFF1", width=3, dash="dot"),
        marker=dict(size=6, symbol="diamond"),
        showlegend=True,
    ))
    # Projected (pointillé)
    # Raccordement : on part du dernier observé
    x_proj = [2023] + ANNEES_PROJ
    y_proj = [total_obs_par_an[-1]] + total_proj_par_an
    fig.add_trace(go.Scatter(
        x=x_proj, y=y_proj,
        name="Total projeté (2024-2030)",
        mode="lines+markers",
        line=dict(color="#ECEFF1", width=2, dash="dash"),
        marker=dict(size=5, symbol="diamond-open"),
    ))

    # ── Courbes par catégorie ────────────────────────────
    for key, (label, color) in CATEGORIES.items():
        # Historique
        y_h = _serie_historique(donnees, key)
        fig.add_trace(go.Scatter(
            x=ANNEES_HISTO, y=y_h,
            name=f"{label} (histo)",
            mode="lines+markers",
            line=dict(color=color, width=1.5),
            marker=dict(size=4),
            legendgroup=key,
        ))

        # Observé
        y_o = _serie_observee(donnees, key)
        fig.add_trace(go.Scatter(
            x=ANNEES_OBS, y=y_o,
            name=f"{label} (obs.)",
            mode="lines+markers",
            line=dict(color=color, width=1.5, dash="dot"),
            marker=dict(size=4, symbol="diamond"),
            legendgroup=key,
            showlegend=False,
        ))

        # Projeté
        y_p = _projection(y_o, coeff_reduction)
        x_p = [2023] + ANNEES_PROJ
        y_p_full = [y_o[-1]] + y_p
        fig.add_trace(go.Scatter(
            x=x_p, y=y_p_full,
            name=f"{label} (proj.)",
            mode="lines+markers",
            line=dict(color=color, width=1.2, dash="dash"),
            marker=dict(size=3, symbol="diamond-open"),
            legendgroup=key,
            showlegend=False,
        ))

    # ── Ligne verticale de séparation 2020/2021 ──────────
    fig.add_vline(
        x=2020.5,
        line=dict(color="rgba(255,255,255,0.25)", width=1.5, dash="longdash"),
        annotation_text="ZAN →",
        annotation_position="top right",
        annotation_font=dict(color="rgba(255,255,255,0.5)", size=11),
    )

    # ── Ligne verticale de séparation observé/projeté ───
    fig.add_vline(
        x=2023.5,
        line=dict(color="rgba(255,165,0,0.3)", width=1.5, dash="dot"),
        annotation_text="Projection →",
        annotation_position="top right",
        annotation_font=dict(color="rgba(255,165,0,0.6)", size=10),
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15,25,40,0.8)",
        height=520,
        margin=dict(l=60, r=20, t=40, b=60),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.01,
            xanchor="left",
            x=0,
            font=dict(size=11),
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(
            title="Année",
            tickmode="linear",
            dtick=1,
            tickangle=-45,
            gridcolor="rgba(255,255,255,0.06)",
        ),
        yaxis=dict(
            title="Consommation (ha)",
            gridcolor="rgba(255,255,255,0.06)",
            zeroline=False,
        ),
        hovermode="x unified",
    )

    return fig


# =====================================================
# ENTRÉE PUBLIQUE
# =====================================================

def rendu_graph_analyse(donnees):
    """
    Point d'entrée appelé depuis app_2.py dans l'onglet Analyse & Tendances.
    """

    st.subheader("📈 Analyse & Tendances")

    # ─── Sélecteur de trajectoire ────────────────────────
    labels   = [t[1] for t in TRAJECTOIRES]
    couleurs = [t[2] for t in TRAJECTOIRES]
    valeurs  = [t[0] for t in TRAJECTOIRES]

    col_sel, col_info = st.columns([2, 3])
    with col_sel:
        idx = st.selectbox(
            "🎯 Coefficient de réduction (objectif ZAN)",
            options=range(len(TRAJECTOIRES)),
            format_func=lambda i: labels[i],
            index=DEFAULT_INDEX,
            key="trajectoire_select",
        )
    coeff_reduction = valeurs[idx]
    couleur_traj    = couleurs[idx]

    with col_info:
        st.markdown(
            f"""
            <div style="
                background:rgba(255,255,255,0.04);
                border-radius:8px;
                padding:0.6rem 1rem;
                margin-top:1.6rem;
                border-left:3px solid {couleur_traj};
                font-size:0.9rem;
                color:#CFD8DC;
            ">
            Réduction appliquée : <strong style="color:{couleur_traj};">{fmt_pct(coeff_reduction*100)}</strong>
            &nbsp;|&nbsp; Objectif = consommation&nbsp;2011-2020 &times; <strong>{round(1-coeff_reduction,3)}</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()

    # ─── Calculs ─────────────────────────────────────────
    total_histo = _total_histo(donnees)
    total_obs   = _total_obs(donnees)
    objectif    = _objectif_total(total_histo, coeff_reduction)

    # ─── Cards ───────────────────────────────────────────
    _render_cards(total_histo, objectif, total_obs, coeff_reduction)

    # ─── Graphique ───────────────────────────────────────
    fig = _build_figure(donnees, coeff_reduction)
    st.plotly_chart(fig, use_container_width=True)

    # ─── Note de lecture ─────────────────────────────────
    st.caption(
        "Lignes pleines = consommation historique 2011-2020 · "
        "Tirets courts = valeurs observées 2021-2023 · "
        "Tirets longs = projection 2024-2030 basée sur le rythme 2021-2023 avec réduction appliquée"
    )
