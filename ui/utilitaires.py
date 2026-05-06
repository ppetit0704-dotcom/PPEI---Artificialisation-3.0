import requests

def get_coords_from_insee(code_insee : str):
    """
    Retourne (latitude, longitude) à partir d'un code INSEE.
    """
    print("*****************************", {code_insee} , "********************************")
    url = f"https://geo.api.gouv.fr/communes/{code_insee}?fields=centre&format=json&geometry=centre"
    print(url)
    response = requests.get(url)

    if response.status_code != 200:
        raise ValueError("Code INSEE introuvable ou erreur API")

    data = response.json()

    # L'API renvoie les coordonnées dans data["centre"]["coordinates"] sous forme [lon, lat]
    lon, lat = data["centre"]["coordinates"]
    return lat, lon


