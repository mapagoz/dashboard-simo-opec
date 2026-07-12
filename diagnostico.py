import json
import requests
import truststore
truststore.inject_into_ssl()

BASE_URL = "https://simo.cnsc.gov.co/empleos/ofertaPublica/"
PARAMS = {
    "search_palabraClave": "estadist",
    "tipoProceso": "CONCURSO_ABIERTO",
    "search_convocatoria": "1694220842",
    "search_entidad": "127576965",
    "search_departamento": "6",
    "search_municipio": "144",
    "search_nivel": "3",
    "search_limiteInferior": "4500001",
    "search_limiteSuperior": "5500000",
    "page": 0,
    "size": 5,
}
HEADERS = {
    "User-Agent": "portafolio-analisis-opec/1.0",
    "Accept": "application/json",
    "Referer": "https://simo.cnsc.gov.co/",
    "X-Requested-With": "XMLHttpRequest",
}

data = requests.get(BASE_URL, params=PARAMS, headers=HEADERS, timeout=30).json()
print("Cantidad de elementos:", len(data))

conv = data[0]["empleo"].get("convocatoria")
print("\n--- Objeto 'convocatoria' completo ---")
print(json.dumps(conv, indent=2, ensure_ascii=False))