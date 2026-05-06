import re
import pandas as pd

# ---------------------------------------------------------
# 1. Grammaire officielle des colonnes CEREMA (future-proof)
# ---------------------------------------------------------
GRAMMAIRE = {
    "idcom": r"^idcom$",
    "idcomtxt": r"^idcomtxt$",
    "idreg": r"^idreg$",
    "idregtxt": r"^idregtxt$",
    "iddep": r"^iddep$",
    "iddeptxt": r"^iddeptxt$",
    "epci": r"^epci\d{2}$",
    "epcitxt": r"^epci\d{2}txt$",
    "scot": r"^scot$",

    # AAV
    "aav": r"^aav(\d{4})(txt|_typo)?$",

    # Flux CEREMA
    "flux": r"^art(\d{2})(act|hab|mix|rou|fer|inc)(\d{2})$",

    # Flux NAF → artificialisation
    "naf_flux": r"^naf(\d{2})art(\d{2})$",

    # Artcom
    "artcom": r"^artcom(\d{2})(\d{2})$",

    # Démographie / ménages / emploi
    "demographie": r"^(pop|men|emp|mepart|menhab|artpop)(\d{2})(\d{2})?$",

    # Stock de surface
    "stock": r"^surf([a-z]+)(\d{4})$",
}


# ---------------------------------------------------------
# 2. Fonction de parsing d'une colonne
# ---------------------------------------------------------
def parse_col(col):
    for type_col, regex in GRAMMAIRE.items():
        m = re.match(regex, col)
        if m:
            return type_col, m.groups()
    return None, None


# ---------------------------------------------------------
# 3. Test automatique de décodabilité
# ---------------------------------------------------------
def test_fichier_cerema(df: pd.DataFrame):
    resultat = {
        "colonnes_total": len(df.columns),
        "colonnes_reconnues": 0,
        "colonnes_non_reconnues": [],
        "details": {}
    }

    for col in df.columns:
        type_col, details = parse_col(col)
        if type_col is None:
            resultat["colonnes_non_reconnues"].append(col)
        else:
            resultat["colonnes_reconnues"] += 1
            resultat["details"].setdefault(type_col, []).append((col, details))

    resultat["est_valide"] = (len(resultat["colonnes_non_reconnues"]) == 0)
    return resultat


# ---------------------------------------------------------
# 4. Affichage lisible (console ou Streamlit)
# ---------------------------------------------------------
def afficher_rapport(resultat):
    print("\n=== TEST AUTOMATIQUE CEREMA ===")
    print(f"Colonnes totales : {resultat['colonnes_total']}")
    print(f"Colonnes reconnues : {resultat['colonnes_reconnues']}")
    print(f"Colonnes non reconnues : {len(resultat['colonnes_non_reconnues'])}")

    if resultat["est_valide"]:
        print("\n✔ Le fichier est 100 % décodable.")
    else:
        print("\n❌ Colonnes non reconnues :")
        for col in resultat["colonnes_non_reconnues"]:
            print(f"   - {col}")

    print("\n=== Détails par famille ===")
    for famille, cols in resultat["details"].items():
        print(f"\n[{famille}] ({len(cols)} colonnes)")
        for col, details in cols:
            print(f"  - {col}  →  {details}")

df = pd.read_csv("conso2009-2024-resultats-com.csv", sep=";")
resultat = test_fichier_cerema(df)
afficher_rapport(resultat)
