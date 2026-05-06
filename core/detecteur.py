"""
@author  : Philippe PETIT
@version : 3.0.0
@description : Détecteur automatique de structure du fichier CEREMA.
               Utilise une GRAMMAIRE centralisée de patterns regex pour
               identifier et classer toutes les colonnes du CSV.
               S'adapte automatiquement aux futurs millésimes CEREMA.

               Convention CEREMA :
                 art{a}{cat}{b} = flux du 01/01/20{a} au 31/12/20{a}
                 L'année MÉTIER = a (année de début) = b - 1
                 ex : art22hab23 → habitat consommé du 01/01/2022 au 31/12/2022

               Usage :
                   from core.detecteur import detecter_structure, GRAMMAIRE
                   struct = detecter_structure(df)
"""

import re
import warnings
from typing import Any
import pandas as pd


# ═════════════════════════════════════════════════════════════════
#  GRAMMAIRE CEREMA — SOURCE UNIQUE DE VÉRITÉ
# ═════════════════════════════════════════════════════════════════

GRAMMAIRE: dict[str, str] = {
    # ── Identifiants géographiques ───────────────────────────────
    "idcom":        r"^idcom$",
    "idcomtxt":     r"^idcomtxt$",
    "idreg":        r"^idreg$",
    "idregtxt":     r"^idregtxt$",
    "iddep":        r"^iddep$",
    "iddeptxt":     r"^iddeptxt$",
    "epci":         r"^epci\d{2}$",
    "epcitxt":      r"^epci\d{2}txt$",
    "scot":         r"^scot$",

    # ── Aires d'attraction des villes (AAV) ──────────────────────
    "aav":          r"^aav(\d{4})(txt|_typo)?$",

    # ── Flux CEREMA annuels (catégories) ─────────────────────────
    # CONSÉCUTIFS UNIQUEMENT : b = a + 1 (vérifié à la détection)
    "flux":         r"^art(\d{2})(act|hab|mix|rou|fer|inc)(\d{2})$",

    # ── Flux NAF → artificialisation ─────────────────────────────
    "naf_flux":     r"^naf(\d{2})art(\d{2})$",

    # ── Totaux cumulatifs artificialisation ───────────────────────
    "artcom":       r"^artcom(\d{2})(\d{2})$",

    # ── Démographie / ménages / emploi ───────────────────────────
    # Couvre : pop15, men21, emp19, mepart1521, menhab1521, artpop1521
    "demographie":  r"^(pop|men|emp|mepart|menhab|artpop)(\d{2})(\d{2})?$",

    # ── Stock de surface ─────────────────────────────────────────
    # Couvre : surfcom2024, surfartif2024, etc.
    "stock":        r"^surf([a-z]+)(\d{4})$",
}

# Compilation des patterns (une seule fois au import)
_COMPILED: dict[str, re.Pattern] = {
    nom: re.compile(pattern, re.IGNORECASE)
    for nom, pattern in GRAMMAIRE.items()
}


# ═════════════════════════════════════════════════════════════════
#  CLASSIFICATEUR DE COLONNES
# ═════════════════════════════════════════════════════════════════

def classifier_colonne(col: str) -> tuple[str | None, re.Match | None]:
    """
    Classe une colonne selon la grammaire.
    Retourne (nom_type, match) ou (None, None) si non reconnue.
    """
    for nom, pattern in _COMPILED.items():
        m = pattern.match(col)
        if m:
            return nom, m
    return None, None


def classifier_toutes(colonnes: list[str]) -> dict[str, list[tuple[str, re.Match]]]:
    """
    Classifie toutes les colonnes.
    Retourne un dict {type: [(col, match), ...]}
    """
    result: dict[str, list] = {nom: [] for nom in GRAMMAIRE}
    result["inconnu"] = []

    for col in colonnes:
        typ, match = classifier_colonne(col)
        if typ:
            result[typ].append((col, match))
        else:
            result["inconnu"].append((col, None))

    return result


# ═════════════════════════════════════════════════════════════════
#  UTILITAIRES
# ═════════════════════════════════════════════════════════════════

def _annee_2d(yy: int) -> int:
    """Convertit 2 chiffres en année réelle (9→2009, 24→2024)."""
    return 2000 + yy


# ═════════════════════════════════════════════════════════════════
#  EXTRACTION PAR TYPE
# ═════════════════════════════════════════════════════════════════

