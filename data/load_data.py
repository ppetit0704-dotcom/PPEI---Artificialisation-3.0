"""
@author  : Philippe PETIT
@version : 3.1.0
@description : Lecture et calcul des données d'artificialisation.
               Version adaptative : utilise core/detecteur.py pour
               s'adapter automatiquement à la structure du fichier CEREMA
               quelle que soit l'année de millésime.
"""

import pandas as pd
import numpy as np
from core.detecteur import detecter_structure, get_col


# ─────────────────────────────────────────────────────────────────
#  UTILITAIRES
# ─────────────────────────────────────────────────────────────────

def m2_to_ha(valeur):
    try:
        return round(float(valeur) / 10_000, 2) if valeur else 0.0
    except (TypeError, ValueError):
        return 0.0


def _to_float(x):
    """Convertit en float de manière robuste (gère str, None, etc.)."""
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


def compute_totals(d: dict, suffixes_ref: list, suffixes_zan: list) -> tuple:
    """
    Calcule les 4 sous-totaux d'un dict {index: valeur}.
    Compatible avec n'importe quelle structure d'années.
    """
    # Normaliser les clés en int si possible
    d_norm = {}
    for k, v in d.items():
        try:
            k_int = int(k)
        except (TypeError, ValueError):
            # clé non numérique → on l’ignore pour les totaux indexés
            continue
        d_norm[k_int] = _to_float(v)

    total    = max(sum(d_norm.values()), 0)

    ref_keys = list(range(3, 3 + len(suffixes_ref)))
    zan_keys = list(range(3 + len(suffixes_ref),
                          3 + len(suffixes_ref) + len(suffixes_zan)))

    tot_ref  = max(sum(d_norm.get(i, 0.0) for i in ref_keys), 0)
    tot_zan  = sum(d_norm.get(i, 0.0) for i in zan_keys)
    # tot_1319 conservé pour compatibilité (indices 4-11)
    tot_1319 = sum(d_norm.get(i, 0.0) for i in range(4, 12))

    return total, tot_ref, tot_1319, tot_zan



# ─────────────────────────────────────────────────────────────────
#  LECTURE ADAPTATIVE
# ─────────────────────────────────────────────────────────────────

