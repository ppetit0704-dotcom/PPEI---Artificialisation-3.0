"""
@author  : Philippe PETIT
@version : 2.0.0
@description : Sidebar intelligente — 3 modes de navigation territoriale :
               Commune (INSEE) / EPCI-CC (SIRET) / SCoT (nom)
"""

import streamlit as st
import pandas as pd

MODE_COMMUNE = "commune"
MODE_EPCI    = "epci"
MODE_SCOT    = "scot"


def _chercher_commune(df, code):
    return df[df["idcom"].astype(str).str.strip() == code.strip()]

def _chercher_epci(df, siret):
    return df[df["epci24"].astype(str).str.strip() == siret.strip()]

def _chercher_scot(df, nom):
    return df[df["scot"].astype(str).str.strip() == nom.strip()]

def _liste_scots(df):
    return sorted(df["scot"].dropna().astype(str).unique().tolist())

def _bloc_zoom(communes, key_prefix):
    nb = len(communes)
    options = ["— Toutes les communes —"] + [
        f"{r['idcom']} — {r['idcomtxt']}"
        for _, r in communes.sort_values("idcomtxt").iterrows()
    ]
    choix = st.selectbox(
        f"Zoom sur une commune ({nb} membres)",
        options=options,
        key=f"{key_prefix}_zoom",
    )
    if choix != "— Toutes les communes —":
        code_zoom = choix.split(" — ")[0]
        cz = communes[communes["idcom"].astype(str) == code_zoom]
        return {"zoom_insee": code_zoom, "ligne": cz.iloc[0] if not cz.empty else None,
                "label_zoom": choix, "commune": cz}
    return {"zoom_insee": None, "ligne": None, "label_zoom": None, "commune": pd.DataFrame()}


