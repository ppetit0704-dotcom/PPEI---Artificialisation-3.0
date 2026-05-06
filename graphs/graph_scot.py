"""
@author  : Philippe PETIT
@version : 1.0.0
@description : Module SCoT — Adaptateur au-dessus des modules EPCI.
               La logique d'agrégation est identique (somme de communes),
               seuls les libellés, titres et recommandations sont adaptés
               à l'échelle SCoT (DOO, porter-à-connaissance, etc.).
"""

import io
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ── Réutilisation intégrale des modules EPCI ─────────────────────
from graphs.graph_epci_general  import (
    agreger_epci, agreger_flux_annuels,
    _construire_tableau_communes,
    _fha, _fpct, _fint,
    rendu_general_epci,
)
from graphs.graph_epci_synthese import rendu_synthese_epci
from graphs.graph_epci_analyse  import rendu_analyse_epci
from graphs.graph_epci_ratios   import rendu_ratios_epci, calculer_ratios_epci

# ── Helpers PDF ──────────────────────────────────────────────────
from graphs.graph_export_pdf import (
    W, H, MARGIN,
    C_DARK, C_PRIMARY, C_ACCENT, C_MID, C_WHITE, C_LIGHT,
    _fm2, _fval,
    _make_styles, _metric_table, _data_table,
    _img_from_bytes, _plotly_to_png, _HeaderFooterCanvas,
)
from graphs.graph_export_pdf_epci import (
    _fig_flux_epci, _fig_donut_epci, _fig_top10,
    _fig_jauge_epci, _fig_projection_epci, _fig_zan_communes,
    generer_rapport_pdf_epci,   # réutilisé avec paramètre niveau="scot"
)

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate, Frame, HRFlowable, Image,
    NextPageTemplate, PageBreak, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)


# ─────────────────────────────────────────────────────────────────
#  UTILITAIRES LOCAUX
# ─────────────────────────────────────────────────────────────────

def _fint(v):
    if v is None: return "N/D"
    try: return f"{int(v):,}".replace(",", " ")
    except: return "N/D"


# ─────────────────────────────────────────────────────────────────
#  ONGLET GÉNÉRAL SCOT
# ─────────────────────────────────────────────────────────────────

