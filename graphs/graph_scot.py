"""
@author  : Philippe PETIT
@version : 3.0.0
@description : Module SCOT — version premium, dynamique, cohérente avec agreger_epci(),
               avec prise en compte du coefficient de réduction choisi par l'utilisateur.
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
#  OUTILS DE FORMATAGE ROBUSTES
# ───────────────────────────────────────────────────────────────

def _safe_to_int(x):
    if x is None:
        return None
    try:
        s = str(x).replace("\u202f", "").replace(" ", "").replace(",", ".").strip()
        return int(float(s))
    except:
        return None

def _safe_to_float(x):
    if x is None:
        return None
    try:
        s = str(x).replace("\u202f", "").replace(" ", "").replace(",", ".").strip()
        return float(s)
    except:
        return None

def _fmt_ha(m2):
    if m2 is None:
        return "N/D"
    return f"{m2 / M2_HA:.2f} ha".replace(".", ",")

def _fmt_pct(x):
    if x is None:
        return "N/D"
    return f"{x:.1f} %".replace(".", ",")


# ───────────────────────────────────────────────────────────────
#  IDENTITÉ TERRITORIALE (VERSION PREMIUM)
# ───────────────────────────────────────────────────────────────
def _bloc_identite_territoriale(communes):
    ligne0 = communes.iloc[0]

    nom = ligne0.get("scot", "SCoT")

    # --- Départements multiples ---
    depts = (
        communes["iddeptxt"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
        .tolist()
    )
    dept_txt = ", ".join(sorted(depts)) if depts else "N/D"

    # --- Régions multiples ---
    regions = (
        communes["idregtxt"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
        .tolist()
    )
    region_txt = ", ".join(sorted(regions)) if regions else "N/D"

    nb_com = len(communes)

    # Population totale
    pop_vals = communes["pop21"].apply(_safe_to_int)
    pop_tot = pop_vals.sum() if pop_vals.notna().any() else None
    pop_txt = "N/D" if pop_tot is None else f"{pop_tot:,d}".replace(",", "\u202f")

    # Emplois totaux
    emp_vals = communes["emp21"].apply(_safe_to_int)
    emplois = emp_vals.sum() if emp_vals.notna().any() else None
    emp_txt = "N/D" if emplois is None else f"{emplois:,d}".replace(",", "\u202f")

    # Surface totale
    surf_vals = communes["surfcom2024"].apply(_safe_to_float)
    surf_m2 = surf_vals.sum() if surf_vals.notna().any() else None
    surf_ha = surf_m2 / 10_000 if surf_m2 is not None else None
    surf_txt = (
        f"{surf_ha:,.2f} ha".replace(",", "\u202f").replace(".", ",")
        if surf_ha is not None else "N/D"
    )

    st.markdown("### 🏛️ Identité du territoire")
    st.markdown(
        f"""
        <div style="padding:18px; border:1px solid #ddd; border-radius:10px; background:#fafafa;color:blue;">
            <b>Nom :</b> {nom}<br>
            <b>Département(s) :</b> {dept_txt}<br>
            <b>Région(s) :</b> {region_txt}<br>
            <br>
            <b>Communes membres :</b> {nb_com}<br>
            <b>Population 2021 :</b> {pop_txt} hab.<br>
            <b>Emplois 2021 :</b> {emp_txt}<br>
            <b>Surface totale :</b> {surf_txt}<br>
        </div>
        """,
        unsafe_allow_html=True
    )


# ───────────────────────────────────────────────────────────────
#  CALCULS CATÉGORIES
# ───────────────────────────────────────────────────────────────

def _compute_totaux_par_categorie(flux: dict):
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


# ───────────────────────────────────────────────────────────────
#  GRAPHIQUES
# ───────────────────────────────────────────────────────────────

def _graph_barres(flux: dict) -> go.Figure:
    annees = sorted(flux.keys())
    fig = go.Figure()

    for key, label, col in CATEGORIES:
        vals = [(flux[a].get(key, 0.0) / M2_HA) for a in annees]
        fig.add_trace(go.Bar(name=label, x=annees, y=vals, marker_color=col))

    fig.update_layout(
        barmode="stack",
        title="Consommation annuelle agrégée (ha/an)",
        height=380,
        margin=dict(l=40, r=20, t=60, b=40),
        plot_bgcolor="rgba(0,0,0,0)",
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
#  RENDU — GÉNÉRAL SCOT
# ───────────────────────────────────────────────────────────────

def rendu_general_scot(communes: pd.DataFrame, struct: dict, coeff_reduction: float):

    if communes.empty:
        st.warning("Aucune donnée disponible pour ce SCoT.")
        return

    agg = agreger_epci(communes, struct)
    flux = agg["flux"]

    conso_ref = agg["totaux"]["ref"]
    conso_zan = agg["totaux"]["zan"]
    enveloppe_m2 = conso_ref * coeff_reduction
    pct_enveloppe = (conso_zan / enveloppe_m2 * 100) if enveloppe_m2 > 0 else None

    totaux_cat, _, _ = _compute_totaux_par_categorie(flux)

    ligne0 = communes.iloc[0]
    nom_scot = ligne0.get("scot", "SCoT")

    st.markdown(f"## 🏛️ Général — {nom_scot}")
    st.divider()

    _bloc_identite_territoriale(communes)
    st.divider()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Consommation totale 2009–2024", _fmt_ha(agg["totaux"]["total"]))
    c2.metric("Référence 2011–2020",           _fmt_ha(conso_ref))
    c3.metric("ZAN 2021–2024",                 _fmt_ha(conso_zan))
    c4.metric(f"% enveloppe ({coeff_reduction:.2f}× réf.)", _fmt_pct(pct_enveloppe))

    st.divider()

    col_g, col_d = st.columns([2, 1])
    col_g.plotly_chart(_graph_barres(flux), use_container_width=True, key="scot_general_barres")
    col_d.plotly_chart(_graph_donut(totaux_cat), use_container_width=True, key="scot_general_donut")


# ───────────────────────────────────────────────────────────────
#  RENDU — SYNTHÈSE SCOT
# ───────────────────────────────────────────────────────────────

def rendu_synthese_scot(communes: pd.DataFrame, struct: dict, coeff_reduction: float):

    if communes.empty:
        st.warning("Aucune donnée disponible pour ce SCoT.")
        return

    agg = agreger_epci(communes, struct)
    flux = agg["flux"]

    conso_ref = agg["totaux"]["ref"]
    conso_zan = agg["totaux"]["zan"]
    enveloppe_m2 = conso_ref * coeff_reduction
    pct_enveloppe = (conso_zan / enveloppe_m2 * 100) if enveloppe_m2 > 0 else None

    totaux_cat, totaux_ref_cat, totaux_zan_cat = _compute_totaux_par_categorie(flux)

    ligne0 = communes.iloc[0]
    nom_scot = ligne0.get("scot", "SCoT")

    st.markdown(f"## 📐 Synthèse — {nom_scot}")
    st.divider()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Consommation totale 2009–2024", _fmt_ha(agg["totaux"]["total"]))
    c2.metric("Référence 2011–2020",           _fmt_ha(conso_ref))
    c3.metric("ZAN 2021–2024",                 _fmt_ha(conso_zan))
    c4.metric(f"% enveloppe ({coeff_reduction:.2f}× réf.)", _fmt_pct(pct_enveloppe))

    st.divider()

    rows = []
    for key, label, _ in CATEGORIES:
        rows.append({
            "Catégorie": label,
            "Total 2009–2024": _fmt_ha(totaux_cat[key]),
            "2011–2020 (réf.)": _fmt_ha(totaux_ref_cat[key]),
            "2021–2024 (ZAN)": _fmt_ha(totaux_zan_cat[key]),
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.divider()

    col_g, col_d = st.columns([2, 1])
    col_g.plotly_chart(_graph_barres(flux), use_container_width=True, key="scot_synthese_barres")
    col_d.plotly_chart(_graph_donut(totaux_cat), use_container_width=True, key="scot_synthese_donut")


# ───────────────────────────────────────────────────────────────
#  RENDU — ANALYSE SCOT
# ───────────────────────────────────────────────────────────────

def rendu_analyse_scot(communes: pd.DataFrame, struct: dict):

    if communes.empty:
        st.warning("Aucune donnée disponible pour ce SCoT.")
        return

    agg = agreger_epci(communes, struct)
    flux = agg["flux"]

    totaux_cat, totaux_ref_cat, totaux_zan_cat = _compute_totaux_par_categorie(flux)

    ligne0 = communes.iloc[0]
    nom_scot = ligne0.get("scot", "SCoT")

    st.markdown(f"## 📈 Analyse — {nom_scot}")
    st.divider()

    st.markdown("### 📉 Tendances annuelles")
    st.plotly_chart(_graph_barres(flux), use_container_width=True, key="scot_analyse_barres")

    st.divider()

    rows = []
    for key, label, _ in CATEGORIES:
        r_ref = (totaux_ref_cat[key] / 10) / M2_HA
        r_zan = (totaux_zan_cat[key] / 4) / M2_HA
        evol = ((r_zan - r_ref) / r_ref * 100) if r_ref > 0 else None

        rows.append({
            "Catégorie": label,
            "Rythme réf. (ha/an)": f"{r_ref:.2f}".replace(".", ","),
            "Rythme ZAN (ha/an)": f"{r_zan:.2f}".replace(".", ","),
            "Évolution (%)": _fmt_pct(evol),
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ───────────────────────────────────────────────────────────────
#  RENDU — RATIOS SCOT
# ───────────────────────────────────────────────────────────────

def rendu_ratios_scot(communes: pd.DataFrame, struct: dict):

    if communes.empty:
        st.warning("Aucune donnée disponible pour ce SCoT.")
        return

    agg = agreger_epci(communes, struct)

    ligne0 = communes.iloc[0]
    nom_scot = ligne0.get("scot", "SCoT")

    st.markdown(f"## 📊 Ratios — {nom_scot}")
    st.divider()

    rows = [
        {"Ratio": "m² / hab (total)", "Valeur": (agg["m2_hab_total"])},
        {"Ratio": "m² / hab (réf.)",   "Valeur":(agg["m2_hab_ref"])},
        {"Ratio": "m² / hab (ZAN)",    "Valeur":(agg["m2_hab_zan"])},
        {"Ratio": "ha / hab",          "Valeur":(agg["ha_par_hab"])},
        {"Ratio": "m² activité / emploi", "Valeur": (agg["m2_act_par_emploi"])},
    ]


    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ───────────────────────────────────────────────────────────────
#  RENDU — EXPORT PDF SCOT
# ───────────────────────────────────────────────────────────────

def rendu_export_pdf_scot(communes: pd.DataFrame, struct: dict):

    if communes.empty:
        st.warning("Aucune donnée disponible pour ce SCoT.")
        return

    agg = agreger_epci(communes, struct)
    flux = agg["flux"]
    totaux_cat, _, _ = _compute_totaux_par_categorie(flux)

    ligne0 = communes.iloc[0]
    nom_scot = ligne0.get("scot", "SCoT")

    st.markdown(f"## 📄 Export PDF — {nom_scot}")
    st.caption("Imprimez cette page en PDF via votre navigateur.")
    st.divider()

    st.markdown(f"""
    <div style="padding:40px; border:2px solid #ccc; border-radius:12px; margin-bottom:40px;">
        <h1 style="text-align:center; margin-bottom:0;">Synthèse SCoT</h1>
        <h2 style="text-align:center; margin-top:5px; color:#555;">{nom_scot}</h2>
    </div>
    """, unsafe_allow_html=True)

    st.plotly_chart(_graph_barres(flux), use_container_width=True, key="scot_pdf_barres")
    st.plotly_chart(_graph_donut(totaux_cat), use_container_width=True, key="scot_pdf_donut")
