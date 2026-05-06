"""
@author : Philippe PETIT (module ratios généré avec Claude)
@version : 1.0.0
@description : Module de ratios analytiques pour le tableau de bord artificialisation.
               5 familles de ratios : Foncier/Pop, Habitat, Activité, Surface, ZAN.
"""

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import streamlit as st
import numpy as np


# ─────────────────────────────────────────────────────────────────
#  CONSTANTES
# ─────────────────────────────────────────────────────────────────

ANNEES = list(range(2010, 2025))          # années disponibles (flux annuels)
PERIODE_REF = list(range(2011, 2021))     # 2011-2020  (décennie de référence ZAN)
PERIODE_ZAN = list(range(2021, 2025))     # 2021-2024  (période de comptage ZAN)

# Objectif ZAN : réduire de 50 % la conso 2011-2020 sur la décennie 2021-2031
ZAN_REDUCTION = 0.5
ZAN_DUREE = 10   # ans (2021-2031)

COLORS = {
    "habitat":     "#3B82F6",
    "activite":    "#F59E0B",
    "mixte":       "#8B5CF6",
    "route":       "#6B7280",
    "ferroviaire": "#EC4899",
    "inconnu":     "#D1D5DB",
    "total":       "#10B981",
    "danger":      "#EF4444",
    "warning":     "#F97316",
    "ok":          "#22C55E",
}


# ─────────────────────────────────────────────────────────────────
#  EXTRACTION DES DONNÉES DEPUIS UNE LIGNE DU DATAFRAME
# ─────────────────────────────────────────────────────────────────

def _safe(val, default=0.0):
    try:
        v = float(val)
        return v if not np.isnan(v) else default
    except (TypeError, ValueError):
        return default


def extraire_flux_annuels(ligne):
    """
    Retourne un dict {annee: {cat: m2}} pour chaque année 2010-2024.
    Les colonnes suivent le patron : art{YY}{cat}{YY+1}
    ex : art09hab10 → habitat consommé entre 2009 et 2010.
    """
    cats = {"act": "activite", "hab": "habitat", "mix": "mixte",
            "rou": "route",   "fer": "ferroviaire", "inc": "inconnu"}
    flux = {}
    for debut in range(9, 24):      # 09 → 23  (i.e. 2009→2010  … 2023→2024)
        an_fin = debut + 1
        annee = 2000 + an_fin
        flux[annee] = {}
        for code, label in cats.items():
            col = f"art{debut:02d}{code}{an_fin:02d}"
            flux[annee][label] = _safe(ligne.get(col, 0))
        flux[annee]["total"] = sum(flux[annee].values())
    return flux


def extraire_totaux_periodes(flux):
    """
    Somme par catégorie sur différentes périodes.
    Correspondance avec load_data.py / graph_analyse.py :
      - Référence (indices 3-12) : art11xxx12→flux[2012] … art20xxx21→flux[2021]
      - ZAN      (indices 13-15) : art21xxx22→flux[2022] … art23xxx24→flux[2024]
    """
    periodes = {
        "2009-2024": range(2010, 2025),
        "2011-2020": range(2012, 2022),   # ← corrigé (était range(2011,2021))
        "2021-2024": range(2022, 2025),   # ← corrigé (était range(2021,2025))
    }
    cats = ["activite", "habitat", "mixte", "route", "ferroviaire", "inconnu", "total"]
    result = {}
    for label, ans in periodes.items():
        result[label] = {c: sum(flux.get(a, {}).get(c, 0) for a in ans) for c in cats}
    return result


# ─────────────────────────────────────────────────────────────────
#  CALCUL DES RATIOS
# ─────────────────────────────────────────────────────────────────

