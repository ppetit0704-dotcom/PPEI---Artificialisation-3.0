"""
@module  : graphs.graph_ratios
@author  : Philippe PETIT
@version : 2.0.0
@description : Module de ratios analytiques aligné sur lire_les_donnees().
               - Utilise les flux déjà calculés (activity, habitat, etc.)
               - S'appuie sur suffixes_ref / suffixes_zan
               - Compatible tous millésimes CEREMA
               - Sans emojis dans les chaînes Plotly (évite SyntaxError)
"""

import streamlit as st
import plotly.graph_objects as go
import numpy as np

from data.load_data import lire_les_donnees


# ───────────────────────────────────────────────────────────────
#  CONSTANTES
# ───────────────────────────────────────────────────────────────

ZAN_REDUCTION = 0.5   # -50 % de la conso 2011-2020
ZAN_DUREE     = 10    # horizon décennal

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


# ───────────────────────────────────────────────────────────────
#  UTILITAIRES
# ───────────────────────────────────────────────────────────────

def _safe(val, default=0.0):
    try:
        v = float(val)
        return v if not np.isnan(v) else default
    except Exception:
        return default


def _m2_to_ha(v):
    return v / 10_000 if v is not None else None


# ───────────────────────────────────────────────────────────────
#  RECONSTRUCTION DES FLUX (depuis lire_les_donnees)
# ───────────────────────────────────────────────────────────────

def construire_flux_depuis_donnees(donnees: dict):
    """
    Construit un dict {année_debut: {cat: m2, ..., "total": m2}}
    à partir des dicts activity/habitat/... et des suffixes_ref/zAN.
    """
    cats_map = {
        "activity":    "activite",
        "habitat":     "habitat",
        "mixte":       "mixte",
        "route":       "route",
        "ferroviaire": "ferroviaire",
        "inconnu":     "inconnu",
    }

    suffixes = donnees["suffixes_ref"] + donnees["suffixes_zan"]
    flux = {}

    for i, (a, b) in enumerate(suffixes):
        idx   = 3 + i
        annee = 2000 + int(a)

        flux[annee] = {}
        total = 0.0

        for key_src, key_dst in cats_map.items():
            d_cat = donnees[key_src]
            val   = _safe(d_cat.get(idx, 0.0))
            flux[annee][key_dst] = val
            total += val

        flux[annee]["total"] = total

    return flux


# ───────────────────────────────────────────────────────────────
#  TOTAUX PAR PÉRIODE
# ───────────────────────────────────────────────────────────────

def extraire_totaux_periodes(flux: dict, donnees: dict):
    cats = ["activite", "habitat", "mixte", "route", "ferroviaire", "inconnu", "total"]

    suffixes_ref = donnees["suffixes_ref"]
    suffixes_zan = donnees["suffixes_zan"]

    years_ref = [2000 + int(a) for (a, b) in suffixes_ref]
    years_zan = [2000 + int(a) for (a, b) in suffixes_zan]
    years_all = sorted(flux.keys())

    def _sum_on_years(years):
        return {c: sum(flux.get(y, {}).get(c, 0.0) for y in years) for c in cats}

    return {
        "total": _sum_on_years(years_all),
        "ref":   _sum_on_years(years_ref),
        "zan":   _sum_on_years(years_zan),
        "meta": {
            "years_all": years_all,
            "years_ref": years_ref,
            "years_zan": years_zan,
            "label_ref": f"{min(years_ref)}-{max(years_ref)}" if years_ref else "Référence",
            "label_zan": f"{min(years_zan)}-{max(years_zan)}" if years_zan else "ZAN",
        }
    }


# ───────────────────────────────────────────────────────────────
#  CALCUL DES RATIOS
# ───────────────────────────────────────────────────────────────

