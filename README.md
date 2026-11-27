# rECOCIDOaCERO — análisis y optimización de recocido

Proyecto académico de Ternium. El modelo térmico anterior `difusiondecalor_R1.py` se conserva **sin cambios**.

## Estado del proyecto
- **Etapa 1 (en revisión):** depuración conservadora de aceros CS, correlaciones, PCA y regresión múltiple.
- **Etapa 2 (pendiente):** auditoría independiente de resultados de regresión.
- **Etapa 3 (pendiente):** recocido simulado con función objetivo y restricciones justificadas.
- **Etapa 4 (pendiente):** auditoría del optimizador y comparación con referencia.
- **Etapa final:** integrar validación física y calidad; *no* seleccionar modelos usando el conjunto de prueba.

## Ejecutar etapa 1 (en tu computadora o Colab)
```bash
pip install -r requirements.txt
python -m src.analisis_cs --dep "data/raw/Recocido -Tec-dep(1).xlsx" --original "data/raw/Recocido -Tec.xlsx" --salida "results/etapa1"
pytest -q
```

O abre `notebooks/01_PCA_correlaciones_regresion_CS.ipynb` y coloca los dos Excel **localmente** en `data/raw/`. La base original es opcional para ejecutar, **pero obligatoria para afirmar que las cargas son exclusivamente CS**. Sin ella el subconjunto contiene *filas CS*, no necesariamente *cargas solo CS*.

## Comparar cargas solo CS y mixtas CS–MS

```bash
python -m src.analisis_composicion --original "data/raw/Recocido -Tec.xlsx" --salida "results/composicion"
```

El Excel original aporta la familia de cada posición. El módulo resume el tiempo neto por composición y por secuencia de abajo hacia arriba. Compara cargas solo CS con mixtas CS–MS mediante regresiones OLS con intervalos de confianza HC3. A1 estima la diferencia de medias. A3 ajusta por geometría y mes. S1 agrega el horno. Los R² y MAE de este análisis describen el ajuste sobre la muestra. Los intervalos cuantifican incertidumbre de asociaciones observacionales y las secuencias con pocas cargas se mantienen como resultados descriptivos.

Los archivos Excel contienen información de planta: **no subir datos industriales, CSV individuales, archivos con identificadores de carga, ni resultados derivados sin autorización de Ternium**. El repositorio es público. `results/` y `data/` están ignorados por Git; las gráficas pueden exportarse para entrega controlada previa revisión.

## Qué representa una observación
Cada fila del Excel depurado es un registro de bobina y puede repetirse por mediciones de laboratorio. Se deduplica por `RH- Carga` + `RH- Posicion`, verificando que los atributos repetidos no discrepen. Una fila en la tabla modelada representa **una carga**. La variable objetivo es `RH-Tiempo Neto carga`, en minutos (no `RH-Tiempo STD Carga` ni eficiencia).

Se conserva el peso de carga registrado por planta, sin recomponerlo como suma de filas CS. Se usan promedios geométricos de las posiciones distintas. Las temperaturas se mantienen en °F; los tiempos en minutos. La regla simple de inclusión para el modelo es: valores disponibles y físicamente positivos, con tiempo de saturación no negativo. Los tiempos largos plausibles **no se eliminan automáticamente**.

## Advertencias científicas
- **PCA y correlación no son optimización** ni demuestran causalidad.
- El tiempo de saturación es parte del ciclo: el modelo que lo incluye es **retrospectivo/explicativo**, no una política prospectiva validada.
- El modelo de solo geometría permite comparar sin condiciones de operación pos-tratamiento.
- Los resultados son asociaciones observacionales. Sin propiedades mecánicas y restricciones físicas no se garantiza calidad.
- Reportar `R²`, MAE, RMSE **en prueba** y validación cruzada solo sobre entrenamiento; comparar contra referencia mediana. No optimizar para subir `R²` de prueba.
- Referirse a `docs/auditoria_etapa1.md` para revisión independiente y criterios de aceptación.

## Organización
- `difusiondecalor_R1.py`: simulación térmica ya existente, intacta.
- `src/analisis_cs.py`: flujo reproducible y control de calidad.
- `src/analisis_composicion.py`: auditoría de la base original y comparación de composiciones y secuencias.
- `notebooks/01_PCA_correlaciones_regresion_CS.ipynb`: explicación del análisis y ejecución.
- `tests/`: verificaciones con datos **sintéticos**, no de planta.
- `docs/`: metodología y auditoría.