def _extraire_flux(classes: dict) -> tuple[list, list]:
    """
    Extrait les suffixes de flux annuels CONSÉCUTIFS (b = a+1).
    Retourne (suffixes_all, cats_presentes).
    """
    flux_trouve: dict[tuple[int,int], set[str]] = {}

    for col, m in classes.get("flux", []):
        a   = int(m.group(1))
        cat = m.group(2).lower()
        b   = int(m.group(3))
        # Filtre strict : consécutif uniquement (exclut art09xxx24, etc.)
        if b != a + 1:
            continue
        flux_trouve.setdefault((a, b), set()).add(cat)

    suffixes_all = sorted(
        [(f"{a:02d}", f"{b:02d}") for (a, b) in flux_trouve],
        key=lambda x: int(x[1])
    )
    cats = sorted({cat for cats in flux_trouve.values() for cat in cats})
    return suffixes_all, cats


def _extraire_demographie(classes: dict) -> dict:
    """
    Extrait les colonnes démographiques (pop, men, emp, etc.).
    Pour chaque indicateur, retourne les deux millésimes les plus récents.
    """
    indicateurs: dict[str, list[tuple[int, int | None, str]]] = {}

    for col, m in classes.get("demographie", []):
        prefixe  = m.group(1).lower()
        yy1      = int(m.group(2))
        yy2      = int(m.group(3)) if m.group(3) else None
        indicateurs.setdefault(prefixe, []).append((yy1, yy2, col))

    result = {}
    for prefixe, entrees in indicateurs.items():
        # Colonnes simples (ex: pop15, men21) : yy2 est None
        simples = sorted(
            [(yy1, col) for yy1, yy2, col in entrees if yy2 is None],
            key=lambda x: x[0]
        )
        # Colonnes calculées (ex: pop1521, mepart1521) : yy2 présent
        calculees = [(yy1, yy2, col) for yy1, yy2, col in entrees if yy2 is not None]

        if len(simples) >= 2:
            result[f"col_{prefixe}1"] = simples[-2][1]  # avant-dernier millésime
            result[f"col_{prefixe}2"] = simples[-1][1]  # dernier millésime
        elif len(simples) == 1:
            result[f"col_{prefixe}1"] = simples[0][1]
            result[f"col_{prefixe}2"] = simples[0][1]

        result[f"{prefixe}_annees"] = [yy1 for yy1, _ in simples]

        # Colonnes calculées
        for yy1, yy2, col in calculees:
            result[f"col_{prefixe}{yy1:02d}{yy2:02d}"] = col

    return result


def _extraire_epci(classes: dict) -> dict:
    """Détecte la colonne EPCI la plus récente."""
    epci_entries = [(int(m.group(0)[-2:]) if m.group(0).endswith('txt') == False
                     else int(m.group(0).replace('txt','')[-2:]), col)
                    for col, m in classes.get("epci", [])]

    # Re-parse proprement
    epci_annees = []
    for col, m in classes.get("epci", []):
        yy = int(re.search(r'\d{2}', col).group())
        epci_annees.append((yy, col))

    if not epci_annees:
        return {"col_epci": "epci24", "col_epci_txt": "epci24txt"}

    yy_max = max(yy for yy, _ in epci_annees)
    return {
        "col_epci":     f"epci{yy_max:02d}",
        "col_epci_txt": f"epci{yy_max:02d}txt",
        "epci_annee":   yy_max,
    }


def _extraire_stock(classes: dict) -> dict:
    """Détecte les colonnes de stock (surfcom, surfartif, etc.)."""
    result = {}
    stocks: dict[str, list[tuple[int, str]]] = {}

    for col, m in classes.get("stock", []):
        suffixe = m.group(1).lower()   # ex: "com", "artif"
        annee   = int(m.group(2))      # ex: 2024
        stocks.setdefault(suffixe, []).append((annee, col))

    for suffixe, entrees in stocks.items():
        entrees.sort(key=lambda x: x[0], reverse=True)
        col_plus_recent = entrees[0][1]
        result[f"col_surf{suffixe}"] = col_plus_recent

    # Alias pratique pour surfcom
    if "col_surfcom" not in result:
        result["col_surfcom"] = "surfcom2024"  # fallback

    return result


def _extraire_artcom(classes: dict) -> dict:
    """Détecte la colonne artcom la plus récente."""
    artcom_entries = []
    for col, m in classes.get("artcom", []):
        b = int(m.group(2))
        artcom_entries.append((b, col))

    if not artcom_entries:
        return {"col_artcom": "artcom0924"}

    artcom_entries.sort(reverse=True)
    return {"col_artcom": artcom_entries[0][1]}


# ═════════════════════════════════════════════════════════════════
#  DÉTECTION DES PÉRIODES
# ═════════════════════════════════════════════════════════════════

