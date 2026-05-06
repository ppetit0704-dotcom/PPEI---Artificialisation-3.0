"""
@author  : Philippe PETIT
@version : 1.0.0
@description : Module d'agrégation intercommunale — Onglet Général EPCI.
               Fiche d'identité de la CC + tableau des communes membres
               avec leurs indicateurs clés triables.
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st


# ─────────────────────────────────────────────────────────────────
#  UTILITAIRES
# ─────────────────────────────────────────────────────────────────

def _safe(val, default=0.0):
    try:
        v = float(val)
        return v if not np.isnan(v) else default
    except (TypeError, ValueError):
        return default

def _fha(v, dec=2):
    if v is None or np.isnan(float(v if v is not None else 0)):
        return "N/D"
    return f"{v:,.{dec}f} ha".replace(",", " ").replace(".", ",")

def _fpct(v, dec=1):
    if v is None: return "N/D"
    try:
        return f"{float(v):.{dec}f} %".replace(".", ",")
    except: return "N/D"

def _fint(v):
    if v is None: return "N/D"
    try:
        return f"{int(v):,}".replace(",", " ")
    except: return "N/D"


# ─────────────────────────────────────────────────────────────────
#  AGRÉGATION
# ─────────────────────────────────────────────────────────────────

# Colonnes flux à sommer (toutes les colonnes art__xxx__)
_FLUX_COLS_ACT = [f"art{a:02d}act{b:02d}" for a,b in [(y,y+1) for y in range(9,24)]]
_FLUX_COLS_HAB = [f"art{a:02d}hab{b:02d}" for a,b in [(y,y+1) for y in range(9,24)]]
_FLUX_COLS_MIX = [f"art{a:02d}mix{b:02d}" for a,b in [(y,y+1) for y in range(9,24)]]
_FLUX_COLS_ROU = [f"art{a:02d}rou{b:02d}" for a,b in [(y,y+1) for y in range(9,24)]]
_FLUX_COLS_FER = [f"art{a:02d}fer{b:02d}" for a,b in [(y,y+1) for y in range(9,24)]]
_FLUX_COLS_INC = [f"art{a:02d}inc{b:02d}" for a,b in [(y,y+1) for y in range(9,24)]]

# Période référence : indices 3-12 de load_data → colonnes art11xxx12 à art20xxx21
_REF_SUFFIXES  = [(f"{a:02d}", f"{b:02d}") for a,b in zip(range(11,21), range(12,22))]
_ZAN_SUFFIXES  = [(f"{a:02d}", f"{b:02d}") for a,b in zip(range(21,24), range(22,25))]


def _sum_cols(df, suffixes, cat):
    """Somme les colonnes art{a}{cat}{b} sur un DataFrame de communes."""
    cols = [f"art{a}{cat}{b}" for a, b in suffixes if f"art{a}{cat}{b}" in df.columns]
    return df[cols].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1).sum()


def agreger_epci(communes: pd.DataFrame) -> dict:
    """
    Agrège toutes les données d'une CC.
    Retourne un dict utilisable par tous les onglets.
    """
    m2ha = 10_000
    cats = {"act": "activite", "hab": "habitat", "mix": "mixte",
            "rou": "route",   "fer": "ferroviaire", "inc": "inconnu"}

    # ── Totaux par catégorie et par période ──────────────────────
    totaux = {}
    for code, label in cats.items():
        tot_all = _sum_cols(communes,
            [(f"{a:02d}", f"{b:02d}") for a,b in zip(range(9,24), range(10,25))], code)
        tot_ref = _sum_cols(communes, _REF_SUFFIXES, code)
        tot_zan = _sum_cols(communes, _ZAN_SUFFIXES, code)
        totaux[label] = {
            "total": tot_all,
            "ref":   tot_ref,
            "zan":   tot_zan,
        }

    conso_tot = sum(v["total"] for v in totaux.values())
    conso_ref = sum(v["ref"]   for v in totaux.values())
    conso_zan = sum(v["zan"]   for v in totaux.values())

    # ── Population / emploi / ménages ───────────────────────────
    pop15 = communes["pop15"].apply(pd.to_numeric, errors="coerce").sum()
    pop21 = communes["pop21"].apply(pd.to_numeric, errors="coerce").sum()
    men15 = communes["men15"].apply(pd.to_numeric, errors="coerce").sum()
    men21 = communes["men21"].apply(pd.to_numeric, errors="coerce").sum()
    emp15 = communes["emp15"].apply(pd.to_numeric, errors="coerce").sum()
    emp21 = communes["emp21"].apply(pd.to_numeric, errors="coerce").sum()
    surf  = communes["surfcom2024"].apply(pd.to_numeric, errors="coerce").sum()

    delta_men = men21 - men15
    delta_emp = emp21 - emp15
    pop_moy   = (pop15 + pop21) / 2 if (pop15 + pop21) > 0 else None

    # ── Ratios ───────────────────────────────────────────────────
    def ratio(a, b): return a / b if b and b > 0 else None

    r = {
        "nb_communes":      len(communes),
        "pop15":            pop15,
        "pop21":            pop21,
        "men15":            men15,
        "men21":            men21,
        "emp15":            emp15,
        "emp21":            emp21,
        "delta_men":        delta_men,
        "delta_emp":        delta_emp,
        "surf_ha":          surf / m2ha,

        "conso_tot_ha":     conso_tot / m2ha,
        "conso_ref_ha":     conso_ref / m2ha,
        "conso_zan_ha":     conso_zan / m2ha,

        "pct_artificialise": ratio(conso_tot, surf) * 100 if surf > 0 else None,

        "m2_hab_total":     ratio(conso_tot, pop21),
        "m2_hab_ref":       ratio(conso_ref, pop_moy),
        "rythme_ref":       ratio(conso_ref, pop_moy) / 10 if pop_moy else None,
        "rythme_zan":       ratio(conso_zan / 4, pop21),

        "m2_hab_par_menage": ratio(totaux["habitat"]["ref"], delta_men),
        "densite_resid":    ratio(delta_men, totaux["habitat"]["total"] / m2ha),
        "m2_act_par_emploi": ratio(totaux["activite"]["total"], delta_emp),

        "part_habitat":     ratio(totaux["habitat"]["total"], conso_tot) * 100 if conso_tot > 0 else 0,
        "part_activite":    ratio(totaux["activite"]["total"], conso_tot) * 100 if conso_tot > 0 else 0,
        "part_route":       ratio(totaux["route"]["total"], conso_tot) * 100 if conso_tot > 0 else 0,

        "totaux":           totaux,
    }

    return r


def agreger_flux_annuels(communes: pd.DataFrame) -> dict:
    """
    Retourne les flux annuels agrégés {annee: {cat: m2}}
    pour alimenter les graphiques (même structure que graph_ratios.py).
    """
    cats = {"act": "activite", "hab": "habitat", "mix": "mixte",
            "rou": "route",   "fer": "ferroviaire", "inc": "inconnu"}
    flux = {}
    for debut in range(9, 24):
        an_fin = debut + 1
        annee  = 2000 + an_fin
        flux[annee] = {}
        for code, label in cats.items():
            col = f"art{debut:02d}{code}{an_fin:02d}"
            if col in communes.columns:
                flux[annee][label] = communes[col].apply(
                    pd.to_numeric, errors="coerce").fillna(0).sum()
            else:
                flux[annee][label] = 0.0
        flux[annee]["total"] = sum(flux[annee].values())
    return flux


# ─────────────────────────────────────────────────────────────────
#  TABLEAU DES COMMUNES MEMBRES
# ─────────────────────────────────────────────────────────────────

def _construire_tableau_communes(communes: pd.DataFrame, coeff_reduction: float) -> pd.DataFrame:
    """
    Construit un DataFrame enrichi pour affichage dans le tableau membres.
    """
    m2ha = 10_000
    rows = []
    for _, c in communes.iterrows():
        # Conso totale (colonnes art09xxxYY à art23xxx24)
        conso_tot = sum(
            _safe(c.get(f"art{a:02d}{cat}{b:02d}", 0))
            for a, b in zip(range(9, 24), range(10, 25))
            for cat in ["act","hab","mix","rou","fer","inc"]
        )
        # Référence 2011-2020
        conso_ref = sum(
            _safe(c.get(f"art{a}{cat}{b}", 0))
            for a, b in _REF_SUFFIXES
            for cat in ["act","hab","mix","rou","fer","inc"]
        )
        # ZAN 2021-2024
        conso_zan = sum(
            _safe(c.get(f"art{a}{cat}{b}", 0))
            for a, b in _ZAN_SUFFIXES
            for cat in ["act","hab","mix","rou","fer","inc"]
        )
        enveloppe = conso_ref * (1.0 - coeff_reduction)
        pct_zan   = conso_zan / enveloppe * 100 if enveloppe > 0 else None
        surf      = _safe(c.get("surfcom2024", 0))

        rows.append({
            "INSEE":           str(c.get("idcom", "")),
            "Commune":         str(c.get("idcomtxt", "")),
            "Pop. 2021":       int(_safe(c.get("pop21", 0))),
            "Conso totale":    round(conso_tot / m2ha, 2),
            "Réf. 2011-2020":  round(conso_ref / m2ha, 2),
            "ZAN 2021-2024":   round(conso_zan / m2ha, 2),
            "Enveloppe ZAN":   round(enveloppe  / m2ha, 2),
            "% enveloppe":     round(pct_zan, 1) if pct_zan is not None else None,
            "% territoire":    round(conso_tot / surf * 100, 2) if surf > 0 else None,
            "_alerte":         (
                "🔴" if (pct_zan or 0) >= 100
                else "🟠" if (pct_zan or 0) >= 70
                else "🟢"
            ),
        })

    df = pd.DataFrame(rows).sort_values("Commune")
    return df


# ─────────────────────────────────────────────────────────────────
#  GRAPHIQUES SYNTHÈSE EPCI
# ─────────────────────────────────────────────────────────────────

def _graph_top10(df_communes: pd.DataFrame) -> go.Figure:
    """Top 10 communes par consommation totale."""
    top = df_communes.nlargest(10, "Conso totale")
    fig = go.Figure(go.Bar(
        x=top["Conso totale"],
        y=top["Commune"],
        orientation="h",
        marker_color="#1565C0",
        text=[f"{v:.2f} ha".replace(".", ",") for v in top["Conso totale"]],
        textposition="outside",
    ))
    fig.update_layout(
        title="🏆 Top 10 communes — Consommation totale (ha)",
        xaxis_title="Hectares", height=340,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=120, r=60, t=50, b=40),
        yaxis=dict(autorange="reversed"),
    )
    return fig


def _graph_zan_communes(df_communes: pd.DataFrame) -> go.Figure:
    """Jauge ZAN par commune (% enveloppe utilisée)."""
    df = df_communes.dropna(subset=["% enveloppe"]).sort_values("% enveloppe", ascending=True)
    cols = [
        "#EF4444" if v >= 100 else "#F97316" if v >= 70 else "#10B981"
        for v in df["% enveloppe"]
    ]
    fig = go.Figure(go.Bar(
        x=df["% enveloppe"],
        y=df["Commune"],
        orientation="h",
        marker_color=cols,
        text=[f"{v:.1f} %".replace(".", ",") for v in df["% enveloppe"]],
        textposition="outside",
    ))
    fig.add_vline(x=100, line=dict(color="#EF4444", dash="dash", width=2))
    fig.update_layout(
        title="⚡ % Enveloppe ZAN utilisée par commune",
        xaxis_title="% enveloppe 2021-2031 utilisée", height=max(300, len(df) * 28),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=130, r=80, t=50, b=40),
        yaxis=dict(autorange="reversed"),
    )
    return fig


# ─────────────────────────────────────────────────────────────────
#  RENDU PRINCIPAL — ONGLET GÉNÉRAL EPCI
# ─────────────────────────────────────────────────────────────────

def rendu_general_epci(communes: pd.DataFrame, coeff_reduction: float = 0.5):
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
    siret    = str(ligne0.get("epci24", ""))
    nb       = len(communes)

    # ── Gestion multi-département / multi-région ─────────────────
    deps    = communes["iddeptxt"].dropna().unique().tolist()
    regions = communes["idregtxt"].dropna().unique().tolist()
    dep     = " · ".join(sorted(deps))
    region  = " · ".join(sorted(regions))
    scots   = communes["scot"].dropna().unique().tolist()

    # ── Agrégation ───────────────────────────────────────────────
    agg = agreger_epci(communes)

    st.markdown(f"## 🏛️ {nom_epci}")
    st.caption(f"SIRET : {siret}  |  {nb} communes membres  |  {dep}  |  {region}")
    st.divider()

    # ── Carte d'identité ─────────────────────────────────────────
    st.markdown("### 📋 Identité de l'intercommunalité")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Nom :** {nom_epci}")
        st.markdown(f"**SIRET :** {siret}")
        # Affichage adapté selon nombre de départements/régions
        if len(deps) > 1:
            st.markdown(f"**Départements :** {dep}")
        else:
            st.markdown(f"**Département :** {dep}")
        if len(regions) > 1:
            st.markdown(f"**Régions :** {region}")
        else:
            st.markdown(f"**Région :** {region}")
        st.markdown(f"**SCoT(s) :** {' · '.join(scots)}")
    with col2:
        st.metric("Communes membres",      nb)
        st.metric("Population 2021",       _fint(agg["pop21"]) + " hab.")
        st.metric("Emplois 2021",          _fint(agg["emp21"]))
        st.metric("Surface totale",        _fha(agg["surf_ha"], 0))

    st.divider()

    # ── Métriques clés ───────────────────────────────────────────
    st.markdown("### 📊 Indicateurs clés de consommation foncière")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Consommation totale\n2009-2024",  _fha(agg["conso_tot_ha"]))
    c2.metric("Décennie référence\n2011-2020",   _fha(agg["conso_ref_ha"]))
    c3.metric("Période ZAN\n2021-2024",          _fha(agg["conso_zan_ha"]))
    c4.metric("% territoire artificialisé",      _fpct(agg["pct_artificialise"]))

    st.divider()

    # ── Tableau des communes membres ──────────────────────────────
    st.markdown("### 🗂️ Communes membres — vue détaillée")

    df_tab = _construire_tableau_communes(communes, coeff_reduction)

    # Compteurs alertes ZAN
    nb_rouge  = (df_tab["_alerte"] == "🔴").sum()
    nb_orange = (df_tab["_alerte"] == "🟠").sum()
    nb_vert   = (df_tab["_alerte"] == "🟢").sum()

    ca, cb, cc = st.columns(3)
    ca.metric("🔴 Enveloppe dépassée",  nb_rouge)
    cb.metric("🟠 Vigilance ZAN",       nb_orange)
    cc.metric("🟢 Situation favorable", nb_vert)

    st.markdown("---")

    # Tableau affiché
    df_affiche = df_tab.drop(columns=["_alerte"]).copy()
    df_affiche.insert(0, "ZAN", df_tab["_alerte"])

    # Formatage colonnes ha
    for col in ["Conso totale", "Réf. 2011-2020", "ZAN 2021-2024", "Enveloppe ZAN"]:
        df_affiche[col] = df_affiche[col].apply(
            lambda v: f"{v:.2f} ha".replace(".", ",") if pd.notna(v) else "N/D"
        )
    df_affiche["% enveloppe"] = df_affiche["% enveloppe"].apply(
        lambda v: f"{v:.1f} %".replace(".", ",") if pd.notna(v) else "N/D"
    )
    df_affiche["% territoire"] = df_affiche["% territoire"].apply(
        lambda v: f"{v:.2f} %".replace(".", ",") if pd.notna(v) else "N/D"
    )
    df_affiche["Pop. 2021"] = df_affiche["Pop. 2021"].apply(
        lambda v: f"{v:,}".replace(",", " ")
    )

    st.dataframe(df_affiche, use_container_width=True, hide_index=True,
                 column_config={
                     "ZAN":          st.column_config.TextColumn("ZAN", width="small"),
                     "INSEE":        st.column_config.TextColumn("INSEE", width="small"),
                     "Commune":      st.column_config.TextColumn("Commune"),
                     "Pop. 2021":    st.column_config.TextColumn("Pop. 2021"),
                 })

    st.divider()

    # ── Graphiques ───────────────────────────────────────────────
    st.markdown("### 📈 Visualisations intercommunales")

    col_g, col_d = st.columns(2)
    with col_g:
        st.plotly_chart(_graph_top10(df_tab), use_container_width=True)
    with col_d:
        st.plotly_chart(_graph_zan_communes(df_tab), use_container_width=True)