def calculer_ratios(ligne, flux, totaux):
    r = {}
    m2ha = 10_000

    pop15   = _safe(ligne.get("pop15", 0))
    pop21   = _safe(ligne.get("pop21", 0))
    pop_moy = (pop15 + pop21) / 2 if (pop15 + pop21) > 0 else None

    men15   = _safe(ligne.get("men15", 0))
    men21   = _safe(ligne.get("men21", 0))
    delta_men = men21 - men15

    emp15   = _safe(ligne.get("emp15", 0))
    emp21   = _safe(ligne.get("emp21", 0))
    delta_emp = emp21 - emp15

    surf_com = _safe(ligne.get("surfcom2024", 0))  # m²

    conso_total   = totaux["2009-2024"]["total"]
    conso_2011_20 = totaux["2011-2020"]["total"]
    conso_2021_24 = totaux["2021-2024"]["total"]

    # ── 1. Foncier / Population ──────────────────────────────────
    r["m2_hab_total"]    = conso_total / pop21 if pop21 > 0 else None
    r["m2_hab_ref"]      = conso_2011_20 / pop_moy if pop_moy else None
    r["ha_par_1000hab"]  = (conso_total / m2ha) / (pop21 / 1000) if pop21 > 0 else None

    # Rythme annuel (m²/hab/an)
    r["rythme_m2_hab_ref"]  = r["m2_hab_ref"] / 10 if r["m2_hab_ref"] else None
    r["rythme_m2_hab_zan"]  = (conso_2021_24 / pop21) / 4 if pop21 > 0 else None

    # ── 2. Habitat ───────────────────────────────────────────────
    hab_2015_21 = totaux["2011-2020"]["habitat"]   # proxy période ménages
    r["m2_hab_par_menage"]  = hab_2015_21 / delta_men if delta_men > 0 else None
    r["ha_hab_par_menage"]  = r["m2_hab_par_menage"] / m2ha if r["m2_hab_par_menage"] else None
    r["part_habitat"]       = totaux["2009-2024"]["habitat"] / conso_total * 100 if conso_total > 0 else 0
    r["part_activite"]      = totaux["2009-2024"]["activite"] / conso_total * 100 if conso_total > 0 else 0
    r["part_route"]         = totaux["2009-2024"]["route"] / conso_total * 100 if conso_total > 0 else 0
    r["part_mixte"]         = totaux["2009-2024"]["mixte"] / conso_total * 100 if conso_total > 0 else 0

    # Densité résidentielle implicite (ménages/ha hab)
    ha_hab = totaux["2009-2024"]["habitat"] / m2ha
    r["densite_resid"]  = delta_men / ha_hab if ha_hab > 0 else None

    # ── 3. Activité économique ───────────────────────────────────
    act_total = totaux["2009-2024"]["activite"]
    r["m2_act_par_emploi"]  = act_total / delta_emp if delta_emp > 0 else None
    r["ha_act_par_emploi"]  = r["m2_act_par_emploi"] / m2ha if r["m2_act_par_emploi"] else None
    r["ratio_hab_act"]      = totaux["2009-2024"]["habitat"] / act_total if act_total > 0 else None

    # ── 4. Surface communale ─────────────────────────────────────
    r["pct_artificialise"]  = conso_total / surf_com * 100 if surf_com > 0 else None
    r["pct_artificialise_ref"] = conso_2011_20 / surf_com * 100 if surf_com > 0 else None
    r["rythme_annuel_pct"]  = r["pct_artificialise_ref"] / 10 if r["pct_artificialise_ref"] else None
    r["surf_com_ha"]        = surf_com / m2ha

    # ── 5. ZAN ───────────────────────────────────────────────────
    # Enveloppe autorisée 2021-2031 = 50 % de la conso 2011-2020
    enveloppe_zan = conso_2011_20 * ZAN_REDUCTION
    r["enveloppe_zan_ha"]  = enveloppe_zan / m2ha
    r["consomme_zan_ha"]   = conso_2021_24 / m2ha
    r["restant_zan_ha"]    = (enveloppe_zan - conso_2021_24) / m2ha
    r["pct_enveloppe_utilisee"] = conso_2021_24 / enveloppe_zan * 100 if enveloppe_zan > 0 else None

    # Rythme moyen annuel période ZAN (4 ans de données)
    rythme_zan_annuel = conso_2021_24 / 4
    # Années restantes avant épuisement (2031 - 2024 = 7 ans restants pour se conformer)
    r["annees_restantes_zan"] = 7  # années restantes jusqu'en 2031
    r["solde_zan_annuel_ha"]  = r["restant_zan_ha"] / 7 if r["restant_zan_ha"] is not None else None

    # Projection : épuisement au rythme actuel ?
    restant_m2 = enveloppe_zan - conso_2021_24
    if rythme_zan_annuel > 0 and restant_m2 > 0:
        r["annees_avant_epuisement"] = restant_m2 / rythme_zan_annuel
    elif restant_m2 <= 0:
        r["annees_avant_epuisement"] = 0
    else:
        r["annees_avant_epuisement"] = 99

    # Score ZAN global (0-100)
    pct = r["pct_enveloppe_utilisee"] or 0
    r["score_zan"] = max(0, 100 - pct)

    return r