def _detecter_periodes(suffixes_all: list) -> dict:
    """
    Détermine les périodes de référence et ZAN.

    Convention CEREMA :
      art{a}{cat}{b}  →  année métier = a  (01/01/20{a} → 31/12/20{a})
      b = a + 1  (flux consécutif)

    Période de référence officielle : années métier 2011 → 2020
      = suffixes avec a in 11..20, b = a+1 in 12..21
    Période ZAN : années métier après 2020
    """
    annees_metier = sorted({_annee_2d(int(a)) for a, _ in suffixes_all})

    if not annees_metier:
        return {}

    an_min = annees_metier[0]
    an_max = annees_metier[-1]

    # Détection période de référence (années métier 2011-2020)
    REF_DUREE = 10
    candidats_ref = [a for a in annees_metier if 2011 <= a <= 2020]

    if len(candidats_ref) == REF_DUREE:
        ref_metier_debut = 2011
        ref_metier_fin   = 2020
    elif len(candidats_ref) >= 5:
        ref_metier_debut = min(candidats_ref)
        ref_metier_fin   = max(candidats_ref)
    else:
        ref_metier_debut = annees_metier[0]
        ref_metier_fin   = annees_metier[min(REF_DUREE - 1, len(annees_metier) - 1)]
        warnings.warn(
            f"Période de référence non standard : {ref_metier_debut}-{ref_metier_fin}",
            UserWarning, stacklevel=3
        )

    # Période ZAN = années métier après la référence
    zan_annees = [a for a in annees_metier if a > ref_metier_fin]
    zan_metier_debut = zan_annees[0]  if zan_annees else ref_metier_fin + 1
    zan_metier_fin   = zan_annees[-1] if zan_annees else ref_metier_fin + 1

    duree_ref        = ref_metier_fin - ref_metier_debut + 1
    duree_zan        = zan_metier_fin - zan_metier_debut + 1
    annees_restantes = max(0, 2031 - zan_metier_fin - 1)

    # Années techniques (valeurs de b dans les colonnes)
    ref_debut = ref_metier_debut + 1   # 2012
    ref_fin   = ref_metier_fin   + 1   # 2021
    zan_debut = zan_metier_debut + 1   # 2022
    zan_fin   = zan_metier_fin   + 1   # 2024

    return {
        # Techniques (pour filtres colonnes)
        "ref_debut":         ref_debut,
        "ref_fin":           ref_fin,
        "zan_debut":         zan_debut,
        "zan_fin":           zan_fin,
        # Métier (pour affichage et libellés)
        "ref_metier_debut":  ref_metier_debut,
        "ref_metier_fin":    ref_metier_fin,
        "zan_metier_debut":  zan_metier_debut,
        "zan_metier_fin":    zan_metier_fin,
        # Durées
        "duree_ref":         duree_ref,
        "duree_zan":         duree_zan,
        "annees_restantes":  annees_restantes,
        "an_min":            an_min,
        "an_max":            an_max,
    }


# ═════════════════════════════════════════════════════════════════
#  DÉTECTEUR PRINCIPAL
# ═════════════════════════════════════════════════════════════════