def rendu_sidebar(df: pd.DataFrame) -> dict:
    st.markdown("## 📋 Menu de pilotage")
    st.caption("Chargement, filtres et navigation")
    st.divider()

    st.markdown("#### 🔍 Niveau territorial")
    mode = st.radio(
        "Mode", options=[MODE_COMMUNE, MODE_EPCI, MODE_SCOT],
        format_func=lambda m: {
            MODE_COMMUNE: "🏘️ Commune  (code INSEE)",
            MODE_EPCI:    "🏛️ Intercommunalité  (SIRET EPCI)",
            MODE_SCOT:    "🗺️ SCoT  (Schéma de Cohérence Territoriale)",
        }[m],
        key="sidebar_mode", label_visibility="collapsed",
    )
    st.session_state["mode"] = mode
    st.divider()

    ctx = {"mode": mode, "code": "", "label": "", "commune": pd.DataFrame(),
           "communes": pd.DataFrame(), "ligne": None, "valide": False,
           "zoom_insee": None, "niveau": mode}

    # ── MODE COMMUNE ─────────────────────────────────────────────
    if mode == MODE_COMMUNE:
        code = st.text_input("🏘️ Code INSEE", placeholder="Ex : 31555",
                             max_chars=5, key="input_insee")
        if code and not code.isdigit():
            st.error("Code INSEE : chiffres uniquement.")
            return ctx
        if code:
            commune = _chercher_commune(df, code)
            if commune.empty:
                st.warning(f"Commune introuvable : **{code}**")
                return ctx
            ligne = commune.iloc[0]
            st.success(f"**{code}** — {ligne.get('idcomtxt','')}")
            st.caption(f"EPCI : {ligne.get('epci24txt','')}  |  SCoT : {ligne.get('scot','')}")
            ctx.update({"code": code, "label": f"{code} — {ligne.get('idcomtxt','')}",
                        "commune": commune, "communes": commune, "ligne": ligne,
                        "valide": True, "niveau": "commune"})

    # ── MODE EPCI ────────────────────────────────────────────────
    elif mode == MODE_EPCI:
        siret = st.text_input("🏛️ SIRET EPCI", placeholder="Ex : 200069193",
                              max_chars=9, key="input_siret")
        if siret and not siret.isdigit():
            st.error("SIRET : chiffres uniquement.")
            return ctx

        with st.expander("🔎 Rechercher par nom de CC", expanded=not bool(siret)):
            rech = st.text_input("Nom CC", placeholder="Ex : Frontonnais",
                                 key="rech_epci")
            if rech and len(rech) >= 3:
                res = df[df["epci24txt"].str.contains(rech, case=False, na=False)
                        ][["epci24","epci24txt"]].drop_duplicates().head(10)
                if res.empty:
                    st.info("Aucune CC trouvée.")
                else:
                    for _, row in res.iterrows():
                        c1, c2 = st.columns([1,3])
                        c1.code(row["epci24"]); c2.write(row["epci24txt"])

        if siret:
            communes = _chercher_epci(df, siret)
            if communes.empty:
                st.warning(f"SIRET introuvable : **{siret}**")
                return ctx
            nom = communes.iloc[0].get("epci24txt", siret)
            st.success(f"**{nom}**")
            st.caption(f"SIRET : {siret}  |  {len(communes)} commune(s)")
            zoom = _bloc_zoom(communes, "epci")
            if zoom["zoom_insee"]:
                ctx.update({"code": siret, "label": f"{nom}  ›  {zoom['label_zoom']}",
                            "commune": zoom["commune"], "communes": communes,
                            "ligne": zoom["ligne"], "valide": True,
                            "zoom_insee": zoom["zoom_insee"], "niveau": "commune"})
            else:
                ctx.update({"code": siret, "label": nom, "communes": communes,
                            "valide": True, "niveau": "epci"})

    # ── MODE SCOT ────────────────────────────────────────────────
    else:
        nom_scot = None

        with st.expander("🔎 Rechercher un SCoT", expanded=True):
            rech = st.text_input("Nom du SCoT", placeholder="Ex : Toulousain",
                                 key="rech_scot")
            if rech and len(rech) >= 2:
                resultats = [s for s in _liste_scots(df) if rech.lower() in s.lower()]
                if not resultats:
                    st.info("Aucun SCoT trouvé.")
                else:
                    st.markdown(f"**{len(resultats)} SCoT(s) :**")
                    nom_scot = st.radio("", options=resultats,
                                        key="scot_radio", label_visibility="collapsed")

        with st.expander("📋 Liste complète des SCoT", expanded=False):
            choix = st.selectbox("", options=["— Choisir —"] + _liste_scots(df),
                                 key="scot_select", label_visibility="collapsed")
            if choix != "— Choisir —":
                nom_scot = choix

        if nom_scot:
            communes = _chercher_scot(df, nom_scot)
            if communes.empty:
                st.warning(f"SCoT introuvable : **{nom_scot}**")
                return ctx

            nb_epci = communes["epci24txt"].nunique()
            st.success(f"**{nom_scot}**")
            st.caption(f"{len(communes)} communes  |  {nb_epci} EPCI/CC membres")

            # Filtre optionnel par EPCI dans le SCoT
            with st.expander("🏛️ Filtrer par EPCI", expanded=False):
                epci_list = ["— Tout le SCoT —"] + sorted(
                    communes["epci24txt"].dropna().unique().tolist())
                epci_choix = st.selectbox("EPCI", options=epci_list,
                                          key="scot_filtre_epci",
                                          label_visibility="collapsed")
                if epci_choix != "— Tout le SCoT —":
                    communes = communes[communes["epci24txt"] == epci_choix]
                    st.caption(f"Filtré : {epci_choix} ({len(communes)} communes)")

            zoom = _bloc_zoom(communes, "scot")
            if zoom["zoom_insee"]:
                ctx.update({"code": nom_scot,
                            "label": f"{nom_scot}  ›  {zoom['label_zoom']}",
                            "commune": zoom["commune"], "communes": communes,
                            "ligne": zoom["ligne"], "valide": True,
                            "zoom_insee": zoom["zoom_insee"], "niveau": "commune"})
            else:
                ctx.update({"code": nom_scot, "label": nom_scot,
                            "communes": communes, "valide": True, "niveau": "scot"})

    return ctx