def rendu_general_scot(communes: pd.DataFrame, coeff_reduction: float = 0.5):
    """
    Vue Général à l'échelle SCoT.
    Réutilise rendu_general_epci avec un titre adapté +
    un tableau des EPCI membres en plus.
    """
    if communes.empty:
        st.warning("Aucune donnée disponible pour ce SCoT.")
        return

    ligne0   = communes.iloc[0]
    nom_scot = str(ligne0.get("scot", "SCoT"))

    # ── Gestion multi-département / multi-région ─────────────────
    deps    = communes["iddeptxt"].dropna().unique().tolist()
    regions = communes["idregtxt"].dropna().unique().tolist()
    dep     = " · ".join(sorted(deps))
    region  = " · ".join(sorted(regions))

    agg      = agreger_epci(communes)
    nb_epci  = communes["epci24txt"].nunique()

    st.markdown(f"## 🗺️ {nom_scot}")

    # Caption adapté selon multi-dep/région
    caption_parts = [f"{len(communes)} communes", f"{nb_epci} EPCI/CC"]
    if len(deps) > 1:
        caption_parts.append(f"Départements : {dep}")
    else:
        caption_parts.append(dep)
    if len(regions) > 1:
        caption_parts.append(f"Régions : {region}")
    else:
        caption_parts.append(region)
    st.caption("  |  ".join(caption_parts))
    st.divider()

    # ── Résumé EPCI membres ──────────────────────────────────────
    st.markdown("### 🏛️ Intercommunalités membres du SCoT")

    epci_rows = []
    for epci_nom, grp in communes.groupby("epci24txt"):
        conso = sum(
            grp.get(f"art{a:02d}{cat}{b:02d}", pd.Series(0)).apply(
                pd.to_numeric, errors="coerce").fillna(0).sum()
            for a, b in zip(range(9,24), range(10,25))
            for cat in ["act","hab","mix","rou","fer","inc"]
        )
        deps_epci = " · ".join(sorted(grp["iddeptxt"].dropna().unique().tolist()))
        epci_rows.append({
            "EPCI / CC":       epci_nom,
            "SIRET":           str(grp.iloc[0].get("epci24","")),
            "Département(s)":  deps_epci,
            "Communes":        len(grp),
            "Pop. 2021":       int(grp["pop21"].apply(pd.to_numeric, errors="coerce").sum()),
            "Conso totale":    f"{conso/10_000:.2f} ha".replace(".", ","),
        })

    df_epci = pd.DataFrame(epci_rows).sort_values("EPCI / CC")
    st.dataframe(df_epci, use_container_width=True, hide_index=True)
    st.divider()

    # ── Métriques agrégées SCoT ──────────────────────────────────
    st.markdown("### 📊 Indicateurs clés agrégés SCoT")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Communes membres",       len(communes))
    c2.metric("EPCI / CC membres",      nb_epci)
    c3.metric("Population 2021",        _fint(agg["pop21"]) + " hab.")
    c4.metric("Surface totale",         _fha(agg["surf_ha"], 0))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Consommation 2009-2024", _fha(agg["conso_tot_ha"]))
    c6.metric("Référence 2011-2020",    _fha(agg["conso_ref_ha"]))
    c7.metric("ZAN 2021-2024",          _fha(agg["conso_zan_ha"]))
    c8.metric("% territoire artificialisé", _fpct(agg["pct_artificialise"]))

    st.divider()

    # ── Tableau communes (même que EPCI) ─────────────────────────
    st.markdown("### 🗂️ Communes membres — vue détaillée")
    from graphs.graph_epci_general import (
        _construire_tableau_communes, _graph_top10, _graph_zan_communes
    )
    df_tab = _construire_tableau_communes(communes, coeff_reduction)

    nb_rouge  = (df_tab["_alerte"] == "🔴").sum()
    nb_orange = (df_tab["_alerte"] == "🟠").sum()
    nb_vert   = (df_tab["_alerte"] == "🟢").sum()

    ca, cb, cc = st.columns(3)
    ca.metric("🔴 Enveloppe dépassée",  nb_rouge)
    cb.metric("🟠 Vigilance ZAN",       nb_orange)
    cc.metric("🟢 Situation favorable", nb_vert)

    df_affiche = df_tab.drop(columns=["_alerte"]).copy()
    df_affiche.insert(0, "ZAN", df_tab["_alerte"])
    for col in ["Conso totale","Réf. 2011-2020","ZAN 2021-2024","Enveloppe ZAN"]:
        df_affiche[col] = df_affiche[col].apply(
            lambda v: f"{v:.2f} ha".replace(".", ",") if pd.notna(v) else "N/D")
    df_affiche["% enveloppe"] = df_affiche["% enveloppe"].apply(
        lambda v: f"{v:.1f} %".replace(".", ",") if pd.notna(v) else "N/D")
    df_affiche["Pop. 2021"] = df_affiche["Pop. 2021"].apply(
        lambda v: f"{v:,}".replace(",", " "))

    st.dataframe(df_affiche, use_container_width=True, hide_index=True)
    st.divider()

    st.markdown("### 📈 Visualisations")
    col_g, col_d = st.columns(2)
    with col_g:
        st.plotly_chart(_graph_top10(df_tab), use_container_width=True)
    with col_d:
        st.plotly_chart(_graph_zan_communes(df_tab), use_container_width=True)


# ─────────────────────────────────────────────────────────────────
#  ONGLETS SYNTHÈSE / ANALYSE / RATIOS SCOT
#  → Délégation aux modules EPCI avec injection du nom SCoT
# ─────────────────────────────────────────────────────────────────

def _communes_avec_nom_scot(communes: pd.DataFrame) -> pd.DataFrame:
    """
    Remplace epci24txt par le nom du SCoT sur TOUTES les lignes
    du DataFrame, pour que les modules EPCI affichent le bon nom.
    La colonne epci24txt_orig est conservée pour les tableaux.
    """
    communes = communes.copy()
    nom_scot = str(communes.iloc[0].get("scot", "SCoT"))
    communes["epci24txt_orig"] = communes["epci24txt"]   # sauvegarde
    communes["epci24txt"]      = nom_scot                # injection
    return communes


def rendu_synthese_scot(communes: pd.DataFrame, coeff_reduction: float = 0.5):
    """Synthèse SCoT — délègue à rendu_synthese_epci avec nom SCoT."""
    if communes.empty:
        st.warning("Aucune donnée."); return
    rendu_synthese_epci(_communes_avec_nom_scot(communes), coeff_reduction)


def rendu_analyse_scot(communes: pd.DataFrame):
    """Analyse & Tendances SCoT — délègue à rendu_analyse_epci."""
    if communes.empty:
        st.warning("Aucune donnée."); return
    rendu_analyse_epci(_communes_avec_nom_scot(communes))


def rendu_ratios_scot(communes: pd.DataFrame):
    """Ratios SCoT — délègue à rendu_ratios_epci."""
    if communes.empty:
        st.warning("Aucune donnée."); return
    rendu_ratios_epci(_communes_avec_nom_scot(communes))


