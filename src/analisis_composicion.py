"""Compara el tiempo de recocido por composición y secuencia de la carga."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from src.analisis_cs import (
    ANCHO, COLUMNAS_NECESARIAS, ESPESOR, FAMILIA, GEO, ID, PESO, POS, SAT, TEMP, Y,
    _normalizar_id, leer_base,
)

FECHA = "RH- Fecha Produccion"
HORNO = "RH- Horno"
MATERIAL = "Material"
SOLO_CS = "Solo CS"
MIXTA = "Mixta CS–MS"


def _composicion(secuencia):
    familias = set(secuencia)
    if familias == {"CS"}:
        return SOLO_CS
    if familias == {"CS", "MS"}:
        return MIXTA
    if {"CS", "MS"} < familias:
        return "CS–MS–otros"
    return "Otras combinaciones"


def reconstruir_original(original):
    """Usa una fila por posición y una observación por carga."""
    columnas = [*COLUMNAS_NECESARIAS, MATERIAL, FECHA, HORNO]
    faltantes = set(columnas) - set(original.columns)
    if faltantes:
        raise ValueError(f"Faltan columnas en base original: {sorted(faltantes)}")
    datos = original[columnas].copy()
    datos[ID] = _normalizar_id(datos[ID])
    datos[MATERIAL] = _normalizar_id(datos[MATERIAL])
    datos[FAMILIA] = datos[FAMILIA].astype("string").str.strip().str.upper().replace("", pd.NA)
    datos[HORNO] = _normalizar_id(datos[HORNO])
    datos[FECHA] = pd.to_datetime(datos[FECHA], errors="coerce").dt.to_period("M").astype("string")
    for columna in [POS, Y, PESO, TEMP, SAT, ANCHO, ESPESOR]:
        datos[columna] = pd.to_numeric(datos[columna], errors="coerce")
    faltan_claves = datos[[ID, POS, MATERIAL, FAMILIA]].isna().any(axis=1)
    posiciones_invalidas = (datos[POS] < 1) | (datos[POS] % 1 != 0)
    if (faltan_claves | posiciones_invalidas).any():
        raise ValueError(f"{int((faltan_claves | posiciones_invalidas).sum())} filas sin identificación, familia o posición válida.")

    por_posicion = datos.groupby([ID, POS], sort=True)
    columnas_posicion = [MATERIAL, FAMILIA, ANCHO, ESPESOR]
    conflictos_posicion = (por_posicion[columnas_posicion].nunique() > 1).any(axis=1)
    if conflictos_posicion.any():
        raise ValueError(f"{int(conflictos_posicion.sum())} posiciones con material, familia o geometría en conflicto.")
    columnas_carga = [Y, PESO, TEMP, SAT, FECHA, HORNO]
    por_carga = datos.groupby(ID, sort=True)
    conflictos_carga = (por_carga[columnas_carga].nunique() > 1).any(axis=1)
    if conflictos_carga.any():
        raise ValueError(f"{int(conflictos_carga.sum())} cargas con datos de ciclo, peso, mes u horno en conflicto.")

    # first toma el primer valor disponible de cada variable tras verificar consistencia.
    bobinas = por_posicion[columnas_posicion].first().reset_index()
    posiciones_carga = bobinas.groupby(ID, sort=True)
    cargas = por_carga[columnas_carga].first().rename(columns={
        Y: "tiempo_real_min", PESO: "peso_carga_kg", TEMP: "temp_sat_f",
        SAT: "tiempo_sat_min", FECHA: "mes", HORNO: "horno",
    }).join(posiciones_carga.agg(
        n_rollos=(POS, "size"), espesor_medio_mm=(ESPESOR, "mean"),
        ancho_medio_mm=(ANCHO, "mean"),
    ))
    secuencias = posiciones_carga[FAMILIA].agg(tuple)
    cargas["composicion"] = secuencias.map(_composicion)
    cargas["secuencia"] = secuencias.str.join("–")
    auditoria = {
        "filas_original": len(datos),
        "bobinas": len(bobinas),
        "cargas": len(cargas),
        "filas_repetidas_misma_carga_posicion": len(datos) - len(bobinas),
        "cargas_con_repeticiones": int(datos.loc[datos.duplicated([ID, POS]), ID].nunique()),
        "cargas_con_posiciones_no_consecutivas_desde_1": int(
            posiciones_carga[POS].agg(lambda p: p.tolist() != list(range(1, len(p) + 1))).sum()
        ),
        "cargas_con_temperatura_saturacion_cero": int(cargas["temp_sat_f"].eq(0).sum()),
        "cargas_con_tiempo_saturacion_no_positivo": int(cargas["tiempo_sat_min"].le(0).sum()),
    }
    return cargas, auditoria


def ajustar_regresiones(cargas):
    """Compara cargas CS–MS con cargas solo CS mediante OLS e intervalos HC3."""
    muestra = cargas.loc[cargas["composicion"].isin([SOLO_CS, MIXTA])].copy()
    muestra = muestra.loc[muestra["tiempo_real_min"].gt(0)]
    muestra["mixta_cs_ms"] = muestra["composicion"].eq(MIXTA).astype(int)
    ajustes = [
        ("A1", []),
        ("A3", [*GEO, "C(mes)"]),
        ("S1", [*GEO, "C(mes)", "C(horno)"]),
    ]
    coeficientes, metricas = [], []
    for nombre, predictores in ajustes:
        columnas = [x[2:-1] if x.startswith("C(") else x for x in predictores]
        datos = muestra.dropna(subset=columnas).copy()
        if datos["mixta_cs_ms"].nunique() != 2:
            raise ValueError(f"{nombre} requiere cargas válidas de ambos grupos.")
        # Las categorías se pasan como object para admitir los distintos backends de pandas.
        for categoria in [col for col in columnas if col in ("mes", "horno")]:
            datos[categoria] = datos[categoria].astype(object)
        formula = "tiempo_real_min ~ " + " + ".join(["mixta_cs_ms", *predictores])
        modelo = smf.ols(formula, data=datos, missing="raise").fit(cov_type="HC3", use_t=False)
        tabla = modelo.conf_int()
        for variable, valor in modelo.params.items():
            coeficientes.append({
                "modelo": nombre, "variable": variable, "coeficiente_min": valor,
                "ic95_inferior_min": tabla.loc[variable, 0], "ic95_superior_min": tabla.loc[variable, 1],
                "p": modelo.pvalues[variable], "n": int(modelo.nobs),
            })
        metricas.append({
            "modelo": nombre, "n": int(modelo.nobs), "R2_muestra": modelo.rsquared,
            "MAE_muestra_min": float(np.abs(modelo.resid).mean()),
        })
    return pd.DataFrame(coeficientes), pd.DataFrame(metricas)


def ejecutar(original, salida="results/composicion"):
    cargas, auditoria = reconstruir_original(leer_base(original))
    muestras = cargas.loc[cargas["tiempo_real_min"].gt(0)]
    auditoria["cargas_sin_tiempo_real_positivo"] = len(cargas) - len(muestras)
    por_composicion = muestras.groupby("composicion")["tiempo_real_min"].agg(
        n_cargas="size", media_min="mean", mediana_min="median", desv_est_min="std",
    )
    por_secuencia = muestras.loc[muestras["composicion"].eq(MIXTA)].groupby(
        "secuencia"
    )["tiempo_real_min"].agg(n_cargas="size", media_min="mean", mediana_min="median")
    por_secuencia = por_secuencia.sort_values("n_cargas", ascending=False, kind="stable")
    coeficientes, metricas = ajustar_regresiones(cargas)
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    por_composicion.to_csv(salida / "resumen_composicion.csv", encoding="utf-8-sig")
    por_secuencia.to_csv(salida / "resumen_secuencias_mixtas.csv", encoding="utf-8-sig")
    coeficientes.to_csv(salida / "coeficientes_regresiones.csv", index=False)
    metricas.to_csv(salida / "metricas_regresiones.csv", index=False)
    (salida / "auditoria.json").write_text(json.dumps(auditoria, indent=2), encoding="utf-8")
    print(por_composicion.round(2).to_string())
    print(coeficientes.loc[coeficientes["variable"].eq("mixta_cs_ms")].round(4).to_string(index=False))
    print(f"Resultados locales en {salida.resolve()}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", required=True, help="Excel original con todas las familias")
    parser.add_argument("--salida", default="results/composicion")
    args = parser.parse_args()
    ejecutar(args.original, args.salida)


if __name__ == "__main__":
    main()
