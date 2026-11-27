import numpy as np
import pandas as pd
import pytest

from src.analisis_composicion import (
    ANCHO, ESPESOR, FAMILIA, FECHA, HORNO, ID, MATERIAL, MIXTA, PESO, POS, SAT,
    SOLO_CS, TEMP, Y, ajustar_regresiones, reconstruir_original,
)


def bobina(carga, posicion, familia):
    return {
        ID: carga, POS: posicion, FAMILIA: familia, MATERIAL: carga * 10 + posicion,
        Y: 2000, PESO: 50000, TEMP: 1200, SAT: 300, ANCHO: 1000, ESPESOR: 1.0,
        FECHA: pd.Timestamp("2026-01-05"), HORNO: 1,
    }


def test_reconstruccion_deduplica_y_respeta_el_orden_numerico():
    principal = bobina(1, 1, "MS")
    filas = [bobina(1, 10, "CS"), principal, principal.copy(), bobina(2, 1, "CS")]
    cargas, auditoria = reconstruir_original(pd.DataFrame(filas))
    assert cargas.loc["1", "secuencia"] == "MS–CS"
    assert cargas.loc["1", "composicion"] == MIXTA
    assert cargas.loc["2", "composicion"] == SOLO_CS
    assert auditoria["bobinas"] == 3
    assert auditoria["filas_repetidas_misma_carga_posicion"] == 1
    assert auditoria["cargas_con_posiciones_no_consecutivas_desde_1"] == 1


def test_reconstruccion_detecta_material_distinto_en_la_misma_posicion():
    original = bobina(1, 1, "CS")
    conflicto = {**original, MATERIAL: 99}
    with pytest.raises(ValueError, match="posiciones con material"):
        reconstruir_original(pd.DataFrame([original, conflicto]))


def test_regresiones_excluyen_otras_composiciones():
    rng = np.random.default_rng(42)
    filas = []
    for i in range(20):
        peso, n, espesor, ancho = rng.integers([40000, 2, 1, 800], [60000, 6, 5, 1200])
        for grupo, diferencia in [(SOLO_CS, 0), (MIXTA, 20), ("Otras combinaciones", 500)]:
            filas.append({
                "composicion": grupo, "tiempo_real_min": 2000 + i + diferencia,
                "peso_carga_kg": peso, "n_rollos": n,
                "espesor_medio_mm": espesor, "ancho_medio_mm": ancho,
                "mes": f"2026-0{1 + i % 2}", "horno": str(1 + i % 3),
            })
    coeficientes, metricas = ajustar_regresiones(pd.DataFrame(filas))
    efectos = coeficientes.loc[coeficientes["variable"].eq("mixta_cs_ms"), "coeficiente_min"]
    assert efectos.to_list() == pytest.approx([20, 20, 20])
    assert metricas["n"].to_list() == [40, 40, 40]