# ─────────────────────────────────────────────────────────────────
#  HELPERS AFFICHAGE
# ─────────────────────────────────────────────────────────────────

def _fha(v, dec=2):
    if v is None: return "N/D"
    return f"{v:,.{dec}f}".replace(",", "\u202f").replace(".", ",") + " ha"

def _fm2(v, dec=0):
    if v is None: return "N/D"
    return f"{v:,.{dec}f}".replace(",", "\u202f").replace(".", ",") + " m²"

def _fpct(v, dec=1):
    if v is None: return "N/D"
    return f"{v:.{dec}f} %".replace(".", ",")

def _fval(v, unit="", dec=1):
    if v is None: return "N/D"
    return f"{v:.{dec}f}{unit}".replace(".", ",")

def couleur_alerte(pct):
    if pct is None: return COLORS["ok"]
    if pct >= 100: return COLORS["danger"]
    if pct >= 70:  return COLORS["warning"]
    return COLORS["ok"]

def emoji_alerte(pct):
    if pct is None: return "⚪"
    if pct >= 100: return "🔴"
    if pct >= 70:  return "🟠"
    return "🟢"


# ─────────────────────────────────────────────────────────────────
#  GRAPHIQUES PLOTLY
# ─────────────────────────────────────────────────────────────────

def graph_flux_annuel(flux):
    annees = sorted(flux.keys())
    cats = ["habitat", "activite", "mixte", "route", "ferroviaire", "inconnu"]
    labels = ["Habitat", "Activité", "Mixte", "Route", "Ferroviaire", "Inconnu"]
    couleurs = [COLORS[c] for c in cats]

    fig = go.Figure()
    for cat, label, col in zip(cats, labels, couleurs):
        vals = [flux[a][cat] / 10_000 for a in annees]
        fig.add_trace(go.Bar(name=label, x=annees, y=vals, marker_color=col))

    fig.update_layout(
        barmode="stack",
        title="📅 Flux annuels de consommation foncière (ha/an)",
        xaxis_title="Année",
        yaxis_title="Hectares",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=380,
        margin=dict(t=60, b=40),
    )
    fig.update_xaxes(tickmode="linear", dtick=1)
    return fig


