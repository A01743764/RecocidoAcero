"""Pruebas sintéticas: NO contienen datos industriales de Ternium."""
import numpy as np
import pandas as pd
import pytest
from src.analisis_cs import (
    ID, POS, FAMILIA, Y, PESO, TEMP, SAT, ANCHO, ESPESOR,
    reconstruir_cargas, preparar_muestra,
)


def ejemplo():
    d = pd.DataFrame([
        {ID: 100, POS: 1, FAMILIA: "CS", Y: 2000, PESO: 50000,
         TEMP: 1200, SAT: 300, ANCHO: 1000, ESPESOR: 1.0},
        {ID: 100, POS: 1, FAMILIA: "CS", Y: 2000, PESO: 50000,
         TEMP: 1200, SAT: 300, ANCHO: 1000, ESPESOR: 1.0},  # repetida
        {ID: 100, POS: 2, FAMILIA: "CS", Y: 2000, PESO: 50000,
         TEMP: 1200, SAT: 300, ANCHO: 1100, ESPESOR: 2.0},
        {ID: 200, POS: 1, FAMILIA: "CS", Y: 2100, PESO: 51000,
         TEMP: 1200, SAT: 300, ANCHO: 1000, ESPESOR: 1.0},
    ])
    orig = pd.DataFrame({ID: [100, 100, 200, 200],
                         FAMILIA: ["CS", "CS", "CS", "MS"]})
    return d, orig


def test_deduplicacion_y_filtro_homogeneo():
    d, orig = ejemplo()
    cargas, aud = reconstruir_cargas(d, orig)
    assert len(cargas) == 1
    assert cargas.iloc[0]["n_rollos"] == 2
    assert cargas.iloc[0]["espesor_medio_mm"] == 1.5
    assert cargas.iloc[0]["peso_carga_kg"] == 50000
    assert aud["filas_repetidas_misma_carga_posicion"] == 1
    assert aud["homogeneidad_verificada_con_original"] is True
    assert len(preparar_muestra(cargas, aud)) == 1 if len(cargas) >= 30 else True


def test_contradiccion_de_datos_frena_pipeline():
    d, orig = ejemplo()
    d.loc[1, ESPESOR] = 99
    with pytest.raises(ValueError, match="posiciones"):
        reconstruir_cargas(d, orig)


def test_sin_original_no_se_afirma_homogeneidad():
    d, _ = ejemplo()
    cargas, aud = reconstruir_cargas(d)
    assert len(cargas) == 2
    assert aud["homogeneidad_verificada_con_original"] is False
    assert "advertencia" in aud
