import re
import pandas as pd
import gspread

SHEET_ID = "1JpCSBemtrHtpkLoENOsEHJ8wtscOIKbAeZSREqrkXcc"   # el mismo de tu pipeline
WORKSHEET = "vacantes"

gc = gspread.service_account(filename="credentials.json")
ws = gc.open_by_key(SHEET_ID).worksheet(WORKSHEET)
df = pd.DataFrame(ws.get_all_records())

col = df["requisito_experiencia"].fillna("").astype(str)

# 1) Cuantas celdas traen MAS de un numero (principal + alternativa)
num_numeros = col.apply(lambda t: len(re.findall(r"\((\d+)\)", t)))
print("Celdas con 2+ numeros entre parentesis:", (num_numeros >= 2).sum())
print("Celdas con 1 numero:", (num_numeros == 1).sum())
print("Celdas con 0 numeros:", (num_numeros == 0).sum())

# 2) Todas las palabras clave de TIPO que aparecen tras "EXPERIENCIA"
tipos = col.str.upper().str.findall(r"EXPERIENCIA\s+([A-ZÁÉÍÓÚÑ\s]+?)(?:\.|,|<|\n|$)")
from collections import Counter
cont = Counter()
for lista in tipos:
    for t in lista:
        cont[t.strip()] += 1
print("\n--- Tipos de experiencia encontrados (y su frecuencia) ---")
for tipo, n in cont.most_common():
    print(f"  {n:>5}  {tipo}")

# 3) Muestra 15 celdas con 2+ numeros, para ver el patron real
print("\n--- Ejemplos con 2+ numeros ---")
for texto in col[num_numeros >= 2].head(15):
    print(" -", texto.replace("\n", " ")[:160])