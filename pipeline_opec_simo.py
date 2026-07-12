"""
Pipeline OPEC - SIMO (CNSC): extrae la Oferta Publica de Empleos de Carrera
y la sube a una Google Sheet. Genera una fila por vacante (municipio) y
etiqueta cada una con su PROCESO DE SELECCION padre.

Estrategia: recorre los procesos visibles (endpoint visiblesTipo) y consulta
el endpoint principal filtrando por cada proceso. Asi se obtiene el nombre del
proceso padre y, de paso, solo lo vigente/visible.

Datos publicos de convocatorias, sin informacion de participantes.

Requisitos:
    pip install requests pandas gspread gspread-dataframe truststore
"""

import os
import json
import time

import requests
import pandas as pd
import gspread
from gspread_dataframe import set_with_dataframe

import truststore
truststore.inject_into_ssl()  # usa los certificados de Windows (resuelve el SSL de SIMO)

# ------------------- CONFIGURACION -------------------
BASE_URL = "https://simo.cnsc.gov.co/empleos/ofertaPublica/"
PROCESOS_URL = "https://simo.cnsc.gov.co/convocatorias/visiblesTipo/list/"

# Filtros base del endpoint principal. Deja "" para no filtrar.
# El proceso (search_convocatoria) se asigna automaticamente en el recorrido.
PARAMS_BASE = {
    "search_palabraClave": "",   # <-- para probar rapido pon aqui "estad"
    "tipoProceso": "",
    "search_convocatoria": "",
    "search_entidad": "",
    "search_departamento": "",
    "search_municipio": "",
    "search_nivel": "",
    "search_salario": "",
    "search_limiteInferior": "",
    "search_limiteSuperior": "",
    "search_discapacidad": "",
    "search_numeroOPEC": "",
    "size": 100,
}

HEADERS = {
    "User-Agent": "portafolio-analisis-opec/1.0 (proyecto personal de datos publicos)",
    "Accept": "application/json",
    "Referer": "https://simo.cnsc.gov.co/",
    "X-Requested-With": "XMLHttpRequest",
}

PAUSA_SEGUNDOS = 1.0

# Google Sheets
SHEET_ID = "1JpCSBemtrHtpkLoENOsEHJ8wtscOIKbAeZSREqrkXcc"
WORKSHEET = "vacantes"
# -----------------------------------------------------