def lire_les_donnees(ligne: pd.Series, struct: dict = None) -> dict:
    """
    Lit et calcule toutes les données d'artificialisation pour une ligne.

    struct : dict retourné par detecter_structure(df).
             Si None, une détection minimale est effectuée sur la ligne.
             Recommandé : passer le struct stocké dans session_state.
    """
    # ── Détection de la structure si non fournie ─────────────────
    if struct is None:
        # Fallback : reconstitution minimale depuis la ligne seule
        import re
        _RE_FLUX = re.compile(r'^art(\d{2})(act|hab|mix|rou|fer|inc)(\d{2})$')
        suffixes_all = sorted(
            {(m.group(1), m.group(3))
             for col in ligne.index
             if (m := _RE_FLUX.match(str(col)))},
            key=lambda x: int(x[1])
        )
        # On ignore explicitement les flux avant 2011 (09,10)
        suffixes_all = [(a, b) for (a, b) in suffixes_all if int(a) >= 11]

        n = len(suffixes_all)
        # Par défaut : 10 ans de référence, reste = ZAN
        suffixes_ref = suffixes_all[:10] if n >= 10 else suffixes_all
        suffixes_zan = suffixes_all[10:] if n > 10 else []

        suffixes = suffixes_ref + suffixes_zan

        col_pop1 = "pop15"; col_pop2 = "pop21"
        col_men1 = "men15"; col_men2 = "men21"
        col_emp1 = "emp15"; col_emp2 = "emp21"
        col_surf = "surfcom2024"
        col_artcom = "artcom0924"
        duree_zan = max(len(suffixes_zan), 1)
        annees_restantes = 7
    else:
        # On s'appuie sur la structure détectée
        # suffixes_all peut contenir des flux antérieurs (09,10),
        # mais suffixes_ref / suffixes_zan sont déjà calibrés pour 2011–2020 / ZAN.
        suffixes_ref = struct["suffixes_ref"]
        suffixes_zan = struct["suffixes_zan"]
        suffixes     = suffixes_ref + suffixes_zan

        col_pop1   = get_col(struct, "pop1",  "pop15")
        col_pop2   = get_col(struct, "pop2",  "pop21")
        col_men1   = get_col(struct, "men1",  "men15")
        col_men2   = get_col(struct, "men2",  "men21")
        col_emp1   = get_col(struct, "emp1",  "emp15")
        col_emp2   = get_col(struct, "emp2",  "emp21")
        col_surf   = get_col(struct, "surfcom", "surfcom2024")
        col_artcom = get_col(struct, "artcom",  "artcom0924")
        duree_zan       = struct.get("duree_zan", 4)
        annees_restantes = struct.get("annees_restantes", 7)

    def get(col):
        return ligne[col] if col in ligne.index else None

    # ── Données socio-démographiques ─────────────────────────────
    my_pop1 = get(col_pop1)
    my_pop2 = get(col_pop2)
    my_men1 = get(col_men1)
    my_men2 = get(col_men2)
    my_emp1 = get(col_emp1)
    my_emp2 = get(col_emp2)

    # ── Initialisation des catégories ────────────────────────────
    # On dimensionne les dicts en fonction du nombre de flux retenus
    nb_flux = len(suffixes)
    cats = {
        'act': {i: 0 for i in range(1, nb_flux + 3)},
        'hab': {i: 0 for i in range(1, nb_flux + 3)},
        'mix': {i: 0 for i in range(1, nb_flux + 3)},
        'inc': {i: 0 for i in range(1, nb_flux + 3)},
        'rou': {i: 0 for i in range(1, nb_flux + 3)},
        'fer': {i: 0 for i in range(1, nb_flux + 3)},
    }

    # ── Remplissage dynamique ────────────────────────────────────
    # Index 3 = premier flux de référence (art11…12), 4 = deuxième, etc.
    for idx, (a, b) in enumerate(suffixes, start=3):
        for suffix, target in cats.items():
            key = f'art{a}{suffix}{b}'
            target[idx] = get(key) or 0

    # ── Calcul des totaux ────────────────────────────────────────
    totaux = {}
    for suffix, d in cats.items():
        tot, tot_ref, tot_1319, tot_zan = compute_totals(d, suffixes_ref, suffixes_zan)
        totaux[suffix] = {
            "total": tot, "ref": tot_ref,
            "zan": tot_zan, "tot_1319": tot_1319
        }

    # ── Totaux globaux (en m²) ───────────────────────────────────
    cons_tot  = sum(v["total"] for v in totaux.values())
    cons_ref  = sum(v["ref"]   for v in totaux.values())
    cons_zan  = sum(v["zan"]   for v in totaux.values())

    # Noms de colonnes rétrocompatibles avec app.py existant
    return {
        # Socio (clés génériques + clés legacy)
        "pop13": my_pop1, "pop19": my_pop2,   # legacy
        "pop1":  my_pop1, "pop2":  my_pop2,   # générique
        "men13": my_men1, "men19": my_men2,
        "men1":  my_men1, "men2":  my_men2,
        "emp13": my_emp1, "emp19": my_emp2,
        "emp1":  my_emp1, "emp2":  my_emp2,

        # Catégories (dict {index: m²})
        "activity":    cats["act"],
        "habitat":     cats["hab"],
        "mixte":       cats["mix"],
        "inconnu":     cats["inc"],
        "route":       cats["rou"],
        "ferroviaire": cats["fer"],

        # Totaux en m² bruts
        "cons_tot":     cons_tot,
        "cons_tot2020": cons_ref,   # legacy (= période de référence)
        "cons_tot2130": cons_zan,   # legacy (= période ZAN)
        "cons_ref":     cons_ref,   # générique
        "cons_zan":     cons_zan,   # générique

        # Totaux en ha
        "cons_tot_ha":     m2_to_ha(cons_tot),
        "cons_tot2020_ha": m2_to_ha(cons_ref),  # legacy
        "cons_tot2130_ha": m2_to_ha(cons_zan),  # legacy
        "cons_ref_ha":     m2_to_ha(cons_ref),  # générique
        "cons_zan_ha":     m2_to_ha(cons_zan),  # générique

        # % artificialisation totale
        "pcent_art_com": get(col_artcom),

        # Paramètres de structure (utiles pour les modules de ratios / graphes)
        "suffixes_ref":      suffixes_ref,
        "suffixes_zan":      suffixes_zan,
        "duree_zan":         duree_zan,
        "annees_restantes":  annees_restantes,
    }