def calculer_ratios(ligne, flux, totaux):
    r = {}
    meta = totaux["meta"]

    pop1 = _safe(ligne.get("pop15", ligne.get("pop1", 0)))
    pop2 = _safe(ligne.get("pop21", ligne.get("pop2", 0)))
    pop_moy = (pop1 + pop2) / 2 if (pop1 + pop2) > 0 else None

    men1 = _safe(ligne.get("men15", ligne.get("men1", 0)))
    men2 = _safe(ligne.get("men21", ligne.get("men2", 0)))
    delta_men = men2 - men1

    emp1 = _safe(ligne.get("emp15", ligne.get("emp1", 0)))
    emp2 = _safe(ligne.get("emp21", ligne.get("emp2", 0)))
    delta_emp = emp2 - emp1

    surf_com = _safe(ligne.get("surfcom2024", ligne.get("surfcom", 0)))

    conso_total = totaux["total"]["total"]
    conso_ref   = totaux["ref"]["total"]
    conso_zan   = totaux["zan"]["total"]

    # Foncier / population
    r["label_ref"] = meta["label_ref"]
    r["label_zan"] = meta["label_zan"]

    r["m2_hab_total"] = conso_total / pop2 if pop2 > 0 else None
    r["m2_hab_ref"]   = conso_ref / pop_moy if pop_moy else None

    r["ha_par_1000hab"] = (conso_total / 10_000) / (pop2 / 1000) if pop2 > 0 else None

    r["rythme_m2_hab_ref"] = (
        r["m2_hab_ref"] / len(meta["years_ref"])
        if r["m2_hab_ref"] and meta["years_ref"] else None
    )
    r["rythme_m2_hab_zan"] = (
        (conso_zan / pop2) / len(meta["years_zan"])
        if pop2 > 0 and meta["years_zan"] else None
    )

    # Habitat
    hab_ref = totaux["ref"]["habitat"]
    r["m2_hab_par_menage"] = hab_ref / delta_men if delta_men > 0 else None
    r["ha_hab_par_menage"] = _m2_to_ha(r["m2_hab_par_menage"]) if r["m2_hab_par_menage"] else None

    r["part_habitat"]  = totaux["total"]["habitat"] / conso_total * 100 if conso_total > 0 else 0
    r["part_activite"] = totaux["total"]["activite"] / conso_total * 100 if conso_total > 0 else 0
    r["part_route"]    = totaux["total"]["route"] / conso_total * 100 if conso_total > 0 else 0
    r["part_mixte"]    = totaux["total"]["mixte"] / conso_total * 100 if conso_total > 0 else 0

    ha_hab = totaux["total"]["habitat"] / 10_000
    r["densite_resid"] = delta_men / ha_hab if ha_hab > 0 else None

    # Activité
    act_total = totaux["total"]["activite"]
    r["m2_act_par_emploi"] = act_total / delta_emp if delta_emp > 0 else None
    r["ha_act_par_emploi"] = _m2_to_ha(r["m2_act_par_emploi"]) if r["m2_act_par_emploi"] else None
    r["ratio_hab_act"]     = totaux["total"]["habitat"] / act_total if act_total > 0 else None

    # Surface communale
    r["pct_artificialise"]     = conso_total / surf_com * 100 if surf_com > 0 else None
    r["pct_artificialise_ref"] = conso_ref / surf_com * 100 if surf_com > 0 else None
    r["rythme_annuel_pct"]     = (
        r["pct_artificialise_ref"] / len(meta["years_ref"])
        if r["pct_artificialise_ref"] and meta["years_ref"] else None
    )
    r["surf_com_ha"] = surf_com / 10_000

    # ZAN
    enveloppe_zan = conso_ref * ZAN_REDUCTION
    r["enveloppe_zan_ha"] = enveloppe_zan / 10_000
    r["consomme_zan_ha"]  = conso_zan / 10_000
    r["restant_zan_ha"]   = (enveloppe_zan - conso_zan) / 10_000
    r["pct_enveloppe_utilisee"] = (
        conso_zan / enveloppe_zan * 100 if enveloppe_zan > 0 else None
    )

    rythme_zan_annuel = conso_zan / len(meta["years_zan"]) if meta["years_zan"] else 0
    restant_m2 = enveloppe_zan - conso_zan

    if rythme_zan_annuel > 0 and restant_m2 > 0:
        r["annees_avant_epuisement"] = restant_m2 / rythme_zan_annuel
    elif restant_m2 <= 0:
        r["annees_avant_epuisement"] = 0
    else:
        r["annees_avant_epuisement"] = None

    r["solde_zan_annuel_ha"] = (
        r["restant_zan_ha"] / 7 if r["restant_zan_ha"] is not None else None
    )

    return r


