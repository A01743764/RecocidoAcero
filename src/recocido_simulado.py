"""Recocido simulado sobre configuraciones históricas de cargas solo CS."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.analisis_cs import GEO, ID

REAL = "tiempo_real_min"
PRED = "tiempo_predicho_min"
TEMPERATURA_INICIAL = 30.0
TEMPERATURA_FINAL = 0.3


def cargar_candidatas(etapa1):
    cargas = pd.read_csv(etapa1 / "cargas_modelo_PRIVADAS.csv", dtype={ID: str})
    columna = "pred_Regresion multiple geometria"
    pred = pd.read_csv(etapa1 / "predicciones_prueba_PRIVADAS.csv", dtype={ID: str})
    datos = pred[[ID, REAL, columna]].merge(
        cargas[[ID, REAL, *GEO]], on=ID, how="left", suffixes=("", "_base"), validate="one_to_one"
    ).rename(columns={columna: PRED})
    if datos.empty or datos[ID].isna().any() or not np.isfinite(datos[[REAL, PRED, *GEO]]).all().all():
        raise ValueError("La salida de etapa 1 no contiene una muestra de prueba completa.")
    if not np.allclose(datos[REAL], datos[f"{REAL}_base"], rtol=0, atol=1e-8):
        raise ValueError("Las predicciones y las cargas deben provenir de la misma corrida.")
    return datos[[ID, *GEO, REAL, PRED]].sort_values(ID).reset_index(drop=True)


def buscar(costos, inicio, pasos, semilla):
    rng = np.random.default_rng(semilla)
    actual = mejor = inicio
    visitados = {inicio}
    temperaturas = np.geomspace(TEMPERATURA_INICIAL, TEMPERATURA_FINAL, pasos)
    traza = []
    for paso, temperatura in enumerate(temperaturas, start=1):
        propuesta = int(rng.integers(len(costos) - 1))
        propuesta += propuesta >= actual
        visitados.add(propuesta)
        delta = costos[propuesta] - costos[actual]
        acepta = delta <= 0 or rng.random() < np.exp(-delta / temperatura)
        if acepta:
            actual = propuesta
        if costos[actual] < costos[mejor]:
            mejor = actual
        traza.append({
            "paso": paso, "temperatura_algoritmo_min": temperatura, "propuesta": propuesta,
            "delta_min": delta, "aceptada": acepta, "actual": actual, "mejor": mejor,
            "objetivo_actual_min": costos[actual], "mejor_objetivo_min": costos[mejor],
        })
    return mejor, len(visitados), traza


def ejecutar(etapa1, salida, referencia, tolerancia, pasos, repeticiones, semilla):
    datos = cargar_candidatas(etapa1)
    if referencia is None:
        grupo = datos.loc[datos["n_rollos"].eq(datos["n_rollos"].mode().iloc[0])]
        distancia = (grupo["peso_carga_kg"] - grupo["peso_carga_kg"].median()).abs()
        referencia = grupo.loc[distancia.idxmin(), ID]
    coincidencias = datos.loc[datos[ID].eq(referencia)]
    if coincidencias.empty:
        raise ValueError("La carga de referencia debe pertenecer a la muestra de prueba de etapa 1.")
    base = coincidencias.iloc[0]
    peso = float(base["peso_carga_kg"])
    candidatas = datos.loc[
        datos["n_rollos"].eq(base["n_rollos"])
        & datos["peso_carga_kg"].between(peso * (1 - tolerancia), peso * (1 + tolerancia))
    ].reset_index(drop=True)
    if len(candidatas) < 2:
        raise ValueError("Se necesitan dos cargas candidatas. Revisa la referencia o la tolerancia de peso.")
    candidatas.index.name = "candidata"
    inicio = int(candidatas.index[candidatas[ID].eq(referencia)][0])
    costos = candidatas[PRED].to_numpy()
    optimo = int(costos.argmin())
    filas, trazas = [], []
    for repeticion in range(repeticiones):
        semilla_corrida = semilla + repeticion
        mejor, evaluadas, traza = buscar(costos, inicio, pasos, semilla_corrida)
        filas.append({
            "semilla": semilla_corrida, "mejor_candidata": mejor, "candidatas_evaluadas": evaluadas,
            "mejor_predicho_min": costos[mejor], "brecha_vs_exhaustiva_min": costos[mejor] - costos[optimo],
        })
        trazas.extend({"semilla": semilla_corrida, **paso} for paso in traza)
    corridas = pd.DataFrame(filas)
    elegida = int(corridas.loc[corridas["mejor_predicho_min"].idxmin(), "mejor_candidata"])
    resumen = {
        "cargas_prueba_etapa1": len(datos), "candidatas": len(candidatas),
        "tolerancia_peso_relativa": tolerancia, "pasos_por_corrida": pasos,
        "repeticiones": repeticiones, "primera_semilla": semilla,
        "temperatura_algoritmo_inicial_min": TEMPERATURA_INICIAL,
        "temperatura_algoritmo_final_min": TEMPERATURA_FINAL,
        "corridas_que_alcanzan_optimo": int(np.isclose(corridas["brecha_vs_exhaustiva_min"], 0).sum()),
        "mae_prueba_etapa1_min": float((datos[REAL] - datos[PRED]).abs().mean()),
        "reduccion_predicha_min": float(costos[inicio] - costos[elegida]),
        "referencia": candidatas.loc[inicio, [*GEO, PRED, REAL]].to_dict(),
        "mejor_recocido": candidatas.loc[elegida, [*GEO, PRED, REAL]].to_dict(),
        "mejor_exhaustiva": candidatas.loc[optimo, [*GEO, PRED, REAL]].to_dict(),
    }
    salida.mkdir(parents=True, exist_ok=True)
    candidatas.to_csv(salida / "candidatas_PRIVADAS.csv")
    corridas.to_csv(salida / "corridas.csv", index=False)
    pd.DataFrame(trazas).to_csv(salida / "trazas.csv", index=False)
    informe = json.dumps(resumen, indent=2, ensure_ascii=False)
    (salida / "resumen.json").write_text(informe + "\n", encoding="utf-8")
    print(informe)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--etapa1", type=Path, default=Path("results/etapa1"))
    parser.add_argument("--salida", type=Path, default=Path("results/recocido"))
    parser.add_argument("--referencia", help="Identificador de una carga del conjunto de prueba")
    parser.add_argument("--tolerancia-peso", type=float, default=0.05)
    parser.add_argument("--pasos", type=int, default=100)
    parser.add_argument("--repeticiones", type=int, default=20)
    parser.add_argument("--semilla", type=int, default=42)
    args = parser.parse_args()
    if not 0 <= args.tolerancia_peso < 1 or args.pasos < 2 or args.repeticiones < 1 or args.semilla < 0:
        parser.error("Usa 0 ≤ tolerancia < 1, al menos dos pasos, una repetición y una semilla no negativa.")
    ejecutar(args.etapa1, args.salida, args.referencia, args.tolerancia_peso,
             args.pasos, args.repeticiones, args.semilla)


if __name__ == "__main__":
    main()
