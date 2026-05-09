"""
@module  : graphs.graph_epci_general
@author  : Philippe PETIT
@version : 3.0.0
@description : Vue générale EPCI — version premium
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st

from data.load_data import lire_les_donnees


# ───────────────────────────────────────────────────────────────
#  UTILITAIRES
# ───────────────────────────────────────────────────────────────

def _safe(v, default=0.0):
    try:
        f = float(v)
        return f if not np.isnan(f) else default
    except:
        return default

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

def _fha(v, dec=2):
    if v is None:
        return "N/D"
    return f"{v:,.{dec}f} ha".replace(",", " ").replace(".", ",")

def _fpct(v, dec=1):
    if v is None:
        return "N/D"
    return f"{v:.{dec}f} %".replace(".", ",")

def _fint(v):
    if v is None:
        return "N/D"
    return f"{int(v):,}".replace(",", " ")


# ───────────────────────────────────────────────────────────────
#  EXTRACTION FLUX COMMUNE
# ───────────────────────────────────────────────────────────────

def _extraire_flux_commune(donnees):
    flux = {}
    suffixes = donnees["suffixes_ref"] + donnees["suffixes_zan"]

    cats = {
        "activity":    "activite",
        "habitat":     "habitat",
        "mixte":       "mixte",
        "route":       "route",
        "ferroviaire": "ferroviaire",
        "inconnu":     "inconnu",
    }

    for i, (a, b) in enumerate(suffixes):
        idx = 3 + i
        annee = 2000 + int(a)
        flux[annee] = {}
        total = 0.0

        for key_src, key_dst in cats.items():
            val = _safe(donnees[key_src].get(idx, 0))
            flux[annee][key_dst] = val
            total += val

        flux[annee]["total"] = total

    return flux


def _extraire_totaux_commune(donnees, flux):
    suffixes_ref = donnees["suffixes_ref"]
    suffixes_zan = donnees["suffixes_zan"]

    years_ref = [2000 + int(a) for (a, b) in suffixes_ref]
    years_zan = [2000 + int(a) for (a, b) in suffixes_zan]
    years_all = sorted(flux.keys())

    cats = ["activite", "habitat", "mixte", "route", "ferroviaire", "inconnu", "total"]

    def _sum(years):
        return {c: sum(flux[y][c] for y in years) for c in cats}

    return {
        "total": _sum(years_all),
        "ref":   _sum(years_ref),
        "zan":   _sum(years_zan),
        "meta": {
            "years_all": years_all,
            "years_ref": years_ref,
            "years_zan": years_zan,
        }
    }


# ───────────────────────────────────────────────────────────────
#  AGRÉGATION EPCI
# ───────────────────────────────────────────────────────────────
def agreger_epci(communes: pd.DataFrame, struct) -> dict:
    """
    Agrège toutes les communes via lire_les_donnees().
    Retourne un dict complet incluant les ratios A3‑C.
    """

    donnees_list = []
    flux_list = []
    totaux_list = []

    for _, ligne in communes.iterrows():
        d = lire_les_donnees(ligne, struct)
        f = _extraire_flux_commune(d)
        t = _extraire_totaux_commune(d, f)

        donnees_list.append(d)
        flux_list.append(f)
        totaux_list.append(t)

    # 1) Flux annuels agrégés
    flux_epci = {}
    all_years = sorted({y for f in flux_list for y in f.keys()})

    cats = ["activite", "habitat", "mixte", "route", "ferroviaire", "inconnu"]

    for y in all_years:
        flux_epci[y] = {}
        total = 0.0
        for c in cats:
            val = sum(f.get(y, {}).get(c, 0) for f in flux_list)
            flux_epci[y][c] = val
            total += val
        flux_epci[y]["total"] = total

    # 2) Totaux ref / ZAN
    def _sum_tot(key):
        return sum(t[key]["total"] for t in totaux_list)

    conso_tot = _sum_tot("total")
    conso_ref = _sum_tot("ref")
    conso_zan = _sum_tot("zan")

    # 3) Données démographiques et surface
    pop21 = communes["pop21"].apply(pd.to_numeric, errors="coerce").sum()
    emp21 = communes["emp21"].apply(pd.to_numeric, errors="coerce").sum()
    surf  = communes["surfcom2024"].apply(pd.to_numeric, errors="coerce").sum()

    m2ha = 10_000

    # 4) Ratios A3‑C
    def ratio(a, b):
        return a / b if b and b > 0 else None

    pop_moy = pop21  # cohérent avec ton tableau de bord

    m2_hab_total = ratio(conso_tot, pop21)
    m2_hab_ref   = ratio(conso_ref, pop_moy)
    m2_hab_zan   = ratio(conso_zan, pop21)

    ha_par_hab = ratio(conso_tot / m2ha, pop21)

    conso_act_tot = sum(t["total"]["activite"] for t in totaux_list)
    m2_act_par_emploi = ratio(conso_act_tot, emp21)

    pct_artificialise = ratio(conso_tot, surf) * 100 if surf > 0 else None

    enveloppe_zan_ha = (conso_ref * 0.5) / m2ha
    pct_enveloppe = ratio(conso_zan, conso_ref * 0.5) * 100 if conso_ref > 0 else None

    # 5) Retour complet
    r = {
        "nb_communes": len(communes),
        "pop21": pop21,
        "emp21": emp21,
        "surf_ha": surf / m2ha,

        "conso_tot_ha": conso_tot / m2ha,
        "conso_ref_ha": conso_ref / m2ha,
        "conso_zan_ha": conso_zan / m2ha,

        # Ratios A3‑C
        "m2_hab_total": m2_hab_total,
        "m2_hab_ref":   m2_hab_ref,
        "m2_hab_zan":   m2_hab_zan,
        "ha_par_hab":   ha_par_hab,
        "m2_act_par_emploi": m2_act_par_emploi,

        # Pourcentages
        "pct_artificialise": pct_artificialise,
        "pct_enveloppe": pct_enveloppe,

        # Enveloppe ZAN
        "enveloppe_zan_ha": enveloppe_zan_ha,

        # Flux et totaux
        "flux": flux_epci,
        "totaux": {
            "total": conso_tot,
            "ref": conso_ref,
            "zan": conso_zan,
        }
    }

    return r


# ───────────────────────────────────────────────────────────────
#  IDENTITÉ TERRITORIALE (VERSION ROBUSTE)
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
#  TABLEAU DES COMMUNES
# ───────────────────────────────────────────────────────────────

def construire_tableau_communes(communes, struct):
    rows = []
    m2ha = 10_000

    for _, ligne in communes.iterrows():
        d = lire_les_donnees(ligne, struct)
        f = _extraire_flux_commune(d)
        t = _extraire_totaux_commune(d, f)

        conso_tot = t["total"]["total"]
        conso_ref = t["ref"]["total"]
        conso_zan = t["zan"]["total"]

        enveloppe = conso_ref * 0.5
        pct = conso_zan / enveloppe * 100 if enveloppe > 0 else None

        rows.append({
            "INSEE": ligne["idcom"],
            "Commune": ligne["idcomtxt"],
            "Pop. 2021": int(_safe(ligne["pop21"])),
            "Conso totale": conso_tot / m2ha,
            "Réf. 2011-2020": conso_ref / m2ha,
            "ZAN 2021-2024": conso_zan / m2ha,
            "Enveloppe ZAN": enveloppe / m2ha,
            "% enveloppe": pct,
            "_alerte": (
                "🔴" if (pct or 0) >= 100 else
                "🟠" if (pct or 0) >= 70 else
                "🟢"
            )
        })

    return pd.DataFrame(rows).sort_values("Commune")


# ───────────────────────────────────────────────────────────────
#  GRAPHIQUES
# ───────────────────────────────────────────────────────────────

def graph_top10(df):
    top = df.nlargest(10, "Conso totale")
    fig = go.Figure(go.Bar(
        x=top["Conso totale"],
        y=top["Commune"],
        orientation="h",
        marker_color="#1565C0",
        text=[f"{v:.2f} ha".replace(".", ",") for v in top["Conso totale"]],
        textposition="outside",
    ))
    fig.update_layout(
        title="Top 10 communes — Consommation totale (ha)",
        xaxis_title="Hectares",
        height=340,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=120, r=60, t=50, b=40),
        yaxis=dict(autorange="reversed"),
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


def graph_zan(df):
    df2 = df.dropna(subset=["% enveloppe"]).sort_values("% enveloppe")
    cols = [
        "#EF4444" if v >= 100 else "#F97316" if v >= 70 else "#10B981"
        for v in df2["% enveloppe"]
    ]
    fig = go.Figure(go.Bar(
        x=df2["% enveloppe"],
        y=df2["Commune"],
        orientation="h",
        marker_color=cols,
        text=[f"{v:.1f} %".replace(".", ",") for v in df2["% enveloppe"]],
        textposition="outside",
    ))
    fig.add_vline(x=100, line=dict(color="#EF4444", dash="dash"))
    fig.update_layout(
        title="% Enveloppe ZAN utilisée par commune",
        xaxis_title="% enveloppe 2021-2031 utilisée",
        height=max(300, len(df2) * 28),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=130, r=80, t=50, b=40),
        yaxis=dict(autorange="reversed"),
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
#  RENDU STREAMLIT
# ───────────────────────────────────────────────────────────────

def rendu_general_epci(communes, struct):

    if communes.empty:
        st.warning("Aucune donnée disponible pour cette intercommunalité.")
        return

    agg = agreger_epci(communes, struct)
    df_tab = construire_tableau_communes(communes, struct)

    ligne0 = communes.iloc[0]
    nom_epci = ligne0.get("epci24txt", "Intercommunalité")
    siret = ligne0.get("epci24", "")

    st.markdown(f"## 🏛️ {nom_epci}")
    st.caption(f"SIRET : {siret} — {agg['nb_communes']} communes membres")
    st.divider()

    # Bloc identité premium
    _bloc_identite_territoriale(communes)
    st.divider()

    # Ratios A3‑C
    st.markdown("### Ratios intercommunaux (A3‑C)")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("m²/hab (total)", f"{agg['conso_tot_ha'] * 10000 / agg['pop21']:.1f} m²".replace(".", ","))
    c2.metric("m²/hab (réf.)", f"{agg['conso_ref_ha'] * 10000 / agg['pop21']:.1f} m²".replace(".", ","))
    c3.metric("m²/hab (ZAN)", f"{agg['conso_zan_ha'] * 10000 / agg['pop21']:.1f} m²".replace(".", ","))
    c4.metric("% enveloppe ZAN", _fpct(agg["pct_enveloppe"]))

    st.divider()

    # Tableau communes
    st.markdown("### Communes membres")
    df_aff = df_tab.copy()
    df_aff["Conso totale"] = df_aff["Conso totale"].apply(lambda v: f"{v:.2f} ha".replace(".", ","))
    df_aff["Réf. 2011-2020"] = df_aff["Réf. 2011-2020"].apply(lambda v: f"{v:.2f} ha".replace(".", ","))
    df_aff["ZAN 2021-2024"] = df_aff["ZAN 2021-2024"].apply(lambda v: f"{v:.2f} ha".replace(".", ","))
    df_aff["Enveloppe ZAN"] = df_aff["Enveloppe ZAN"].apply(lambda v: f"{v:.2f} ha".replace(".", ","))
    df_aff["% enveloppe"] = df_aff["% enveloppe"].apply(lambda v: f"{v:.1f} %".replace(".", ",") if v is not None else "N/D")

    st.dataframe(df_aff, use_container_width=True, hide_index=True)

    st.divider()

    # Graphiques
    st.markdown("### Visualisations intercommunales")
    col_g, col_d = st.columns(2)
    col_g.plotly_chart(graph_top10(df_tab), use_container_width=True)
    col_d.plotly_chart(graph_zan(df_tab), use_container_width=True)
