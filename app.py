"""
@author : Philippe PETIT
@version : 3.0.00
@description : Tableau de bord artificialisation (V3.0.0) Détection automatique des champs ajoutés ou de changement de millésime
"""

import sys
import io
import os
from datetime import datetime
from pathlib import Path
import urllib.parse
import webbrowser

from ui.utilitaires import get_coords_from_insee
from ui.sidebar import rendu_sidebar, MODE_COMMUNE, MODE_EPCI, MODE_SCOT


from graphs.graph_epci_general import rendu_general_epci, agreger_epci
from graphs.graph_epci_synthese import rendu_synthese_epci
from graphs.graph_epci_analyse import rendu_analyse_epci
from graphs.graph_epci_ratios import rendu_ratios_epci
from graphs.graph_scot import (
    rendu_general_scot, rendu_synthese_scot,
    rendu_analyse_scot, rendu_ratios_scot,
    rendu_export_pdf_scot,
)

from graphs.graph_export_pdf import *
from graphs.graph_export_pdf_epci import generer_rapport_epci
from graphs.graph_export_pdf_scot import generer_rapport_scot
from core.detecteur import get_col   # ← pour colonnes dynamiques

# =====================================================
# PATH PROJET  (doit être avant les imports locaux)
# =====================================================

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.loader import load_csv
from graphs.graph_synthese import rendu_graph_synthese
from graphs.graph_analyse import rendu_graph_analyse
from graphs.graph_ratios import rendu_ratios
from graphs.graph_epci_general import _bloc_identite_territoriale
from graphs.graph_scot import _bloc_identite_territoriale



import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st


# =====================================================
# CONFIG STREAMLIT
# =====================================================

st.set_page_config(
    layout="wide",
    page_title="Tableau de bord artificialisation communale (V3.0.0)",
    page_icon="📊",
    initial_sidebar_state="expanded"
)


# =====================================================
# UTILITAIRES FORMATAGE
# =====================================================

def m2_to_ha(valeur):
    """Convertit des m² en hectares, arrondi à 2 décimales."""
    try:
        return round(float(valeur) / 10_000, 2) if valeur else 0.0
    except (TypeError, ValueError):
        return 0.0

def fmt_ha(valeur_ha):
    """Formate un nombre en ha avec séparateur de milliers (espace) et virgule décimale."""
    return f"{valeur_ha:,.2f}".replace(",", "\u202f").replace(".", ",")


def fmt_pct(valeur):
    """Formate un pourcentage."""
    try:
        return f"{float(valeur):.2f} %".replace(".", ",")
    except (TypeError, ValueError):
        return "N/A"


