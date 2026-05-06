"""
@author  : Philippe PETIT
@version : 1.0.0
@description : Module d'agrégation intercommunale — Onglet Ratios EPCI.
               Mêmes 5 familles de ratios que graph_ratios.py mais à l'échelle CC.
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st

from graphs.graph_epci_general import (
    agreger_epci,
    agreger_flux_annuels,
    _fha,
    _fpct,
    _fint,
)


# ─────────────────────────────────────────────────────────────────
#  CONSTANTES
# ─────────────────────────────────────────────────────────────────

TRAJECTOIRES = [
    (0.625, "62,5 %"), (0.620, "62,0 %"), (0.615, "61,5 %"),
    (0.610, "61,0 %"), (0.607, "60,7 % — SRADDET Occitanie"),
    (0.605, "60,5 %"), (0.600, "60,0 %"), (0.575, "57,5 %"),
    (0.550, "55,0 %"), (0.525, "52,5 %"), (0.500, "50,0 % — Loi Climat"),
    (0.475, "47,5 %"), (0.450, "45,0 %"), (0.425, "42,5 %"),
    (0.400, "40,0 %"), (0.375, "37,5 %"),
]

COLORS = {
    "habitat":     "#3B82F6",
    "activite":    "#F59E0B",
    "mixte":       "#8B5CF6",
    "route":       "#6B7280",
    "ferroviaire": "#EC4899",
    "inconnu":     "#D1D5DB",
    "total":       "#10B981",
    "ok":          "#22C55E",
    "warning":     "#F97316",
    "danger":      "#EF4444",
}


# ─────────────────────────────────────────────────────────────────
#  FORMATAGE
# ─────────────────────────────────────────────────────────────────

def _fm2(v, dec=0):
    if v is None: return "N/D"
    return f"{v:,.{dec}f} m2".replace(",", " ").replace(".", ",")

def _fval(v, unit="", dec=1):
    if v is None: return "N/D"
    return f"{v:.{dec}f} {unit}".replace(".", ",").strip()

def _couleur_alerte(pct):
    if pct is None: return COLORS["ok"]
    if pct >= 100:  return COLORS["danger"]
    if pct >= 70:   return COLORS["warning"]
    return COLORS["ok"]

def _emoji_alerte(pct):
    if pct is None: return "⚪"
    if pct >= 100:  return "🔴"
    if pct >= 70:   return "🟠"
    return "🟢"


# ─────────────────────────────────────────────────────────────────
#  CALCUL DES RATIOS EPCI
# ─────────────────────────────────────────────────────────────────

def calculer_ratios_epci(agg: dict, coeff_reduction: float) -> dict:
    """Calcule tous les ratios à partir du dict agrégé."""
    m2ha      = 10_000
    pop21     = agg["pop21"]
    pop_moy   = (agg["pop15"] + agg["pop21"]) / 2 if (agg["pop15"] + agg["pop21"]) > 0 else None
    delta_men = agg["delta_men"]
    delta_emp = agg["delta_emp"]
    surf_ha   = agg["surf_ha"]

    # Consommations en m²
    ct  = agg["conso_tot_ha"]  * m2ha
    c20 = agg["conso_ref_ha"]  * m2ha
    c24 = agg["conso_zan_ha"]  * m2ha

    r = {}

    # ── 1. Foncier / Population ──────────────────────────────────
    r["m2_hab_total"]      = ct  / pop21   if pop21   > 0 else None
    r["m2_hab_ref"]        = c20 / pop_moy if pop_moy else None
    r["rythme_m2_hab_ref"] = r["m2_hab_ref"] / 10 if r["m2_hab_ref"] else None
    r["rythme_m2_hab_zan"] = (c24 / pop21)  / 4   if pop21 > 0       else None
    r["ha_par_1000hab"]    = (ct / m2ha) / (pop21 / 1000) if pop21 > 0 else None
    r["pct_artificialise"] = agg["pct_artificialise"]

    # ── 2. Habitat ───────────────────────────────────────────────
    hab_ref    = agg["totaux"]["habitat"]["ref"]
    hab_tot    = agg["totaux"]["habitat"]["total"]
    r["m2_hab_par_menage"] = hab_ref / delta_men if delta_men > 0 else None
    r["ha_hab_par_menage"] = r["m2_hab_par_menage"] / m2ha if r["m2_hab_par_menage"] else None
    r["densite_resid"]     = delta_men / (hab_tot / m2ha) if hab_tot > 0 else None
    r["part_habitat"]      = agg["part_habitat"]
    r["part_activite"]     = agg["part_activite"]
    r["part_route"]        = agg["part_route"]

    # ── 3. Activité / Emploi ─────────────────────────────────────
    act_tot = agg["totaux"]["activite"]["total"]
    r["m2_act_par_emploi"] = act_tot / delta_emp if delta_emp > 0 else None
    r["ha_act_par_emploi"] = r["m2_act_par_emploi"] / m2ha if r["m2_act_par_emploi"] else None
    r["ratio_hab_act"]     = hab_tot / act_tot if act_tot > 0 else None
    r["delta_emp"]         = delta_emp

    # ── 4. Surface communale ─────────────────────────────────────
    r["surf_com_ha"]           = surf_ha
    r["pct_artificialise_ref"] = (c20 / (surf_ha * m2ha) * 100) if surf_ha > 0 else None

    # ── 5. ZAN ───────────────────────────────────────────────────
    env = c20 * (1.0 - coeff_reduction)
    r["enveloppe_zan_ha"]       = env / m2ha
    r["consomme_zan_ha"]        = c24 / m2ha
    r["restant_zan_ha"]         = (env - c24) / m2ha
    r["pct_enveloppe_utilisee"] = c24 / env * 100 if env > 0 else None
    r["solde_zan_annuel_ha"]    = r["restant_zan_ha"] / 7 if r["restant_zan_ha"] else None
    r["coeff_reduction"]        = coeff_reduction

    rythme_zan = c24 / 4
    restant    = env - c24
    r["annees_avant_epuisement"] = (
        restant / rythme_zan if rythme_zan > 0 and restant > 0
        else (0 if restant <= 0 else 99)
    )

    return r


# ─────────────────────────────────────────────────────────────────
#  GRAPHIQUES
# ─────────────────────────────────────────────────────────────────

def _graph_flux(flux: dict) -> go.Figure:
    annees = sorted(flux.keys())
    cats   = ["habitat", "activite", "mixte", "route", "ferroviaire", "inconnu"]
    labels = ["Habitat", "Activité", "Mixte", "Route", "Ferroviaire", "Inconnu"]
    fig = go.Figure()
    for cat, label in zip(cats, labels):
        fig.add_trace(go.Bar(
            name=label, x=annees,
            y=[flux[a][cat] / 10_000 for a in annees],
            marker_color=COLORS[cat],
        ))
    fig.update_layout(
        barmode="stack",
        title="Flux annuels agrégés CC (ha/an)",
        xaxis=dict(tickmode="linear", dtick=1, tickangle=-45),
        yaxis_title="Hectares",
        legend=dict(orientation="h", y=1.15),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        height=360, margin=dict(l=50, r=10, t=60, b=50),
    )
    return fig


def _graph_rythmes(r: dict) -> go.Figure:
    labels = ["Rythme 2011-2020\n(m2/hab/an)", "Rythme 2021-2024\n(m2/hab/an)"]
    vals   = [r["rythme_m2_hab_ref"] or 0, r["rythme_m2_hab_zan"] or 0]
    cols   = [COLORS["total"], COLORS["habitat"]]
    fig = go.Figure(go.Bar(
        x=labels, y=vals, marker_color=cols,
        text=[f"{v:.1f} m2".replace(".", ",") for v in vals],
        textposition="outside",
    ))
    fig.update_layout(
        title="Rythme conso/habitant — comparaison périodes",
        yaxis_title="m2 / habitant / an",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        height=320, margin=dict(l=50, r=20, t=50, b=50),
    )
    return fig


def _graph_jauge(r: dict) -> go.Figure:
    pct = r["pct_enveloppe_utilisee"] or 0
    col = _couleur_alerte(pct)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=pct,
        number={"suffix": " %", "font": {"size": 32}},
        gauge={
            "axis": {"range": [0, 120]},
            "bar":  {"color": col},
            "steps": [
                {"range": [0,  70],  "color": "#DCFCE7"},
                {"range": [70, 100], "color": "#FEF3C7"},
                {"range": [100,120], "color": "#FEE2E2"},
            ],
            "threshold": {"line": {"color": COLORS["danger"], "width": 4},
                          "thickness": 0.75, "value": 100},
        },
        title={"text": "Enveloppe ZAN CC utilisée", "font": {"size": 13}},
    ))
    fig.update_layout(
        height=280, paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=40, b=10),
    )
    return fig


def _graph_projection(r: dict) -> go.Figure:
    env_ha  = r["enveloppe_zan_ha"] or 0
    cons_ha = r["consomme_zan_ha"]  or 0
    rythme  = cons_ha / 4
    annees  = list(range(2021, 2032))
    cumul   = [min(rythme * i, env_ha * 2) for i in range(len(annees))]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=annees, y=[env_ha] * len(annees),
        name="Enveloppe ZAN max",
        line=dict(color=COLORS["danger"], dash="dash", width=2),
    ))
    fig.add_trace(go.Scatter(
        x=annees, y=cumul,
        name="Projection au rythme actuel",
        line=dict(color=COLORS["warning"], width=2),
    ))
    fig.add_trace(go.Scatter(
        x=[2021, 2022, 2023, 2024],
        y=[rythme, rythme*2, rythme*3, cons_ha],
        name="Consommé réel 2021-2024",
        line=dict(color=COLORS["total"], width=3),
        marker=dict(size=7),
    ))
    fig.update_layout(
        title="Projection ZAN CC jusqu'en 2031",
        xaxis=dict(tickmode="linear", dtick=1),
        yaxis_title="Hectares cumulés",
        legend=dict(orientation="h", y=1.18, font=dict(size=10)),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        height=300, margin=dict(l=50, r=10, t=60, b=40),
    )
    return fig


# ─────────────────────────────────────────────────────────────────
#  RENDU PRINCIPAL — ONGLET RATIOS EPCI
# ─────────────────────────────────────────────────────────────────

def rendu_ratios_epci(communes: pd.DataFrame):
    """
    Point d'entrée appelé depuis app.py en mode EPCI (vue agrégée).
    Le coefficient ZAN est lu depuis st.session_state["trajectoire_select"].
    """
    if communes.empty:
        st.warning("Aucune donnée disponible pour cette CC.")
        return

    ligne0   = communes.iloc[0]
    nom_epci = str(ligne0.get("epci24txt", "Intercommunalité"))

    # ── Coefficient ZAN (partagé avec autres onglets) ────────────
    idx_traj       = st.session_state.get("trajectoire_select", 10)
    coeff_reduction = TRAJECTOIRES[idx_traj][0]
    label_traj      = TRAJECTOIRES[idx_traj][1]
    pct_red         = coeff_reduction * 100
    facteur         = round(1.0 - coeff_reduction, 3)

    # ── Agrégation ───────────────────────────────────────────────
    agg  = agreger_epci(communes)
    flux = agreger_flux_annuels(communes)
    r    = calculer_ratios_epci(agg, coeff_reduction)

    st.markdown(f"## 📐 Ratios analytiques — {nom_epci}")
    st.caption(
        f"Coefficient ZAN appliqué : **−{pct_red:.1f} %** ({label_traj}) "
        f"— Enveloppe = référence 2011-2020 × {facteur}"
    )
    st.divider()

    # ════════════════════════════════════════════════════════════
    # FAMILLE 1 — Foncier / Population
    # ════════════════════════════════════════════════════════════
    with st.expander("🏗️ 1 — Foncier & Population", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("m2/habitant (total 2009-2024)",  _fm2(r["m2_hab_total"], 0))
        c2.metric("m2/habitant (2011-2020)",         _fm2(r["m2_hab_ref"], 0))
        c3.metric("ha/1 000 hab (total)",            _fha(r["ha_par_1000hab"], 2))
        c4.metric("% territoire CC artificialisé",   _fpct(r["pct_artificialise"], 2))

        st.markdown("---")
        c5, c6 = st.columns(2)
        c5.metric("Rythme moyen 2011-2020 (m2/hab/an)", _fm2(r["rythme_m2_hab_ref"], 1))
        c6.metric("Rythme moyen 2021-2024 (m2/hab/an)", _fm2(r["rythme_m2_hab_zan"], 1),
                  delta=f"{((r['rythme_m2_hab_zan'] or 0) - (r['rythme_m2_hab_ref'] or 0)):+.1f} m2/hab/an"
                  if r["rythme_m2_hab_ref"] and r["rythme_m2_hab_zan"] else None,
                  delta_color="inverse")

        col_g, col_d = st.columns(2)
        col_g.plotly_chart(_graph_flux(flux), use_container_width=True)
        col_d.plotly_chart(_graph_rythmes(r), use_container_width=True)

    # ════════════════════════════════════════════════════════════
    # FAMILLE 2 — Habitat
    # ════════════════════════════════════════════════════════════
    with st.expander("🏠 2 — Habitat & Ménages", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Part habitat / conso totale",        _fpct(r["part_habitat"]))
        c2.metric("m2/nouveau ménage (2011-2020)",      _fm2(r["m2_hab_par_menage"], 0))
        c3.metric("ha/nouveau ménage",                  _fha(r["ha_hab_par_menage"], 3))
        c4.metric("Densité résidentielle implicite",    _fval(r["densite_resid"], "mén/ha", 1))

        dens = r["densite_resid"]
        if dens is not None:
            if dens >= 20:
                st.success(f"✅ Densité résidentielle CC correcte ({dens:.1f} mén/ha).")
            elif dens >= 10:
                st.warning(f"⚠️ Densité résidentielle CC moyenne ({dens:.1f} mén/ha).")
            else:
                st.error(f"🔴 Densité CC très faible ({dens:.1f} mén/ha) — fort étalement.")

    # ════════════════════════════════════════════════════════════
    # FAMILLE 3 — Activité
    # ════════════════════════════════════════════════════════════
    with st.expander("🏭 3 — Activité économique & Emploi", expanded=False):
        c1, c2, c3 = st.columns(3)
        c1.metric("m2/emploi créé (2015-2021)",  _fm2(r["m2_act_par_emploi"], 0))
        c2.metric("ha/emploi créé",              _fha(r["ha_act_par_emploi"], 3))
        c3.metric("Ratio habitat/activité",       _fval(r["ratio_hab_act"], "x", 2))

        if r["delta_emp"] < 0:
            st.warning(
                f"⚠️ Perte d'emplois à l'échelle CC ({int(r['delta_emp']):+d} entre 2015 et 2021).")

    # ════════════════════════════════════════════════════════════
    # FAMILLE 4 — Surface
    # ════════════════════════════════════════════════════════════
    with st.expander("📏 4 — Surface & Pression territoriale", expanded=False):
        c1, c2, c3 = st.columns(3)
        c1.metric("Surface totale CC",              _fha(r["surf_com_ha"], 0))
        c2.metric("% artificiali. 2009-2024",       _fpct(r["pct_artificialise"], 2))
        c3.metric("% artificiali. réf. 2011-2020",  _fpct(r["pct_artificialise_ref"], 2))

        # Treemap
        cats_tm  = ["Habitat", "Activité", "Mixte", "Route", "Ferroviaire", "Inconnu", "Non artif."]
        clés_tm  = ["habitat", "activite", "mixte", "route", "ferroviaire", "inconnu"]
        m2ha     = 10_000
        vals_tm  = [agg["totaux"][k]["total"] / m2ha for k in clés_tm]
        reste    = max(0, (r["surf_com_ha"] or 0) - sum(vals_tm))
        vals_tm.append(reste)
        cols_tm  = [COLORS[k] for k in clés_tm] + ["#E5E7EB"]

        fig_tree = go.Figure(go.Treemap(
            labels=cats_tm,
            parents=[""] * len(cats_tm),
            values=vals_tm,
            marker=dict(colors=cols_tm),
            texttemplate="%{label}<br>%{value:.2f} ha<br>%{percentRoot:.1%}",
        ))
        fig_tree.update_layout(
            title="Répartition du territoire CC (ha)",
            height=360, margin=dict(t=50, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_tree, use_container_width=True)

    # ════════════════════════════════════════════════════════════
    # FAMILLE 5 — ZAN
    # ════════════════════════════════════════════════════════════
    with st.expander("⚡ 5 — Indicateurs ZAN intercommunaux", expanded=True):
        pct_zan = r["pct_enveloppe_utilisee"]
        emoji   = _emoji_alerte(pct_zan)

        st.markdown(f"### {emoji} Bilan ZAN CC 2021-2031 — situation au 31/12/2024")
        st.caption(
            f"Coefficient : **−{pct_red:.1f} %** ({label_traj}) — "
            f"Enveloppe CC = consommation 2011-2020 × {facteur}"
        )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Enveloppe ZAN 2021-2031",    _fha(r["enveloppe_zan_ha"]))
        c2.metric("Consommé 2021-2024",         _fha(r["consomme_zan_ha"]))
        c3.metric("Solde restant 2025-2031",    _fha(r["restant_zan_ha"]),
                  delta=f"{(r['restant_zan_ha'] or 0):+.2f} ha".replace(".", ","),
                  delta_color="normal")
        c4.metric("Capacité annuelle résiduelle", _fha(r["solde_zan_annuel_ha"]))

        col_j, col_p = st.columns([1, 2])
        col_j.plotly_chart(_graph_jauge(r), use_container_width=True)
        col_p.plotly_chart(_graph_projection(r), use_container_width=True)

        # Message contextuel
        ans = r["annees_avant_epuisement"]
        if pct_zan is None:
            st.info("Données insuffisantes pour calculer le bilan ZAN.")
        elif pct_zan >= 100:
            st.error(
                f"🔴 **Enveloppe ZAN CC dépassée !** {_fpct(pct_zan)} du quota utilisé. "
                "Une révision des PLU/PLUi de la CC est urgente.")
        elif pct_zan >= 70:
            st.warning(
                f"🟠 **Vigilance ZAN CC.** {_fpct(pct_zan)} de l'enveloppe utilisée. "
                f"Au rythme actuel, épuisement vers **{2024 + ans:.0f}**.")
        else:
            st.success(
                f"🟢 **Situation ZAN CC satisfaisante.** {_fpct(pct_zan)} utilisé. "
                f"Enveloppe disponible encore environ **{ans:.1f} ans**.")

        # Tableau synthèse ZAN
        st.markdown("##### Tableau de synthèse ZAN intercommunal")
        zan_data = {
            "Indicateur": [
                "Conso. de référence CC 2011-2020",
                f"Enveloppe ZAN max 2021-2031 (−{pct_red:.1f} %)",
                "Consommé 2021-2024 (4 ans)",
                "Solde disponible 2025-2031",
                "Capacité annuelle résiduelle",
                "% enveloppe utilisée",
                "Projection épuisement",
            ],
            "Valeur": [
                _fha(r["enveloppe_zan_ha"] / (1.0 - coeff_reduction)),
                _fha(r["enveloppe_zan_ha"]),
                _fha(r["consomme_zan_ha"]),
                _fha(r["restant_zan_ha"]),
                _fha(r["solde_zan_annuel_ha"]),
                _fpct(r["pct_enveloppe_utilisee"]),
                f"~{2024 + int(ans)}" if ans < 50 else "Conforme 2031 ✓",
            ],
        }
        st.dataframe(pd.DataFrame(zan_data), use_container_width=True, hide_index=True)