def detecter_structure(df: pd.DataFrame) -> dict[str, Any]:
    """
    Analyse les colonnes d'un DataFrame CEREMA via la GRAMMAIRE
    et retourne un dict de tous les paramètres de structure.
    """
    colonnes = list(df.columns)

    # ── 1. Classification via GRAMMAIRE ─────────────────────────
    classes = classifier_toutes(colonnes)

    # ── 2. Extraction par type ───────────────────────────────────
    suffixes_all, cats_presentes = _extraire_flux(classes)
    annees_flux = sorted({_annee_2d(int(a)) for a, _ in suffixes_all})

    periodes = _detecter_periodes(suffixes_all)

    # Suffixes par période (filtre sur années métier = a)
    suffixes_ref = [
        (a, b) for (a, b) in suffixes_all
        if periodes.get("ref_metier_debut", 0)
           <= _annee_2d(int(a))
           <= periodes.get("ref_metier_fin", 9999)
    ]
    suffixes_zan = [
        (a, b) for (a, b) in suffixes_all
        if periodes.get("zan_metier_debut", 0)
           <= _annee_2d(int(a))
           <= periodes.get("zan_metier_fin", 9999)
    ]

    demographie = _extraire_demographie(classes)
    epci        = _extraire_epci(classes)
    stock       = _extraire_stock(classes)
    artcom      = _extraire_artcom(classes)

    # ── 3. Assemblage ────────────────────────────────────────────
    struct = {
        # Flux
        "annees_flux":    annees_flux,
        "suffixes_all":   suffixes_all,
        "suffixes_ref":   suffixes_ref,
        "suffixes_zan":   suffixes_zan,
        "cats":           cats_presentes,
        "nb_flux":        len(suffixes_all),
        "nb_communes":    len(df),

        # Périodes
        **periodes,

        # Démographie
        **demographie,

        # EPCI / stock / artcom
        **epci,
        **stock,
        **artcom,

        # Classification complète (accessible si besoin)
        "_classes": classes,
    }

    # ── 4. Résumé lisible ────────────────────────────────────────
    struct["resume"] = (
        f"Structure CEREMA détectée :\n"
        f"  • Flux disponibles   : {annees_flux[0] if annees_flux else '?'}"
        f" → {annees_flux[-1] if annees_flux else '?'}"
        f" ({len(suffixes_all)} années)\n"
        f"  • Catégories         : {', '.join(cats_presentes)}\n"
        f"  • Période référence  : {periodes.get('ref_metier_debut','?')}"
        f" – {periodes.get('ref_metier_fin','?')}"
        f"  (01/01/{periodes.get('ref_metier_debut','?')}"
        f" → 31/12/{periodes.get('ref_metier_fin','?')},"
        f" {periodes.get('duree_ref','?')} ans)\n"
        f"  • Période ZAN        : {periodes.get('zan_metier_debut','?')}"
        f" – {periodes.get('zan_metier_fin','?')}"
        f"  (01/01/{periodes.get('zan_metier_debut','?')}"
        f" → 31/12/{periodes.get('zan_metier_fin','?')},"
        f" {periodes.get('duree_zan','?')} ans observées,"
        f" {periodes.get('annees_restantes','?')} restantes jusqu'en 2031)\n"
        f"  • Population         : {demographie.get('col_pop1','?')}"
        f" / {demographie.get('col_pop2','?')}\n"
        f"  • EPCI               : {epci.get('col_epci','?')}\n"
        f"  • Surface communale  : {stock.get('col_surfcom','?')}\n"
        f"  • % artificialisation: {artcom.get('col_artcom','?')}\n"
        f"  • Colonnes inconnues : {len(classes.get('inconnu',[]))}"
    )

    return struct


# ═════════════════════════════════════════════════════════════════
#  HELPERS POUR LES MODULES
# ═════════════════════════════════════════════════════════════════

def get_col(struct: dict, nom: str, fallback: str = "") -> str:
    """
    Retourne le nom de colonne détecté pour un indicateur.
    Noms : "pop1","pop2","men1","men2","emp1","emp2",
           "epci","epci_txt","surfcom","artcom"
    """
    mapping = {
        "pop1":     "col_pop1",
        "pop2":     "col_pop2",
        "men1":     "col_men1",
        "men2":     "col_men2",
        "emp1":     "col_emp1",
        "emp2":     "col_emp2",
        "epci":     "col_epci",
        "epci_txt": "col_epci_txt",
        "surfcom":  "col_surfcom",
        "artcom":   "col_artcom",
    }
    return struct.get(mapping.get(nom, nom), fallback)


def get_suffixes_periode(struct: dict, periode: str) -> list:
    """Retourne les suffixes pour "ref", "zan" ou "all"."""
    return struct.get(f"suffixes_{periode}" if periode != "all"
                      else "suffixes_all", [])


def get_years_for_load_data(struct: dict) -> list[tuple[int, str, str]]:
    """
    Retourne [(index, yy1, yy2), ...] pour load_data.py.
    Index commence à 3 pour compatibilité avec l'existant.
    """
    return [(i, a, b) for i, (a, b) in enumerate(struct["suffixes_all"], start=3)]


def afficher_structure_streamlit(struct: dict) -> None:
    """Affiche le résumé de structure dans Streamlit."""
    try:
        import streamlit as st
        with st.expander("🔍 Structure du fichier CEREMA détectée", expanded=False):
            st.code(struct["resume"], language=None)
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Années de flux", len(struct["annees_flux"]))
            col2.metric("Période référence",
                        f"{struct.get('ref_metier_debut','?')}"
                        f"–{struct.get('ref_metier_fin','?')}")
            col3.metric("Période ZAN",
                        f"{struct.get('zan_metier_debut','?')}"
                        f"–{struct.get('zan_metier_fin','?')}")
            col4.metric("Années restantes", struct.get("annees_restantes","?"))
    except ImportError:
        print(struct["resume"])
