# Metodología — datos CS y regresión

## Alcance
1. Base depurada: selección **de filas CS**. La depuración previa no contiene MS/otros; sin contraste con el Excel original **no se certifica** la composición completa de cada carga.
2. Base original opcional (recomendada): restringe a cargas cuyas familias completas son exactamente {CS}.
3. No se edita ninguno de los Excel; las salidas quedan en la carpeta local ignorada por Git.

## Ingeniería de variables, por carga
- Tiempo neto real (min): `RH-Tiempo Neto carga` → `tiempo_real_min`; un valor por carga.
- Peso en kg: `RH- Peso Carga` registrado, no suma de bobinas CS.
- `n_rollos`: número de posiciones distintas en el archivo depurado.
- Espesor y ancho medios en mm: promedio simple de posiciones distintas, no ponderado.
- Temperatura de saturación °F; tiempo de saturación min. Las unidades no se transforman.

**Filtros para modelo**: objetivo > 0; peso, ancho y espesor > 0; temperatura de saturación > 0; tiempo de saturación >= 0; todas las variables presentes. Se cuentan y conservan por separado las cargas excluidas. Se retienen los atípicos plausibles en el análisis principal para evitar selección favorable de resultados.

## Exploración antes de modelar
- Correlaciones de Pearson, solo relaciones lineales descriptivas; revisar dispersión y colinealidad.
- PCA: `StandardScaler` + `PCA` sobre variables explicativas; varianza explicada, cargas de componentes y plano PC1-PC2. El objetivo nunca entra al PCA.
- PCA no «demuestra» relevancia para predecir el tiempo, porque es no supervisado.

## Regresión y validación
- Modelo de referencia: mediana del tiempo de entrenamiento.
- Modelo A: regresión múltiple con geometría de carga (peso, cantidad de rollos, espesor, ancho).
- Modelo B: geometría + temperatura y minutos de saturación, **solo como modelo explicativo retrospectivo**.
- Partición aleatoria reproducible **por carga** 80/20; una carga no puede aparecer simultáneamente en entrenamiento y prueba.
- Validación cruzada de 5 particiones solo en entrenamiento; errores y R² fuera de entrenamiento.
- Regresión lineal con estandarización; los coeficientes reportados se convierten a unidades originales (min/kg, min/mm, min/°F, etc.).
- No se calculan p-valores ni IC de coeficientes en esta etapa; no afirmar significación sin modelo estadístico y comprobaciones pertinentes.

## Limitaciones y próximos pasos
La muestra seleccionada no es un experimento aleatorizado. Variaciones en horno, receta, estado inicial, apilamiento y calidad pueden confundir relaciones. Las variables de carga quedan resumidas; no se distingue el orden CS/MS. Sin mediciones de propiedades finales no es posible afirmar que disminuir tiempo preserve calidad. Antes de usar recocido simulado, auditar la etapa predictiva, establecer límites de factibilidad y confrontar con simulación térmica.