# ─────────────────────────────────────────────────────────────────
#  EXPORT PDF SCOT
#  → Réutilise generer_rapport_pdf_epci avec textes SCoT
# ─────────────────────────────────────────────────────────────────

def generer_rapport_pdf_scot(communes: pd.DataFrame,
                              coeff_reduction: float = 0.5) -> bytes:
    """
    Génère le rapport PDF à l'échelle SCoT.
    Réutilise intégralement la maquette du rapport EPCI,
    en substituant les libellés SCoT.
    """
    if communes.empty:
        raise ValueError("Aucune commune pour ce SCoT.")

    nom_scot = str(communes.iloc[0].get("scot", "SCoT"))
    nb_epci  = communes["epci24txt"].nunique()

    # On substitue epci24txt par le nom du SCoT pour que
    # generer_rapport_pdf_epci affiche le bon nom partout
    communes_mod = communes.copy()
    communes_mod["epci24txt"] = nom_scot
    # On met le nb d'EPCI en caption via le champ scot (pas utilisé dans le PDF EPCI)
    communes_mod["epci24"] = f"SCoT — {nb_epci} EPCI/CC membres"

    return generer_rapport_pdf_epci(communes_mod, coeff_reduction)


def rendu_export_pdf_scot(communes: pd.DataFrame):
    """Point d'entrée Streamlit — Export PDF SCoT."""
    if communes.empty:
        st.warning("Aucune donnée disponible pour ce SCoT.")
        return

    nom_scot = str(communes.iloc[0].get("scot", "SCoT"))
    nb       = len(communes)
    nb_epci  = communes["epci24txt"].nunique()

    TRAJECTOIRES = [
        (0.625,"62,5 %"),(0.620,"62,0 %"),(0.615,"61,5 %"),(0.610,"61,0 %"),
        (0.607,"60,7 % — SRADDET Occitanie"),(0.605,"60,5 %"),(0.600,"60,0 %"),
        (0.575,"57,5 %"),(0.550,"55,0 %"),(0.525,"52,5 %"),
        (0.500,"50,0 % — Loi Climat (défaut)"),(0.475,"47,5 %"),(0.450,"45,0 %"),
        (0.425,"42,5 %"),(0.400,"40,0 %"),(0.375,"37,5 %"),
    ]
    idx_traj  = st.session_state.get("trajectoire_select", 10)
    coeff_sel = TRAJECTOIRES[idx_traj][0]
    label_sel = TRAJECTOIRES[idx_traj][1]
    pct_sel   = coeff_sel * 100
    facteur   = round(1.0 - coeff_sel, 3)

    st.markdown("## 📄 Export PDF — Rapport SCoT")
    st.markdown(
        f"Rapport **multi-pages A4** pour le SCoT **{nom_scot}** "
        f"({nb} communes  |  {nb_epci} EPCI/CC membres) :")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
- ✅ Couverture SCoT personnalisée
- ✅ Identité SCoT + tableau EPCI membres
- ✅ Métriques agrégées SCoT
- ✅ Graphiques flux annuels agrégés
        """)
    with col2:
        st.markdown("""
- ✅ Top 10 communes + trajectoires ZAN
- ✅ Ratios analytiques SCoT
- ✅ Bilan ZAN SCoT — jauge + projection
- ✅ Conclusion & recommandations DOO
        """)

    st.divider()
    st.info(
        f"📐 **Coefficient ZAN : −{pct_sel:.1f} %** ({label_sel}) — "
        f"Enveloppe SCoT = conso 2011-2020 × {facteur}\n\n"
        "_Modifiez-le dans l'onglet **Analyse & Tendances**._"
    )
    st.divider()

    if st.button("🚀 Générer le rapport PDF SCoT",
                 type="primary", use_container_width=True):
        with st.spinner(
            f"Génération pour {nb} communes ({nb_epci} EPCI)… "
            "agrégation, graphiques, mise en page…"
        ):
            try:
                pdf_bytes = generer_rapport_pdf_scot(communes, coeff_sel)
                nom_fichier = (
                    f"rapport_artificialisation_SCoT_"
                    f"{nom_scot.replace(' ','_')[:40]}_"
                    f"{datetime.now().strftime('%Y%m%d')}.pdf"
                )
                st.success(f"✅ Rapport SCoT généré ! ({len(pdf_bytes)//1024} Ko)")
                st.download_button(
                    label="⬇️ Télécharger le rapport PDF SCoT",
                    data=pdf_bytes,
                    file_name=nom_fichier,
                    mime="application/pdf",
                    use_container_width=True,
                )
            except Exception as e:
                st.error(f"❌ Erreur : {e}")
                raise