def graph_donut_categories(totaux):
    periode = totaux["2009-2024"]
    cats   = ["habitat", "activite", "mixte", "route", "ferroviaire", "inconnu"]
    labels = ["Habitat", "Activité", "Mixte", "Route", "Ferroviaire", "Inconnu"]
    vals   = [periode[c] / 10_000 for c in cats]
    cols   = [COLORS[c] for c in cats]

    fig = go.Figure(go.Pie(
        labels=labels, values=vals,
        hole=0.55,
        marker=dict(colors=cols, line=dict(color="white", width=2)),
        textinfo="label+percent",
        hovertemplate="%{label}<br>%{value:.2f} ha<br>%{percent}<extra></extra>",
    ))
    fig.update_layout(
        title="🗂️ Répartition par catégorie (2009-2024)",
        height=340,
        margin=dict(t=50, b=20, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    return fig


def graph_jauge_zan(r):
    pct = r["pct_enveloppe_utilisee"] or 0
    couleur = couleur_alerte(pct)

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=pct,
        number={"suffix": " %", "font": {"size": 36}},
        delta={"reference": 50, "valueformat": ".1f",
               "increasing": {"color": COLORS["danger"]},
               "decreasing": {"color": COLORS["ok"]}},
        gauge={
            "axis": {"range": [0, 120], "tickwidth": 1},
            "bar": {"color": couleur},
            "steps": [
                {"range": [0, 70],   "color": "#DCFCE7"},
                {"range": [70, 100], "color": "#FEF3C7"},
                {"range": [100, 120],"color": "#FEE2E2"},
            ],
            "threshold": {
                "line": {"color": COLORS["danger"], "width": 4},
                "thickness": 0.75, "value": 100
            },
        },
        title={"text": "Enveloppe ZAN utilisée (2021-2024 / objectif 2021-2031)", "font": {"size": 14}},
    ))
    fig.update_layout(
        height=300,
        margin=dict(t=40, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def graph_comparaison_rythmes(r):
    rythmes = {
        "Rythme 2011-2020<br>(m²/hab/an)": r["rythme_m2_hab_ref"],
        "Rythme 2021-2024<br>(m²/hab/an)": r["rythme_m2_hab_zan"],
    }
    labels = list(rythmes.keys())
    vals   = [v if v else 0 for v in rythmes.values()]
    cols   = [COLORS["total"], COLORS["habitat"]]

    fig = go.Figure(go.Bar(
        x=labels, y=vals,
        marker_color=cols,
        text=[f"{v:.1f} m²" for v in vals],
        textposition="outside",
    ))
    fig.update_layout(
        title="⚡ Rythme de conso / habitant — Comparaison des périodes",
        yaxis_title="m² / habitant / an",
        height=340,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=50, b=40),
    )
    return fig


def graph_projection_zan(r):
    """Timeline ZAN avec enveloppe, consommé, projeté."""
    env_ha  = r["enveloppe_zan_ha"] or 0
    cons_ha = r["consomme_zan_ha"]  or 0
    rythme  = cons_ha / 4           # ha/an sur 4 ans

    annees = list(range(2021, 2032))
    cumul  = []
    for i, an in enumerate(annees):
        v = min(rythme * i, env_ha * 2)   # projection linéaire
        cumul.append(v)

    # Point réel (2024 = index 3)
    cumul_reel = [None] * len(annees)
    cumul_reel[3] = cons_ha

    fig = go.Figure()

    # Zone enveloppe
    fig.add_trace(go.Scatter(
        x=annees, y=[env_ha] * len(annees),
        mode="lines", name="Enveloppe ZAN max",
        line=dict(color=COLORS["danger"], dash="dash", width=2),
        fill=None,
    ))

    # Projection
    fig.add_trace(go.Scatter(
        x=annees, y=cumul,
        mode="lines+markers", name="Projection au rythme actuel",
        line=dict(color=COLORS["warning"], width=2),
        marker=dict(size=5),
    ))

    # Réel
    fig.add_trace(go.Scatter(
        x=[2021, 2022, 2023, 2024],
        y=[rythme, rythme*2, rythme*3, cons_ha],
        mode="lines+markers", name="Consommé réel 2021-2024",
        line=dict(color=COLORS["total"], width=3),
        marker=dict(size=8, symbol="circle"),
    ))

    fig.update_layout(
        title="📈 Projection de consommation ZAN jusqu'en 2031",
        xaxis_title="Année", yaxis_title="Hectares cumulés",
        height=360,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=60, b=40),
    )
    fig.update_xaxes(tickmode="linear", dtick=1)
    return fig


# ─────────────────────────────────────────────────────────────────
#  RENDU PRINCIPAL
# ─────────────────────────────────────────────────────────────────

