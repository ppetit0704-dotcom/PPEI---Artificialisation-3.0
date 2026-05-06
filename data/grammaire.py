GRAMMAIRE = {
    # Identifiants
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

    # Flux CEREMA (catégories)
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
