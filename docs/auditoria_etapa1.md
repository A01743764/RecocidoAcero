# Protocolo de auditoría — Etapa 1 (independiente)

**Estado inicial: PENDIENTE de validación por otro integrante.** Las pruebas automáticas no sustituyen una auditoría de datos reales.

## Responsables y evidencia
- Desarrollador: presenta commit, versión de Python/dependencias, semilla, trazas del resultado y preguntas abiertas.
- Auditor independiente: usa copia de los Excel, reconstruye una muestra directamente desde la fuente, firma/fecha de revisión y registra diferencias.
- Intérprete físico: decide si las asociaciones son plausibles y si requieren límites o validación metalúrgica.

## Checklist para el integrante auditor
1. Abrir ambas hojas `Hoja2`, comprobar que los encabezados reales están en fila 2 y las unidades (°F, min, kg, mm) en fila 1.
2. Confirmar `RH- Carga` como identificador de carga; `RH- Posicion` como posición de bobina; `RH-Tiempo Neto carga` como tiempo real. Comprobar que el tiempo es único dentro de cada carga.
3. Tomar una muestra **manual** de ≥10 cargas, incluyendo cargas con posiciones duplicadas, temperatura cero, tiempos largos y cargas mixtas de la base original. Comparar cantidad de rollos, peso de carga, promedios geométricos y tiempo real contra el output.
4. Si se usa la base original, confirmar que solo se etiquetan como «solo CS» cargas cuyos **todos** los materiales tienen familia CS. Sin original, incluir advertencia de contaminación por mixtas.
5. Verificar que las filas repetidas por carga + posición no aumenten el número de bobinas; los conflictos deben producir error, no promedio silencioso.
6. Comparar recuentos antes/después de cada filtro; revisar por separado tiempo de saturación negativo, temperatura cero y ausencia de datos. Revisar extremos conservados.
7. Revisar que `RH-Eficiencia`, `RH-Tiempo STD Carga`, identificadores y la variable objetivo estén **fuera** de los predictores y del PCA. PCA se ajusta solo sobre entrenamiento.
8. Reproducir la partición con semilla 42 y recalcular a mano o con script independiente al menos una métrica: `MAE = media(|y_real - y_pred|)`; comprobar `R² = 1 - SSE/SST`.
9. Verificar las 5 particiones de CV sobre entrenamiento y comprobar que `R²` de prueba no se utiliza para seleccionar repetidamente variables.
10. Interpretar coeficientes con unidades y colinealidad. No asignar causalidad ni recomendar cambios de planta; validar primero calidad del producto.

## Resultado de auditoría
| Comprobación | Evidencia / archivo local | Resultado | Auditor y fecha |
| --- | --- | --- | --- |
| Filas, unidades, cargas | | pendiente | |
| Muestra manual y cargas mixtas | | pendiente | |
| Duplicados e inconsistencias | | pendiente | |
| Exclusión de fuga de información | | pendiente | |
| Reproducción de métricas | | pendiente | |
| Interpretación/limitaciones | | pendiente | |

**Criterio de avance:** solo cuando no haya discrepancias materiales sin explicar, los modelos superen (o se interpreten frente a) la referencia y la auditoría quede documentada, abrir etapa 2 del optimizador.

## Próxima etapa: recocido simulado
Su función objetivo debe ser un modelo validado y usar cotas justificadas por planta. Compararlo con búsqueda simple/rejilla y con la condición histórica de referencia; medir mejora respecto del error predictivo. Antes de integrar con planta, exigir evaluación térmica y de calidad. No confundir temperatura computacional de Metrópolis con temperatura del horno.