def traer_procesos() -> list:
    """Lista de procesos de seleccion visibles: [{'id':..., 'nombre':...}, ...]."""
    resp = requests.get(PROCESOS_URL, params={"nombre": "*"}, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    unicos = {}  # dedupe por id
    for item in data:
        unicos[item["id"]] = item.get("nombre")
    procesos = [{"id": pid, "nombre": nombre} for pid, nombre in unicos.items()]
    print(f"Procesos visibles encontrados: {len(procesos)}")
    return procesos


def traer_pagina(page: int, search_convocatoria) -> list:
    """La API devuelve directamente una LISTA de registros."""
    params = dict(PARAMS_BASE, page=page, search_convocatoria=search_convocatoria)
    resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def traer_todo() -> list:
    """Recorre cada proceso y pagina sus empleos, etiquetandolos con el proceso."""
    registros = []
    for proc in traer_procesos():
        pid, pnombre = proc["id"], proc["nombre"]
        page = 0
        subtotal = 0
        while True:
            lote = traer_pagina(page, pid)
            if not lote:
                break
            for reg in lote:  # etiqueta con el proceso padre
                reg["_proceso_id"] = pid
                reg["_proceso_nombre"] = pnombre
            registros.extend(lote)
            subtotal += len(lote)
            if len(lote) < PARAMS_BASE["size"]:
                break
            page += 1
            time.sleep(PAUSA_SEGUNDOS)
        print(f"  {pnombre}: {subtotal} empleos")
    print(f"Total registros (empleos): {len(registros)}")
    return registros


def _limpiar(valor):
    return valor.strip() if isinstance(valor, str) else valor


def construir_dataframe(registros: list) -> pd.DataFrame:
    """Aplana el JSON anidado a una fila por vacante (municipio)."""
    filas = []
    for reg in registros:
        empleo = reg.get("empleo") or {}
        conv = empleo.get("convocatoria") or {}
        entidad = conv.get("entidad") or {}
        grado_nivel = empleo.get("gradoNivel") or {}
        requisitos = empleo.get("requisitosMinimos") or []
        req0 = requisitos[0] if requisitos else {}

        base = {
            "proceso_seleccion": reg.get("_proceso_nombre"),
            "proceso_seleccion_id": reg.get("_proceso_id"),
            "opec_empleo_id": empleo.get("id"),
            "codigo_empleo": _limpiar(empleo.get("codigoEmpleo")),
            "denominacion": (empleo.get("denominacion") or {}).get("nombre"),
            "nivel": reg.get("nivelNombre") or grado_nivel.get("nivelNombre"),
            "grado": grado_nivel.get("grado"),
            "salario": empleo.get("asignacionSalarial"),
            "vigencia_salarial": empleo.get("vigenciaSalarial"),
            "modalidad": "Ascenso" if empleo.get("concursoAscenso") else "Ingreso",
            "reserva_discapacidad": empleo.get("condicionDiscapacidad"),
            "convocatoria": conv.get("nombre"),
            "convocatoria_id": conv.get("id"),
            "convocatoria_codigo": conv.get("codigo"),
            "convocatoria_agno": conv.get("agno"),
            "tipo_proceso": conv.get("tipoProceso"),
            "entidad": entidad.get("nombre"),
            "tipo_entidad": (entidad.get("tipoEntidad") or {}).get("nombre"),
            "nit_entidad": entidad.get("nit"),
            "requisito_estudio": _limpiar(req0.get("estudio")),
            "requisito_experiencia": _limpiar(req0.get("experiencia")),
            "proposito": _limpiar(empleo.get("descripcion")),
        }

        vacantes = empleo.get("vacantes") or []
        if not vacantes:
            filas.append({**base, "municipio": None, "departamento": None,
                          "dependencia": None, "cantidad_vacantes": None,
                          "disponibles": None})
            continue

        for vac in vacantes:
            municipio = vac.get("municipio") or {}
            filas.append({
                **base,
                "municipio": municipio.get("nombre"),
                "departamento": (municipio.get("departamento") or {}).get("nombre"),
                "dependencia": (vac.get("dependencia") or {}).get("nombre"),
                "cantidad_vacantes": vac.get("cantidad"),
                "disponibles": vac.get("disponible"),
            })

    return pd.DataFrame(filas)


def cliente_gspread() -> gspread.Client:
    cred_env = os.environ.get("GOOGLE_CREDENTIALS")
    if cred_env:  # automatizado (GitHub Actions): JSON en variable de entorno
        return gspread.service_account_from_dict(json.loads(cred_env))
    return gspread.service_account(filename="credentials.json")  # local


def subir_a_sheets(df: pd.DataFrame) -> None:
    gc = cliente_gspread()
    sh = gc.open_by_key(SHEET_ID)
    try:
        ws = sh.worksheet(WORKSHEET)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=WORKSHEET, rows=100, cols=30)
    ws.clear()
    set_with_dataframe(ws, df)
    print(f"Subidas {len(df)} filas y {len(df.columns)} columnas a la hoja '{WORKSHEET}'.")


def main() -> None:
    registros = traer_todo()
    if not registros:
        print("No se recibieron registros. Revisa filtros o encabezados.")
        return
    df = construir_dataframe(registros)
    print(f"Filas finales (una por vacante): {len(df)}")
    print("Columnas:", list(df.columns))
    subir_a_sheets(df)
    print("Listo.")


if __name__ == "__main__":
    main()