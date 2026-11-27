"""Etapa 1 del reto Ternium: depuración CS, correlaciones, PCA y regresión.

Uso:
 python -m src.analisis_cs --dep "data/raw/Recocido -Tec-dep(1).xlsx" \
     --original "data/raw/Recocido -Tec.xlsx" --salida results/etapa1

Los archivos industriales y resultados por carga se guardan LOCALMENTE: no subir al repositorio.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_validate, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ID = "RH- Carga"
POS = "RH- Posicion"
FAMILIA = "RH-Familia acero"
Y = "RH-Tiempo Neto carga"  # Tiempo REAL de la carga, en minutos
PESO = "RH- Peso Carga"     # Peso de carga registrado por planta, no suma de filas
TEMP = "RH- Temperatura Saturacion"  # °F en archivo fuente
SAT = "RH- Tiempo Saturacion"        # min en archivo fuente
ANCHO = "RH- Ancho"                 # mm
ESPESOR = "RH- Espesor"             # mm
GEO = ["peso_carga_kg", "n_rollos", "espesor_medio_mm", "ancho_medio_mm"]
PROCESO = GEO + ["temp_sat_f", "tiempo_sat_min"]
COLUMNAS_NECESARIAS = [ID, POS, FAMILIA, Y, PESO, TEMP, SAT, ANCHO, ESPESOR]


def leer_base(ruta):
    """El libro tiene unidades en fila 1 y encabezados en fila 2."""
    ruta = Path(ruta)
    if ruta.suffix.lower() == ".csv":
        df = pd.read_csv(ruta, encoding="utf-8-sig")
    else:
        df = pd.read_excel(ruta, sheet_name="Hoja2", header=1)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _normalizar_id(col):
    def convertir(x):
        if pd.isna(x):
            return None
        if isinstance(x, (int, float, np.integer, np.floating)):
            return str(int(x)) if float(x).is_integer() else str(x)
        s = str(x).strip()
        if s.endswith(".0") and s[:-2].isdigit():
            s = s[:-2]
        return s or None
    return col.map(convertir)


def reconstruir_cargas(dep, original=None):
    """Una observación = una carga. Repeticiones por carga/posición no son bobinas nuevas.

    Si se proporciona original, excluye cargas mixtas: tener solo filas CS
    en la base depurada NO prueba que toda la carga sea CS.
    """
    faltantes = set(COLUMNAS_NECESARIAS) - set(dep.columns)
    if faltantes:
        raise ValueError(f"Faltan columnas en base depurada: {sorted(faltantes)}")
    d = dep[COLUMNAS_NECESARIAS].copy()
    d[ID] = _normalizar_id(d[ID])
    d[FAMILIA] = d[FAMILIA].astype("string").str.strip().str.upper()
    d = d.loc[(d[FAMILIA] == "CS") & d[ID].notna()].copy()
    for c in [POS, Y, PESO, TEMP, SAT, ANCHO, ESPESOR]:
        d[c] = pd.to_numeric(d[c], errors="coerce")

    auditoria = {
        "filas_depuradas_CS": int(len(d)),
        "cargas_con_al_menos_una_fila_CS": int(d[ID].nunique()),
        "filas_repetidas_misma_carga_posicion": int(d.duplicated([ID, POS]).sum()),
    }
    # Detecta discrepancias antes de elegir "first"; no promedia mediciones conflictivas.
    for c in [Y, PESO, TEMP, SAT]:
        n_conf = int((d.groupby(ID)[c].nunique(dropna=True) > 1).sum())
        if n_conf:
            raise ValueError(f"{n_conf} cargas tienen valores contradictorios en {c}.")
    for c in [ANCHO, ESPESOR]:
        n_conf = int((d.groupby([ID, POS], dropna=False)[c].nunique(dropna=True) > 1).sum())
        if n_conf:
            raise ValueError(f"{n_conf} posiciones tienen valores contradictorios en {c}.")
    d = d.drop_duplicates([ID, POS]).copy()

    por_rollo = d.groupby(ID, dropna=False).agg(
        n_rollos=(POS, "count"),
        espesor_medio_mm=(ESPESOR, "mean"),
        ancho_medio_mm=(ANCHO, "mean"),
    )
    por_carga = d.groupby(ID, dropna=False).agg(
        tiempo_real_min=(Y, "first"),
        peso_carga_kg=(PESO, "first"),
        temp_sat_f=(TEMP, "first"),
        tiempo_sat_min=(SAT, "first"),
    )
    cargas = por_carga.join(por_rollo).reset_index()
    auditoria["cargas_con_datos_CS_antes_contraste"] = int(len(cargas))
    auditoria["cargas_con_posiciones_no_validas"] = int(
        d.groupby(ID)[POS].apply(lambda x: x.isna().any() or (x < 1).any() or
                                  (x != np.floor(x)).any()).sum()
    )
    if original is not None:
        if ID not in original or FAMILIA not in original:
            raise ValueError("La base original necesita carga y familia de acero.")
        o = original[[ID, FAMILIA]].copy()
        o[ID] = _normalizar_id(o[ID])
        o[FAMILIA] = o[FAMILIA].astype("string").str.strip().str.upper()
        fam = o.dropna(subset=[ID]).groupby(ID)[FAMILIA].agg(
            lambda x: set(x.dropna().tolist())
        )
        homog = set(fam[fam.map(lambda s: s == {"CS"})].index)
        cargas = cargas.loc[cargas[ID].isin(homog)].copy()
        auditoria["homogeneidad_verificada_con_original"] = True
        auditoria["cargas_solo_CS_confirmadas"] = int(len(cargas))
        auditoria["cargas_excluidas_por_no_ser_solo_CS_o_sin_identificador_en_original"] = (
            auditoria["cargas_con_datos_CS_antes_contraste"] - len(cargas)
        )
    else:
        auditoria["homogeneidad_verificada_con_original"] = False
        auditoria["advertencia"] = (
            "Solo se conocen las filas CS: algunas cargas podrían contener MS u otros. "
            "NO interpretar estas cargas como cargas homogeneas CS."
        )
    return cargas, auditoria


def preparar_muestra(cargas, auditoria):
    """Conservar atípicos plausibles; excluir únicamente valores faltantes/imposibles."""
    c = cargas.copy()
    auditoria["cargas_antes_filtro_modelo"] = len(c)
    auditoria["temperatura_saturacion_no_positiva_o_faltante"] = int(
        (c["temp_sat_f"].isna() | (c["temp_sat_f"] <= 0)).sum()
    )
    auditoria["tiempo_saturacion_negativo_o_faltante"] = int(
        (c["tiempo_sat_min"].isna() | (c["tiempo_sat_min"] < 0)).sum()
    )
    valid = (
        c[["tiempo_real_min", *PROCESO]].notna().all(axis=1)
        & (c["tiempo_real_min"] > 0)
        & (c["peso_carga_kg"] > 0)
        & (c["n_rollos"] > 0)
        & (c["espesor_medio_mm"] > 0)
        & (c["ancho_medio_mm"] > 0)
        & (c["temp_sat_f"] > 0)
        & (c["tiempo_sat_min"] >= 0)
    )
    muestra = c.loc[valid].copy()
    auditoria["cargas_modeladas"] = int(len(muestra))
    auditoria["cargas_excluidas_por_faltantes_o_valores_invalidos"] = int((~valid).sum())
    auditoria["atipicos_tiempo_superior_4000_min_retenidos"] = int(
        (muestra["tiempo_real_min"] > 4000).sum()
    )
    if len(muestra) < 30:
        raise ValueError("Muy pocas cargas válidas para modelar (<30).")
    return muestra


def _guardar_figuras(muestra, train, test, modelos, predicciones, salida):
    # Correlaciones con objetivo, pero el objetivo se excluye de PCA y predictores.
    cols = PROCESO + ["tiempo_real_min"]
    corr = muestra[cols].corr(numeric_only=True)
    corr.to_csv(salida / "correlaciones.csv", encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=(9, 7))
    im = ax.imshow(corr, cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_xticks(range(len(cols)), cols, rotation=45, ha="right")
    ax.set_yticks(range(len(cols)), cols)
    for i in range(len(cols)):
        for j in range(len(cols)):
            ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax, label="r de Pearson")
    fig.tight_layout()
    fig.savefig(salida / "01_correlaciones.png", dpi=150)
    plt.close(fig)

    # PCA descriptivo: se ajusta solo con entrenamiento y sin tiempo objetivo.
    estandar = StandardScaler().fit(train[PROCESO])
    xt = estandar.transform(train[PROCESO])
    pca = PCA().fit(xt)
    vari = pd.DataFrame({
        "componente": [f"PC{i+1}" for i in range(len(PROCESO))],
        "varianza_explicada": pca.explained_variance_ratio_,
        "varianza_acumulada": np.cumsum(pca.explained_variance_ratio_),
    })
    vari.to_csv(salida / "varianza_pca.csv", index=False)
    pd.DataFrame(pca.components_.T, index=PROCESO,
                 columns=vari["componente"]).to_csv(salida / "cargas_pca.csv")
    fig, axs = plt.subplots(1, 2, figsize=(11, 4))
    axs[0].bar(vari["componente"], vari["varianza_explicada"])
    axs[0].set(ylabel="Fracción de varianza", title="Varianza explicada")
    coords = pca.transform(xt)
    axs[1].scatter(coords[:, 0], coords[:, 1], s=13, alpha=.65)
    axs[1].set(xlabel="PC1", ylabel="PC2", title="Cargas de entrenamiento")
    fig.tight_layout()
    fig.savefig(salida / "02_pca.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 5))
    y = test["tiempo_real_min"]
    for nombre, pred in predicciones.items():
        if nombre == "Mediana (referencia)":
            continue
        ax.scatter(y, pred, s=18, alpha=.7, label=nombre)
    lims = [min(y.min(), *(p.min() for p in predicciones.values())),
            max(y.max(), *(p.max() for p in predicciones.values()))]
    ax.plot(lims, lims, "k--", lw=1, label="Predicción perfecta")
    ax.set(xlabel="Tiempo real (min)", ylabel="Tiempo predicho (min)",
           title="Evaluación fuera de entrenamiento")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(salida / "03_real_vs_predicho.png", dpi=150)
    plt.close(fig)


def ejecutar(dep_path, original_path=None, salida="results/etapa1", semilla=42):
    """Ejecuta la etapa 1 y deja resultados LOCALES para auditar, no para publicar."""
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    dep = leer_base(dep_path)
    original = leer_base(original_path) if original_path else None
    cargas, auditoria = reconstruir_cargas(dep, original)
    muestra = preparar_muestra(cargas, auditoria)
    # NO se incluyen identificadores, tiempo estándar ni eficiencia entre predictores.
    train, test = train_test_split(muestra, test_size=.2, random_state=semilla)
    algoritmos = {
        "Mediana (referencia)": (DummyRegressor(strategy="median"), GEO),
        "Regresion multiple geometria": (make_pipeline(StandardScaler(), LinearRegression()), GEO),
        "Regresion multiple geometria+proceso": (
            make_pipeline(StandardScaler(), LinearRegression()), PROCESO
        ),
    }
    metricas, coeficientes, predicciones = [], [], {}
    for nombre, (modelo, columnas) in algoritmos.items():
        modelo.fit(train[columnas], train["tiempo_real_min"])
        pred = modelo.predict(test[columnas])
        predicciones[nombre] = pred
        fila = {
            "modelo": nombre,
            "n_entrenamiento": len(train),
            "n_prueba": len(test),
            "R2_entrenamiento": r2_score(train["tiempo_real_min"],
                                         modelo.predict(train[columnas])),
            "R2_prueba": r2_score(test["tiempo_real_min"], pred),
            "MAE_prueba_min": mean_absolute_error(test["tiempo_real_min"], pred),
            "RMSE_prueba_min": np.sqrt(mean_squared_error(test["tiempo_real_min"], pred)),
        }
        if nombre != "Mediana (referencia)":
            cv = cross_validate(
                make_pipeline(StandardScaler(), LinearRegression()),
                train[columnas], train["tiempo_real_min"],
                cv=KFold(n_splits=5, shuffle=True, random_state=semilla),
                scoring={"r2": "r2", "mae": "neg_mean_absolute_error"},
            )
            fila["R2_CV_media_entrenamiento"] = np.mean(cv["test_r2"])
            fila["R2_CV_desviacion"] = np.std(cv["test_r2"])
            fila["MAE_CV_media_min"] = -np.mean(cv["test_mae"])
            scaler, lr = modelo.steps[0][1], modelo.steps[1][1]
            beta = lr.coef_ / scaler.scale_   # Coeficientes en unidades originales
            b0 = lr.intercept_ - np.dot(beta, scaler.mean_)
            coeficientes.append({"modelo": nombre, "variable": "intercepto_min",
                                  "coeficiente": b0})
            coeficientes.extend(
                {"modelo": nombre, "variable": variable, "coeficiente": float(valor)}
                for variable, valor in zip(columnas, beta)
            )
        metricas.append(fila)

    resultados = pd.DataFrame(metricas)
    resultados.to_csv(salida / "metricas_regresion.csv", index=False)
    pd.DataFrame(coeficientes).to_csv(salida / "coeficientes.csv", index=False)
    comparacion = test[[ID, "tiempo_real_min"]].copy()
    for nombre, pred in predicciones.items():
        comparacion["pred_" + nombre] = pred
    comparacion.to_csv(salida / "predicciones_prueba_PRIVADAS.csv", index=False)
    muestra.to_csv(salida / "cargas_modelo_PRIVADAS.csv", index=False)
    _guardar_figuras(muestra, train, test, algoritmos, predicciones, salida)
    auditoria.update({
        "semilla": semilla, "fraccion_prueba": .2,
        "predictores_geometria": GEO, "predictores_geometria_proceso": PROCESO,
        "variable_objetivo": "RH-Tiempo Neto carga (min, tiempo real)",
        "nota_saturacion": (
            "Tiempo de saturacion real forma parte del ciclo: la regresion +proceso "
            "es explicativa/retrospectiva, no prediccion prospectiva validada."
        ),
        "nota_calidad": "La base depurada no incluye elongacion o resistencia: NO valida calidad.",
        "nota_R2": "R2 de prueba y CV son prioritarios; no optimizar hiperparametros sobre test.",
    })
    (salida / "auditoria.json").write_text(
        json.dumps(auditoria, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("AUDITORÍA:\n", json.dumps(auditoria, ensure_ascii=False, indent=2))
    print("\nMÉTRICAS:\n", resultados.to_string(index=False))
    print("\nResultados locales:", salida.resolve())
    return auditoria, resultados


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dep", required=True, help="Excel depurado con registros CS")
    p.add_argument("--original", help="Excel original para confirmar cargas SOLO CS")
    p.add_argument("--salida", default="results/etapa1")
    p.add_argument("--semilla", type=int, default=42)
    a = p.parse_args()
    ejecutar(a.dep, a.original, a.salida, a.semilla)


if __name__ == "__main__":
    main()