def rendu_ratios(code_insee):
    """Point d'entrée : appelé depuis app.py dans tab_ratio."""

    df = st.session_state.get("df")
    if df is None:
        st.warning("Données non chargées.")
        return

    if not code_insee:
        st.info("Veuillez saisir un code INSEE dans le menu latéral.")
        return

    commune = df[df["idcom"] == code_insee]
    if commune.empty:
        st.warning("Aucune commune trouvée pour ce code INSEE.")
        return

    ligne   = commune.iloc[0]
    flux    = extraire_flux_annuels(ligne)
    totaux  = extraire_totaux_periodes(flux)
    r       = calculer_ratios(ligne, flux, totaux)

    nom = ligne.get("idcomtxt", code_insee)
    st.markdown(f"## 📐 Ratios analytiques — {code_insee} · {nom}")
    st.caption("Tous les indicateurs sont calculés à partir des données CEREMA / flux NAF.")
    st.divider()

    # ══════════════════════════════════════════════════════════════
    # FAMILLE 1 — Foncier / Population
    # ══════════════════════════════════════════════════════════════
    with st.expander("🏗️ 1 — Foncier & Population", expanded=True):
        st.markdown("##### Consommation foncière rapportée aux habitants")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("m²/habitant (total 2009-2024)",    _fm2(r["m2_hab_total"], 0))
        c2.metric("m²/habitant (2011-2020)",           _fm2(r["m2_hab_ref"], 0))
        c3.metric("ha/1 000 hab (total)",              _fha(r["ha_par_1000hab"], 2))
        c4.metric("% territoire communal artificiali.", _fpct(r["pct_artificialise"], 2))

        st.markdown("---")
        st.markdown("##### Rythme annuel de consommation / habitant")
        c5, c6 = st.columns(2)
        c5.metric(
            "Rythme moyen 2011-2020 (m²/hab/an)",
            _fm2(r["rythme_m2_hab_ref"], 1),
            help="Consommation de la décennie de référence divisée par 10 ans et par la population moyenne."
        )
        c6.metric(
            "Rythme moyen 2021-2024 (m²/hab/an)",
            _fm2(r["rythme_m2_hab_zan"], 1),
            delta=f"{((r['rythme_m2_hab_zan'] or 0) - (r['rythme_m2_hab_ref'] or 0)):+.1f} m²/hab/an"
            if r["rythme_m2_hab_ref"] and r["rythme_m2_hab_zan"] else None,
            delta_color="inverse",
            help="Rythme de la période ZAN (2021-2024) — doit diminuer par rapport à la décennie de référence."
        )

        col_g, col_d = st.columns(2)
        col_g.plotly_chart(graph_flux_annuel(flux), use_container_width=True)
        col_d.plotly_chart(graph_comparaison_rythmes(r), use_container_width=True)

    # ══════════════════════════════════════════════════════════════
    # FAMILLE 2 — Habitat
    # ══════════════════════════════════════════════════════════════
    with st.expander("🏠 2 — Habitat & Ménages", expanded=True):
        st.markdown("##### Efficacité résidentielle")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Part habitat / conso totale",       _fpct(r["part_habitat"]))
        c2.metric("m²/nouveau ménage (2011-2020)",     _fm2(r["m2_hab_par_menage"], 0),
                  help="Surface habitat consommée 2011-2020 divisée par le nombre de nouveaux ménages créés 2015-2021.")
        c3.metric("ha/nouveau ménage",                 _fha(r["ha_hab_par_menage"], 3))
        c4.metric("Densité résidentielle implicite",   _fval(r["densite_resid"], " mén/ha", 1),
                  help="Nouveaux ménages / hectares d'habitat artificialisés (2009-2024). Référence : > 20 = dense.")

        # Interprétation densité
        dens = r["densite_resid"]
        if dens is not None:
            if dens >= 20:
                st.success(f"✅ Densité résidentielle correcte ({dens:.1f} mén/ha) — territoire bien valorisé.")
            elif dens >= 10:
                st.warning(f"⚠️ Densité résidentielle moyenne ({dens:.1f} mén/ha) — vigilance sur l'étalement.")
            else:
                st.error(f"🔴 Densité très faible ({dens:.1f} mén/ha) — fort étalement résidentiel.")

        col_g, col_d = st.columns(2)
        col_g.plotly_chart(graph_donut_categories(totaux), use_container_width=True)

        # Graphique évolution pop vs conso habitat
        hab_annuel = [flux[a]["habitat"] / 10_000 for a in sorted(flux)]
        fig_hab = go.Figure()
        fig_hab.add_trace(go.Bar(
            x=sorted(flux), y=hab_annuel,
            name="Conso habitat (ha/an)",
            marker_color=COLORS["habitat"],
        ))
        fig_hab.update_layout(
            title="🏠 Consommation habitat annuelle",
            yaxis_title="ha", height=340,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=50, b=40),
        )
        fig_hab.update_xaxes(tickmode="linear", dtick=1)
        col_d.plotly_chart(fig_hab, use_container_width=True)

    # ══════════════════════════════════════════════════════════════
    # FAMILLE 3 — Activité économique
    # ══════════════════════════════════════════════════════════════
    with st.expander("🏭 3 — Activité économique & Emploi", expanded=False):
        st.markdown("##### Coût foncier de l'emploi")
        c1, c2, c3 = st.columns(3)
        c1.metric("m²/emploi créé (2015-2021)",        _fm2(r["m2_act_par_emploi"], 0),
                  help="Surface activité consommée 2009-2024 / variation d'emplois 2015-2021.")
        c2.metric("ha/emploi créé",                    _fha(r["ha_act_par_emploi"], 3))
        c3.metric("Ratio habitat/activité",             _fval(r["ratio_hab_act"], "x", 2),
                  help="> 1 : prédominance résidentielle. < 1 : commune à dominante économique.")

        delta_emp = _safe(ligne.get("emp21", 0)) - _safe(ligne.get("emp15", 0))
        signe = "+" if delta_emp >= 0 else ""
        if delta_emp == 0:
            st.info("ℹ️ Aucune variation d'emploi entre 2015 et 2021 — ratio m²/emploi non calculable.")
        elif delta_emp < 0:
            st.warning(f"⚠️ Perte d'emplois détectée ({signe}{int(delta_emp)}) sur 2015-2021 — "
                       "interpréter les ratios activité avec prudence.")

        # Graphique évolution conso activité
        act_annuel = [flux[a]["activite"] / 10_000 for a in sorted(flux)]
        fig_act = go.Figure(go.Bar(
            x=sorted(flux), y=act_annuel,
            marker_color=COLORS["activite"],
        ))
        fig_act.update_layout(
            title="🏭 Consommation activité annuelle (ha)",
            yaxis_title="ha", height=320,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=50, b=40),
        )
        fig_act.update_xaxes(tickmode="linear", dtick=1)
        st.plotly_chart(fig_act, use_container_width=True)

    # ══════════════════════════════════════════════════════════════
    # FAMILLE 4 — Surface communale
    # ══════════════════════════════════════════════════════════════
    with st.expander("📏 4 — Surface communale & Pression territoriale", expanded=False):
        surf_ha = r["surf_com_ha"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Surface communale",           _fha(surf_ha, 0))
        c2.metric("% artificiali. 2009-2024",    _fpct(r["pct_artificialise"], 3))
        c3.metric("% artificiali. 2011-2020",    _fpct(r["pct_artificialise_ref"], 3))
        c4.metric("Rythme annuel moyen (‰ surf)", _fval(
            (r["pct_artificialise_ref"] / 10 * 10) if r["pct_artificialise_ref"] else None,
            " ‰/an", 2))

        # Treemap des catégories
        cats_tm   = ["Habitat", "Activité", "Mixte", "Route", "Ferroviaire", "Inconnu", "Non artif."]
        clés_tm   = ["habitat", "activite", "mixte", "route", "ferroviaire", "inconnu"]
        vals_tm   = [totaux["2009-2024"][k] / 10_000 for k in clés_tm]
        reste     = max(0, (surf_ha or 0) - sum(vals_tm))
        vals_tm.append(reste)
        cols_tm   = [COLORS[k] for k in clés_tm] + ["#E5E7EB"]

        fig_tree = go.Figure(go.Treemap(
            labels=cats_tm,
            parents=[""] * len(cats_tm),
            values=vals_tm,
            marker=dict(colors=cols_tm),
            texttemplate="%{label}<br>%{value:.2f} ha<br>%{percentRoot:.1%}",
        ))
        fig_tree.update_layout(
            title="🗺️ Répartition du territoire communal (ha)",
            height=380,
            margin=dict(t=50, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_tree, use_container_width=True)

    # ══════════════════════════════════════════════════════════════
    # FAMILLE 5 — ZAN
    # ══════════════════════════════════════════════════════════════
    with st.expander("⚡ 5 — Indicateurs ZAN (Zéro Artificialisation Nette)", expanded=True):
        pct_zan = r["pct_enveloppe_utilisee"]
        emoji   = emoji_alerte(pct_zan)

        st.markdown(f"### {emoji} Bilan ZAN 2021-2031 — situation au 31/12/2024")
        st.caption(
            "L'objectif ZAN (loi Climat et Résilience 2021) impose de réduire la consommation "
            "foncière de **50 %** sur 2021-2031 par rapport à la décennie de référence 2011-2020."
        )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Enveloppe ZAN 2021-2031",    _fha(r["enveloppe_zan_ha"]))
        c2.metric("Consommé 2021-2024",         _fha(r["consomme_zan_ha"]))
        c3.metric("Solde restant",              _fha(r["restant_zan_ha"]),
                  delta=f"{(r['restant_zan_ha'] or 0):+.2f} ha",
                  delta_color="normal")
        c4.metric("Capacité annuelle restante", _fha(r["solde_zan_annuel_ha"]),
                  help="Solde / 7 années restantes jusqu'en 2031")

        col_j, col_p = st.columns([1, 2])
        col_j.plotly_chart(graph_jauge_zan(r), use_container_width=True)
        col_p.plotly_chart(graph_projection_zan(r), use_container_width=True)

        # Message d'alerte contextuel
        ans = r["annees_avant_epuisement"]
        if pct_zan is None:
            st.info("Données insuffisantes pour calculer le bilan ZAN.")
        elif pct_zan >= 100:
            st.error(
                f"🔴 **Enveloppe ZAN dépassée !** La commune a consommé {_fpct(pct_zan)} "
                "de son quota autorisé sur 2021-2031. Une révision de la stratégie foncière est urgente."
            )
        elif pct_zan >= 70:
            st.warning(
                f"🟠 **Vigilance ZAN.** {_fpct(pct_zan)} de l'enveloppe est utilisée en seulement 4 ans. "
                f"Au rythme actuel, l'enveloppe sera épuisée dans **{ans:.1f} ans** (vers {2024 + ans:.0f})."
            )
        else:
            st.success(
                f"🟢 **Situation ZAN satisfaisante.** {_fpct(pct_zan)} de l'enveloppe utilisée. "
                f"Au rythme actuel, la commune dispose encore de **{ans:.1f} ans** d'enveloppe."
            )

        # Tableau de synthèse ZAN
        st.markdown("##### 📋 Tableau de synthèse ZAN")
        zan_data = {
            "Indicateur": [
                "Conso. de référence 2011-2020",
                "Enveloppe ZAN max 2021-2031 (−50 %)",
                "Consommé 2021-2024 (4 ans)",
                "Solde disponible 2025-2031",
                "Capacité annuelle résiduelle",
                "% enveloppe utilisée",
                "Projection épuisement",
            ],
            "Valeur": [
                _fha(r["enveloppe_zan_ha"] * 2),
                _fha(r["enveloppe_zan_ha"]),
                _fha(r["consomme_zan_ha"]),
                _fha(r["restant_zan_ha"]),
                _fha(r["solde_zan_annuel_ha"]),
                _fpct(r["pct_enveloppe_utilisee"]),
                f"~{2024 + (r['annees_avant_epuisement'] or 0):.0f}" if (r["annees_avant_epuisement"] or 0) < 50 else "Avant 2031 ✓",
            ]
        }
        st.dataframe(pd.DataFrame(zan_data), use_container_width=True, hide_index=True)