# =====================================================
# HEADER
# =====================================================
def afficher_header():
    col_logo, col_texte = st.columns([1, 4])

    with col_logo:
        logo_path = ROOT_DIR / "assets" / "logo.png"
        if logo_path.exists():
            st.image(str(logo_path), width=210)

    with col_texte:
        st.markdown(
            """
            <div style='margin-top:10px;'>
                <h1 style='margin-bottom:0px;'>📊 Tableau de bord artificialisation communale & intercommunale</h1>
                <div style='font-size:1rem; font-weight:600; color:orange; margin-top:6px;'>
                    Version 3.0.0 — Version stable, millésime 2026<br>
                    Auteur : Philippe PETIT — Assistants IA : Copilot, Claude & ChatGPT
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Bouton Aide premium
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        with open("Aide.html", "rb") as f:
            st.download_button(
                "📥 Télécharger l'aide",
                f,
                file_name="Aide.html",
                type="primary"
            )

# =====================================================
# ONGLET — GÉNÉRAL
# =====================================================

def rendu_general(code_insee):
    st.subheader("🏘️ Informations générales")

    df     = st.session_state.get("df")
    struct = st.session_state.get("struct", {})
    if df is None:
        st.warning("Données non chargées.")
        return

    # Colonnes dynamiques selon le millésime détecté
    col_epci     = get_col(struct, "epci",     "epci24")
    col_epci_txt = get_col(struct, "epci_txt", "epci24txt")


    if code_insee:
        commune = df[df["idcom"] == code_insee]

        if not commune.empty:
            ligne = commune.iloc[0]
            nom_commune = ligne['idcomtxt']
            nom_dep     = ligne['iddeptxt']
            nom_region  = ligne['idregtxt']
            url_maps  = f"https://www.google.com/maps/search/{nom_commune}+{nom_dep}".replace(" ", "+")
            url_maps2 = f"https://www.google.com/maps/search/{nom_region}".replace(" ", "+")
            url_maps3 = f"https://www.google.com/maps/search/{nom_dep}".replace(" ", "+")

            st.subheader(f"{ligne['idcom']} - {ligne['idcomtxt']}")

            st.markdown(f"**Commune :** {ligne['idcom']} - {ligne['idcomtxt']} &nbsp; [🗺️ Voir sur Google Maps]({url_maps})")
            st.markdown(f"**Région :** {ligne['idreg']} - {ligne['idregtxt']} &nbsp; [🗺️ Voir sur Google Maps]({url_maps2})")
            st.markdown(f"**Département :** {ligne['iddep']} - {ligne['iddeptxt']} &nbsp; [🗺️ Voir sur Google Maps]({url_maps3})")
            # Colonnes EPCI et SCoT dynamiques
            epci_code = ligne.get(col_epci, "N/D")
            epci_nom  = ligne.get(col_epci_txt, "N/D")
            st.markdown(f"**EPCI :** {epci_code} - {epci_nom}")
            st.markdown(f"**SCoT :** {ligne.get('scot', 'N/D')}")
        else:
            st.warning("Aucune commune trouvée pour ce code INSEE.")
    else:
        st.info("Veuillez saisir un code INSEE dans le menu latéral.")


# =====================================================
# LIRE LES DONNEES
# =====================================================
from data.load_data import lire_les_donnees


# =====================================================
# ONGLET — SYNTHÈSE
# =====================================================

def _to_float(x):
    if x is None:
        return 0.0
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        x = x.replace(",", ".").strip()
        try:
            return float(x)
        except ValueError:
            return 0.0
    return 0.0

def rendu_synthese(code_insee):
    st.subheader("📐 Synthèse")

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

    ligne  = commune.iloc[0]
    struct = st.session_state.get("struct", {})
    donnees = lire_les_donnees(ligne, struct)

    # ─── Métriques principales ──────────────────────────────
    struct = st.session_state.get("struct", {})
    lbl_ref = f"{struct.get('ref_metier_debut', 2011)} – {struct.get('ref_metier_fin', 2020)}"
    lbl_zan = f"{struct.get('zan_metier_debut', 2021)} – {struct.get('zan_metier_fin', 2023)}"

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="📦 Consommation totale",
            value=f"{fmt_ha(donnees['cons_tot_ha'])} ha"
        )
    with col2:
        st.metric(
            label=f"📅 {lbl_ref}",
            value=f"{fmt_ha(donnees['cons_tot2020_ha'])} ha"
        )
    with col3:
        st.metric(
            label=f"📅 {lbl_zan}",
            value=f"{fmt_ha(donnees['cons_tot2130_ha'])} ha"
        )
    with col4:
        st.metric(
            label="📊 % artificialisation",
            value=fmt_pct(donnees['pcent_art_com'])
        )

    st.divider()

    # ─── Tableau récapitulatif par catégorie ────────────────
    st.markdown("#### Détail par catégorie")

    CATEGORIES = ["Activité", "Habitat", "Mixte", "Inconnu", "Route", "Ferroviaire"]
    KEYS       = ["activity", "habitat", "mixte", "inconnu", "route", "ferroviaire"]

    # Indices dynamiques selon la structure détectée
    nb_ref = len(struct.get("suffixes_ref", []))
    nb_zan = len(struct.get("suffixes_zan", []))
    idx_ref_debut = 3
    idx_ref_fin   = 3 + nb_ref
    idx_zan_fin   = idx_ref_fin + nb_zan

    recap = pd.DataFrame({
        "Catégorie": CATEGORIES,
        "Total (ha)": [
            fmt_ha(m2_to_ha(sum(_to_float(v) for v in donnees[k].values()))) 
            for k in KEYS
        ],
        f"{lbl_ref} (ha)": [
            fmt_ha(m2_to_ha(sum(
                _to_float(donnees[k].get(i, 0))
                for i in range(idx_ref_debut, idx_ref_fin)
            ))) 
            for k in KEYS
        ],
        f"{lbl_zan} (ha)": [
            fmt_ha(m2_to_ha(sum(
                _to_float(donnees[k].get(i, 0))
                for i in range(idx_ref_fin, idx_zan_fin)
            ))) 
            for k in KEYS
        ],
    })

    st.dataframe(recap, use_container_width=True, hide_index=True)

    st.divider()

    # ─── Graphiques ─────────────────────────────────────────
    rendu_graph_synthese(donnees)

# =====================================================
# MAIN
# =====================================================

def main():
    afficher_header()

    # ─── SIDEBAR ────────────────────────────────────────────
    with st.sidebar:
        url_maps = "https://www.data.gouv.fr/api/1/datasets/r/8c67a68a-bb1a-4b7e-b221-62ccfb8bc4f9"
        st.sidebar.markdown("### 📥 Données de l'observatoire de l'artificialisation.")
        st.sidebar.markdown(f"[🗺️ Télécharger les données depuis data.gouv.fr]({url_maps})")
        st.sidebar.divider()
        # Contacter le programmeur
        subject = "Tableau de bord artificialisation communale & intercommunale"
        body = """Bonjour,

        Je souhaite signaler un problème sur l'application :

        - Description :
        - Étapes pour reproduire :
        - Résultat attendu :
        """
        subject_encoded = urllib.parse.quote(subject)
        body_encoded = urllib.parse.quote(body)
        url_maps2 = f"mailto:philippe.petit.lafiou@outlook.fr?subject={subject_encoded}&body={body_encoded}"
        st.sidebar.markdown(f"[🗺️ Signaler un bug]({url_maps2})")

        # Chargement du fichier CSV
        with st.expander("📂 Chargement des données", expanded=True):
            file = st.file_uploader("📁 Fichier CSV", type="csv")
            if file:
                df, annees = load_csv(file)
                st.session_state["df"] = df
                st.session_state["annees"] = annees

        if "df" not in st.session_state:
            st.info("⬅️ Chargez un fichier CSV")
            st.stop()

        st.divider()

        # ── Nouveau module sidebar ───────────────────────────────
        ctx = rendu_sidebar(st.session_state["df"])
        TRAJECTOIRES_COEFFS = [
            0.625, 0.620, 0.615, 0.610, 0.607, 0.605, 0.600,
            0.575, 0.550, 0.525, 0.500, 0.475, 0.450, 0.425, 0.400, 0.375,
        ]
        idx_traj        = st.session_state.get("trajectoire_select", 10)  # défaut 50 %
        coeff_reduction = TRAJECTOIRES_COEFFS[idx_traj]

    # ─── Extraction du contexte ──────────────────────────────────
    mode       = ctx["mode"]
    valide     = ctx["valide"]
    ligne      = ctx["ligne"]        # pd.Series ou None
    label      = ctx["label"]        # nom affiché
    df         = st.session_state["df"]
    struct     = st.session_state.get("struct", {})

    # code_insee : défini uniquement si une commune est sélectionnée
    code_insee = ctx.get("zoom_insee") or (ctx["code"] if mode == MODE_COMMUNE else None)
    # On n'a une commune à afficher que si ligne n'est pas None
    commune_ok = valide and ligne is not None
    # Niveau d'agrégation : "commune" | "epci" | "scot"
    niveau     = ctx.get("niveau", mode)

    # ─── STYLE ONGLETS ──────────────────────────────────────────
    st.markdown("""
    <style>
    button[data-baseweb="tab"] {
        font-size: 20px !important;
        font-weight: 700 !important;
        padding: 12px 20px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # ─── TABS ───────────────────────────────────────────────────
    tab_general, tab_synthese, tab_analyse, tab_ratio, tab_export, tab_lien = st.tabs([
        "📊 Général",
        "📐 Synthèse",
        "📈 Analyse & Tendances",
        "📈 Ratios",
        "📄 Export PDF",
        "💾 Liens utiles",
    ])

    MSG_ATTENTE = "⬅️ Veuillez sélectionner une commune ou un territoire dans le menu latéral."

    with tab_general:
        if commune_ok:
            rendu_general(code_insee)
        elif valide and niveau == "epci":
            #_bloc_identite_territoriale(ctx["communes"])
            st.divider()
            rendu_general_epci(ctx["communes"], struct)

        elif valide and niveau == "scot":
            #_bloc_identite_territoriale(ctx["communes"])
            st.divider()
            rendu_general_scot(ctx["communes"], struct, coeff_reduction)

        else:
            st.info(MSG_ATTENTE)

    with tab_synthese:
        if commune_ok:
            st.subheader(label)
            rendu_synthese(code_insee)
        elif valide and niveau == "epci":
            rendu_synthese_epci(ctx["communes"], struct)
        elif valide and niveau == "scot":
            rendu_synthese_scot(ctx["communes"],struct, coeff_reduction)
        else:
            st.info(MSG_ATTENTE)

    with tab_analyse:
        if commune_ok:
            st.subheader(label)
            struct  = st.session_state.get("struct", {})
            donnees = lire_les_donnees(ligne, struct)
            rendu_graph_analyse(donnees)
        elif valide and niveau == "epci":
            rendu_analyse_epci(ctx["communes"], struct)
        elif valide and niveau == "scot":
            rendu_analyse_scot(ctx["communes"], struct)
        else:
            st.info(MSG_ATTENTE)

    with tab_ratio:
        if commune_ok:
            st.subheader(label)
            rendu_ratios(code_insee)
        elif valide and niveau == "epci":
            rendu_ratios_epci(ctx["communes"], struct)
        elif valide and niveau == "scot":
            rendu_ratios_scot(ctx["communes"], struct)
        else:
            st.info(MSG_ATTENTE)

    with tab_export:
        if commune_ok:
            # --- Sélection de la commune ---
            code_insee = st.selectbox(
                "Choisissez une commune",
                ctx["communes"]["idcom"].unique()
            )

            # --- Récupération de la ligne complète ---
            ligne_commune = ctx["communes"][ctx["communes"]["idcom"] == code_insee].iloc[0]

            # --- Coefficient ZAN choisi par l’utilisateur ---
            coeff_reduction = st.slider(
                "Coefficient de réduction ZAN",
                min_value=0.1,
                max_value=0.9,
                value=0.5,
                step=0.01
            )

            # --- Génération du PDF ---
            if st.button("📄 Générer le rapport PDF"):
                with st.spinner("Veuillez patienter... Traitement du rapport en cours..."):
                    pdf_bytes = generer_rapport_pdf(ligne_commune, coeff_reduction)
                st.success("Rapport généré avec succès ! Vous pouvez maintenant le télécharger.")

                st.download_button(
                    "📥 Télécharger le rapport PDF",
                    pdf_bytes,
                    file_name=f"rapport_{code_insee}.pdf",
                    mime="application/pdf"
                )
        elif valide and niveau == "epci":
            epci_df = ctx["communes"]      # toutes les communes de l’EPCI
            if st.button("📄 Générer le rapport PDF"):
                with st.spinner(f"Veuillez patienter... Traitement du rapport en cours..."):
                    pdf_bytes = generer_rapport_epci(epci_df, struct)
                st.success("Rapport généré avec succès ! Vous pouvez maintenant le télécharger.")

                st.download_button(
                    "📄 Télécharger le rapport PDF EPCI",
                    pdf_bytes,
                    file_name="rapport_epci.pdf",
                    mime="application/pdf"
                )
        elif valide and niveau == "scot":
            scot_df = ctx["communes"]      # toutes les communes du SCoT
            if st.button("📄 Générer le rapport PDF"):
                with st.spinner("Veuillez patienter... Traitement du rapport en cours..."):
                    pdf_bytes = generer_rapport_scot(scot_df, struct)
                st.success("Rapport généré avec succès ! Vous pouvez maintenant le télécharger.")

                st.download_button(
                    "📄 Télécharger le rapport PDF SCoT",
                    pdf_bytes,
                    file_name="rapport_scot.pdf",
                    mime="application/pdf"
                )
            st.info(MSG_ATTENTE)

    with tab_lien:
        st.write("Découvrez votre commune...")
        if commune_ok:
            struct       = st.session_state.get("struct", {})
            col_epci     = get_col(struct, "epci",     "epci24")
            nom_commune  = ligne['idcom']
            epci_siret   = ligne.get(col_epci, "")
            region       = ligne['idregtxt']
            departement  = ligne['iddep']
            lat, lon = get_coords_from_insee(code_insee)
            url_maps = f"https://www.geoportail.gouv.fr/carte?c={lon},{lat}&z=15&l0=ORTHOIMAGERY.ORTHOPHOTOS::GEOPORTAIL:OGC:WMTS(1)&v1=PLAN.IGN::GEOPORTAIL:GPP:TMS(1;s:standard)&l2=OCSGE.COUVERTURE::GEOPORTAIL:OGC:WMTS(0.6)&l3=OCSGE.USAGE::GEOPORTAIL:OGC:WMTS(0.6)&permalink=yes"
            st.markdown(f"[🗺️ OCSGE (L'OCS GE est une base de données qui contribue au suivi de l'occupation du sol, et à celui de l'usage des sols)]({url_maps})")
            
            url_maps2 = f"https://www.geoportail-urbanisme.gouv.fr/map/#tile=1&lon={lon}&lat={lat}&zoom=12&mlon={lon}&mlat={lat}"
            st.markdown(f"[🗺️ Document d'urbanisme (Le Géoportail de l'urbanisme a pour mission de rendre accessibles les documents d'urbanisme et les servitudes d'utilité publique à tous les utilisateurs du)]({url_maps2})")

            url_maps3 = f"https://www.geoportail.gouv.fr/carte?c={lon},{lat}&z=14&l0=ORTHOIMAGERY.ORTHOPHOTOS::GEOPORTAIL:OGC:WMTS(1)&l1=LANDUSE.AGRICULTURE2021::GEOPORTAIL:OGC:WMTS(0.8)&permalink=yes"
            st.markdown(f"[🗺️ RPG 2022 (Le Registre parcellaire graphique (RPG) est un système d'information géographique représentant au 1/5000ème les îlots culturaux)]({url_maps3})")

            url_maps4 = f"https://cadastre.data.gouv.fr/map?style=ortho&parcelleId=315160000A0432#16.00/{lat}/{lon}"
            st.markdown(f"[🗺️ CADASTRE (Le cadastre est le registre public qui recense et identifie les propriétés foncières (immeuble, maison, terrain, etc.).)]({url_maps4})")

            st.divider()
            
            url_maps5 = f"https://www.insee.fr/fr/statistiques/2011101?geo=COM-{nom_commune}"
            st.markdown(f"[🗺️ INSEE : Dossier complet commune]({url_maps5})")

            url_maps6 = f"https://www.picto-occitanie.fr/geoclip/#c=report&chapter=demo&report=r01&selgeo1=com16.{nom_commune}&selgeo2=epci.{epci_siret}"
            st.markdown(f"[🗺️ Picto-Stat]({url_maps6})")

            url_maps7 = f"https://observatoire.atd31.fr/#c=report&chapter=demo&report=r01&selgeo1=com.{nom_commune}&selgeo2=dep.{departement}"
            st.markdown(f"[🗺️ HGI-GeObservatoire]({url_maps7})")

            st.divider()

            url_maps8 = f"https://inpn.mnhn.fr/"
            st.markdown(f"[🗺️ Inventaire National du Patrimoine Naturel]({url_maps8})")

            url_maps8 = f"https://remonterletemps.ign.fr/comparer?lon={lon}&lat={lat}&z=13.0&layer1=10&layer2=19&mode=mag"
            st.markdown(f"[🗺️ IGN - Remonter le temps]({url_maps8})")

            st.divider()

            url_maps9 = f"https://macarte.ign.fr/carte/1X3jxe/Carte-EnR-Grand-public"
            st.markdown(f"[🗺️ Portail cartographique des énergies renouvelables (Accès grand public)]({url_maps9})")

            url_maps10 = f"http://arec-occitanie.terristory.fr/?zone=commune&maille=commune&zone_id={nom_commune}&id_tableau=643"
            st.markdown(f"[🗺️ TerriSTORY®]({url_maps10})")

            st.divider()

            url_maps11 = f"https://explore.data.gouv.fr/fr/immobilier?onglet=carte&filtre=tous&lat={lat}&lng={lon}&zoom=12.00&code={nom_commune}&level=commune"
            st.markdown(f"[🗺️ Explorateur de données de valeurs foncières]({url_maps11})")

        else:
            st.info("Veuillez saisir un code INSEE dans le menu latéral.")


if __name__ == "__main__":
    main()
