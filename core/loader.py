"""
@author  : Philippe PETIT
@version : 3.0.0
@description : Chargement du CSV CEREMA avec détection automatique de structure.
               Stocke le dict 'struct' dans st.session_state["struct"]
               pour être utilisé par tous les modules.
"""

import pandas as pd
import streamlit as st
from core.detecteur import detecter_structure, afficher_structure_streamlit


def load_csv(file) -> tuple[pd.DataFrame, list]:
    """
    Charge le CSV CEREMA, détecte la structure et retourne (df, annees).
    Stocke automatiquement struct dans st.session_state["struct"].
    """
    # ── Chargement ───────────────────────────────────────────────
    try:
        df = pd.read_csv(file, sep=";", dtype=str, low_memory=False)
    except Exception as e:
        st.error(f"Erreur de lecture du fichier CSV : {e}")
        return pd.DataFrame(), []

    # Nettoyage des noms de colonnes
    df.columns = df.columns.str.strip().str.replace('"', '')

    # Conversion numérique des colonnes numériques
    for col in df.columns:
        try:
            df[col] = pd.to_numeric(df[col], errors="ignore")
        except Exception:
            pass

    # ── Détection de la structure ────────────────────────────────
    struct = detecter_structure(df)

    # Stockage en session
    st.session_state["struct"] = struct

    # Affichage du résumé dans la sidebar
    afficher_structure_streamlit(struct)

    # Liste des années pour compatibilité ascendante
    annees = struct["annees_flux"]

    return df, annees