# ───────────────────────────────────────────────────────────────
#  HELPERS AFFICHAGE
# ───────────────────────────────────────────────────────────────

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


# ───────────────────────────────────────────────────────────────
#  GRAPHIQUES
# ───────────────────────────────────────────────────────────────

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
        title="Flux annuels de consommation foncière (ha/an)",
        xaxis_title="Année (flux, année de début)",
        yaxis_title="Hectares",
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
    fig.update_xaxes(tickmode="linear", dtick=1)
    return fig


def graph_donut_categories(totaux):
    periode = totaux["total"]
    cats   = ["habitat", "activite", "mixte", "route", "ferroviaire", "inconnu"]
    labels = ["Habitat", "Activité", "Mixte", "Route", "Ferroviaire", "Inconnu"]
    vals   = [periode[c] / 10_000 for c in cats]
    cols   = [COLORS[c] for c in cats]

    fig = go.Figure(go.Pie(
        labels=labels, values=vals,
        hole=0.55,
        marker=dict(colors=cols, line=dict(color="white", width=2)),
        textinfo="label+percent",
    ))
    fig.update_layout(
        title="Répartition par catégorie (tous flux disponibles)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
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


def graph_jauge_zan(r):
    pct = r["pct_enveloppe_utilisee"] or 0
    couleur = (
        COLORS["danger"] if pct >= 100 else
        COLORS["warning"] if pct >= 70 else
        COLORS["ok"]
    )

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=pct,
        number={"suffix": " %"},
        gauge={
            "axis": {"range": [0, 120]},
            "bar": {"color": couleur},
            "steps": [
                {"range": [0, 70],   "color": "#DCFCE7"},
                {"range": [70, 100], "color": "#FEF3C7"},
                {"range": [100, 120],"color": "#FEE2E2"},
            ],
        },
        title={"text": "Enveloppe ZAN utilisée"},
    ))
    fig.update_layout(
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


def graph_comparaison_rythmes(r):
    labels = [
        f"Rythme {r['label_ref']}",
        f"Rythme {r['label_zan']}",
    ]
    vals = [
        r["rythme_m2_hab_ref"] or 0,
        r["rythme_m2_hab_zan"] or 0,
    ]
    cols = [COLORS["total"], COLORS["habitat"]]

    fig = go.Figure(go.Bar(
        x=labels, y=vals,
        marker_color=cols,
        text=[f"{v:.1f} m²" for v in vals],
        textposition="outside",
    ))
    fig.update_layout(
        title="Rythme de consommation / habitant",
        yaxis_title="m² / habitant / an",
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

def graph_projection_zan(r):
    env_ha  = r["enveloppe_zan_ha"] or 0
    cons_ha = r["consomme_zan_ha"]  or 0

    # Rythme annuel moyen sur la période ZAN observée
    rythme = cons_ha / 4 if cons_ha > 0 else 0

    annees = list(range(2021, 2032))
    cumul  = [min(rythme * i, env_ha * 2) for i in range(len(annees))]

    fig = go.Figure()

    # Enveloppe ZAN max
    fig.add_trace(go.Scatter(
        x=annees,
        y=[env_ha] * len(annees),
        mode="lines",
        name="Enveloppe ZAN max",
        line=dict(color=COLORS["danger"], dash="dash")
    ))

    # Projection linéaire
    fig.add_trace(go.Scatter(
        x=annees,
        y=cumul,
        mode="lines+markers",
        name="Projection",
        line=dict(color=COLORS["warning"]),
        marker=dict(size=6)
    ))

    # Consommé réel 2021–2024
    fig.add_trace(go.Scatter(
        x=[2021, 2022, 2023, 2024],
        y=[rythme, rythme*2, rythme*3, cons_ha],
        mode="lines+markers",
        name="Consommé réel",
        line=dict(color=COLORS["total"], width=3),
        marker=dict(size=8)
    ))

    fig.update_layout(
        title="Projection de consommation ZAN jusqu'en 2031",
        xaxis_title="Année",
        yaxis_title="Hectares cumulés",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=360,
        margin=dict(t=60, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
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

    fig.update_xaxes(tickmode="linear", dtick=1)

    return fig

# ───────────────────────────────────────────────────────────────
#  RENDU PRINCIPAL STREAMLIT
# ───────────────────────────────────────────────────────────────

def rendu_ratios(code_insee):
    """Point d'entrée : appelé depuis app.py dans tab_ratio."""

    df = st.session_state.get("df")
    struct = st.session_state.get("struct")

    if df is None or struct is None:
        st.warning("Données ou structure non chargées.")
        return

    if not code_insee:
        st.info("Veuillez saisir un code INSEE dans le menu latéral.")
        return

    commune = df[df["idcom"] == code_insee]
    if commune.empty:
        st.warning("Aucune commune trouvée pour ce code INSEE.")
        return

    # Lecture dynamique via lire_les_donnees()
    ligne   = commune.iloc[0]
    donnees = lire_les_donnees(ligne, struct)
    flux    = construire_flux_depuis_donnees(donnees)
    totaux  = extraire_totaux_periodes(flux, donnees)
    r       = calculer_ratios(ligne, flux, totaux)

    nom = ligne.get("idcomtxt", code_insee)
    st.markdown(f"## Ratios analytiques — {code_insee} · {nom}")
    st.caption("Indicateurs calculés à partir des flux CEREMA (année de début).")
    st.divider()

    # ───────────────────────────────────────────────────────────
    # 1 — Foncier / Population
    # ───────────────────────────────────────────────────────────
    with st.expander("1 — Foncier & Population", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("m²/habitant (total)", _fm2(r["m2_hab_total"], 0))
        c2.metric(f"m²/habitant ({r['label_ref']})", _fm2(r["m2_hab_ref"], 0))
        c3.metric("ha / 1 000 hab", _fha(r["ha_par_1000hab"], 2))
        c4.metric("% territoire artificialisé", _fpct(r["pct_artificialise"], 2))

        st.markdown("---")
        c5, c6 = st.columns(2)
        c5.metric(
            f"Rythme {r['label_ref']} (m²/hab/an)",
            _fm2(r["rythme_m2_hab_ref"], 1)
        )
        c6.metric(
            f"Rythme {r['label_zan']} (m²/hab/an)",
            _fm2(r["rythme_m2_hab_zan"], 1)
        )

        col_g, col_d = st.columns(2)
        col_g.plotly_chart(graph_flux_annuel(flux), use_container_width=True)
        col_d.plotly_chart(graph_comparaison_rythmes(r), use_container_width=True)

    # ───────────────────────────────────────────────────────────
    # 2 — Habitat
    # ───────────────────────────────────────────────────────────
    with st.expander("2 — Habitat & Ménages", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Part habitat", _fpct(r["part_habitat"]))
        c2.metric("m² / nouveau ménage", _fm2(r["m2_hab_par_menage"], 0))
        c3.metric("ha / nouveau ménage", _fha(r["ha_hab_par_menage"], 3))
        c4.metric("Densité résidentielle", _fval(r["densite_resid"], " mén/ha", 1))

        col_g, col_d = st.columns(2)
        col_g.plotly_chart(graph_donut_categories(totaux), use_container_width=True)

        hab_annuel = [flux[a]["habitat"] / 10_000 for a in sorted(flux)]
        fig_hab = go.Figure(go.Bar(
            x=sorted(flux), y=hab_annuel,
            marker_color=COLORS["habitat"]
        ))
        fig_hab.update_layout(
            title="Consommation habitat annuelle",
            yaxis_title="ha",
            paper_bgcolor="rgba(0,0,0,0)"
        )

        fig_hab.update_layout(
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
        col_d.plotly_chart(fig_hab, use_container_width=True)

    # ───────────────────────────────────────────────────────────
    # 3 — Activité économique
    # ───────────────────────────────────────────────────────────
    with st.expander("3 — Activité économique & Emploi", expanded=False):
        c1, c2, c3 = st.columns(3)
        c1.metric("m² / emploi créé", _fm2(r["m2_act_par_emploi"], 0))
        c2.metric("ha / emploi créé", _fha(r["ha_act_par_emploi"], 3))
        c3.metric("Ratio habitat / activité", _fval(r["ratio_hab_act"], "x", 2))

        act_annuel = [flux[a]["activite"] / 10_000 for a in sorted(flux)]
        fig_act = go.Figure(go.Bar(
            x=sorted(flux), y=act_annuel,
            marker_color=COLORS["activite"]
        ))
        fig_act.update_layout(
            title="Consommation activité annuelle",
            yaxis_title="ha",
            paper_bgcolor="rgba(0,0,0,0)"
        )
        fig_act.update_layout(
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
        
        st.plotly_chart(fig_act, use_container_width=True)

    # ───────────────────────────────────────────────────────────
    # 4 — Surface communale
    # ───────────────────────────────────────────────────────────
    with st.expander("4 — Surface communale & Pression territoriale", expanded=False):
        surf_ha = r["surf_com_ha"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Surface communale", _fha(surf_ha, 0))
        c2.metric("% artificialisé (total)", _fpct(r["pct_artificialise"], 3))
        c3.metric(f"% artificialisé ({r['label_ref']})", _fpct(r["pct_artificialise_ref"], 3))
        c4.metric("Rythme annuel (‰)", _fval(
            (r["rythme_annuel_pct"] * 10) if r["rythme_annuel_pct"] else None,
            " ‰/an", 2))

        # Treemap
        cats_tm = ["Habitat", "Activité", "Mixte", "Route", "Ferroviaire", "Inconnu", "Non artif."]
        clés_tm = ["habitat", "activite", "mixte", "route", "ferroviaire", "inconnu"]
        vals_tm = [totaux["total"][k] / 10_000 for k in clés_tm]
        reste   = max(0, (surf_ha or 0) - sum(vals_tm))
        vals_tm.append(reste)
        cols_tm = [COLORS[k] for k in clés_tm] + ["#E5E7EB"]

        fig_tree = go.Figure(go.Treemap(
            labels=cats_tm,
            parents=[""] * len(cats_tm),
            values=vals_tm,
            marker=dict(colors=cols_tm),
        ))
        fig_tree.update_layout(
            title="Répartition du territoire communal (ha)",
            paper_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_tree, use_container_width=True)

    # ───────────────────────────────────────────────────────────
    # 5 — ZAN
    # ───────────────────────────────────────────────────────────
    with st.expander("5 — Indicateurs ZAN", expanded=True):
        pct_zan = r["pct_enveloppe_utilisee"]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Enveloppe ZAN", _fha(r["enveloppe_zan_ha"]))
        c2.metric(f"Consommé {r['label_zan']}", _fha(r["consomme_zan_ha"]))
        c3.metric("Solde restant", _fha(r["restant_zan_ha"]))
        c4.metric("Capacité annuelle restante", _fha(r["solde_zan_annuel_ha"]))

        col_j, col_p = st.columns([1, 2])
        col_j.plotly_chart(graph_jauge_zan(r), use_container_width=True)
        col_p.plotly_chart(graph_projection_zan(r), use_container_width=True)

        ans = r["annees_avant_epuisement"]
        if pct_zan is None:
            st.info("Données insuffisantes pour le bilan ZAN.")
        elif pct_zan >= 100:
            st.error(f"Enveloppe ZAN dépassée ({_fpct(pct_zan)}).")
        elif pct_zan >= 70:
            st.warning(f"{_fpct(pct_zan)} de l'enveloppe utilisée. "
                       f"Épuisement estimé dans ~{ans:.1f} ans.")
        else:
            st.success(f"{_fpct(pct_zan)} de l'enveloppe utilisée. "
                       f"Marge restante d'environ {ans:.1f} ans.")
