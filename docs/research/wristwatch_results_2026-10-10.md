# Wristwatch: resultados de la POC, 10 de octubre de 2026

## Cuatro experimentos separados

1. **BTC histórico, replay de posiciones guardadas**: reproducción contable de
   los targets originales con precios oficiales de un minuto. Conserva el sesgo
   del filtro original de disponibilidad futura; no certifica la señal causal.
2. **BTC 2025 y reciente 2026, señal regenerada**: fórmula HGB recuperada,
   features anteriores a la decisión, refits anteriores al año y ejecución t+1.
3. **Aplicación intradiaria al ZIP de Leandro**: no aplicable; todos sus archivos
   no vacíos son diarios y no contienen BTC intradiario.
4. **Adaptación diaria cross-asset**: ejecutada por separado, con configuración
   común, modelo pooled, ventanas declaradas y delay de una barra.

Los porcentajes siguientes son PnL aditivo de retornos logarítmicos ponderados y
drawdown logarítmico. No equivalen a retornos de una cuenta spot autofinanciada.
Default: exposición firmada 0,15, costo round-trip 5 bps, delay un minuto.

| Experimento / variante | PnL neto % | Maximum drawdown % | Sharpe diario | Entradas |
| --- | ---: | ---: | ---: | ---: |
| Histórico 2018–03/08/2024, targets originales | 25,8934 | -9,6684 | 0,5716 | 4078 |
| 2025, agosto | -3,0378 | -5,3407 | -1,0423 | 547 |
| 2025, octubre | -1,2241 | -4,5253 | -0,4681 | 426 |
| 2025, enero | -1,4616 | -4,5369 | -0,4519 | 490 |
| 2026, agosto | 0,9307 | -2,4952 | 0,4082 | 507 |
| 2026, octubre | -3,6828 | -6,0971 | -1,3663 | 418 |
| 2026, enero | -0,3966 | -2,3241 | -0,1794 | 501 |

2025: 02/01/2025–01/01/2026 exclusivo. 2026: 02/01/2026–30/09/2026
exclusivo, corte conservador de días completos. 2025 ya estaba inspeccionado;
2026 tampoco debe llamarse holdout fresco después de este análisis.
Las variantes de 2025 regeneradas coinciden con las posiciones guardadas.

## Diferencias con el brief

El replay histórico reproduce +25,89% / -9,67% a la precisión publicada:
bruto 56,4784%, costos 30,5850%, neto 25,8934%. Se usaron 109 ZIPs oficiales
Binance BTCUSDT spot de septiembre de 2017 a septiembre de 2026, todos con
CHECKSUM verificado; ningún exchange se mezcló silenciosamente.

La regeneración causal completa del histórico queda **bloqueada por precios
realizados ausentes**. El código original seleccionaba también por completitud
futura; al eliminar ese filtro aparecen posiciones que necesitan precios faltantes.
No se publica un PnL inventado ni se rellenan precios. Hay 30.163 minutos ausentes
en la grilla completa, incluyendo 21.602 timestamps fuera de minuto puestos en
cuarentena (20.401 diciembre 2017, 1.201 febrero 2018), nunca redondeados.

Solapamiento con cache local 2022–agosto 2024: para cada delay 0/1/2/5, 45.359
opens coinciden exactamente y dos timestamps oficiales faltan; diferencia media
y máxima cero entre observaciones presentes. Esto valida ese solapamiento, no
todo el feature engineering histórico. Los paneles externos históricos siguen
siendo entradas explícitas; reconstruirlos íntegramente exige certificar warmup,
gaps y paridad con el código fuente recuperado.

Con los mismos targets históricos y delay un minuto: costo 0 bps produce
56,4784%; 5 bps produce 25,8934%; 10 bps produce -4,6916%.
Con costo 5 bps: delay 0/1/2/5 minutos produce 36,5573 / 25,8934 / 21,2185 /
22,7674%. El brief 30m reporta +36,56% / -8,50%; el replay minuto sin delay
coincide en PnL pero observa DD -8,6470%, porque mide oscilaciones intrabar.
La matriz de marcas 30m está etiquetada optimista y conserva fallos de cobertura.
La sensibilidad de target es un reescalado analítico de las mismas posiciones
(0,05/0,10/0,15/0,20), no búsqueda de un target ganador ni nueva señal.

## Descomposición causal y descriptiva

Histórico frozen: long +12,7549%, short +13,1385%. Por régimen: bull +16,2324%,
lateral +8,6989%, bear -2,5671%, desconocido +3,5292%. Por sesión UTC:
00–08 -6,2923%, 08–16 +29,5197%, 16–24 +2,6660%.
En 2025 enero: long +0,5147%, short -1,9763%; en 2026 enero: long +0,1146%,
short -0,5113%. Son atribuciones explicativas; elegir ahora sólo la sesión o
el lado rentable introduciría una nueva selección retrospectiva.
Los artefactos incluyen también año, volatilidad, operaciones, exposición,
turnover y duración; posiciones consecutivas iguales se netean y pueden durar
más de dos horas como posición económica continua.

## ZIP de Leandro: adaptación diaria obligatoria corregida

8.539 instrumentos únicos; 8.431 válidos, 108 rechazados explícitamente.
7.132 evaluados, 1.299 sin evaluación elegible tras warmup. Partición común
congelada antes de cada corrida: desarrollo hasta 2012, validación 2013–2014,
evaluación retrospectiva 2015–2017. Sin datos de 2025 o 2026 en este ZIP.

La revisión corrigió el desalineamiento entre label y ejecución. El resultado
principal es **execution_aligned**: entrenamiento log(open[t+5]/open[t+1]),
con label_entry t+1 y label_exit t+5. **source_label_emulation** conserva
log(open[t+4]/open[t]) y label_exit t+4 sólo para comparar el mapeo ordinal original.
Ambos operan t+1→t+5; los offsets son observaciones de negociación, no días
calendario. Cada modo excluye del entrenamiento labels cuyo exit no sea
estrictamente anterior al cutoff anual. Tests de índices, cutoff y PnL realizado
verifican la alineación; no se cambiaron costos ni se eligieron símbolos ganadores.

| Medida 2013–2017 parcial, 5 bps round-trip | execution_aligned, principal | source_label_emulation, comparación |
| --- | ---: | ---: |
| PnL neto medio / equal-weight | +0.940837% | +0.348158% |
| Cambio contra el resultado anterior | +0.592679 pp | +0.000000 pp |
| Mediana neta | +0.000000% | +0.023230% |
| Símbolos rentables | 48.9905% | 50.6169% |
| Bruto / costo 0 bps, medio | +1.153481% | +0.607387% |
| Neto medio, costo 10 bps | +0.728194% | +0.088928% |
| Neto medio, costo 20 bps | +0.302906% | -0.429531% |
| Contribución media long | +0.278215% | -0.137075% |
| Contribución media short | +0.662622% | +0.485233% |
| Exposición absoluta media | 2.3506% | 2.6240% |
| Equal-weight máximo DD log | -0.584225% | -0.502885% |
| Equal-weight Sharpe, 252 | 0.768051 | 0.266305 |
| Validación 2013–2014 | +0.320440% | +0.090497% |
| Evaluación retrospectiva 2015–2017 | +0.620397% | +0.257660% |

El +0,3481578767% previamente publicado pertenece exclusivamente al modo de
emulación. El resultado principal actual es +0.940837%, un cambio
de +0.592679 puntos porcentuales. La corrección
se hizo después de inspeccionar el dataset y de la review; no crea un holdout nuevo.
No se mezclan conclusiones de la adaptación diaria con la reproducción BTC.

Buy-and-hold equal-weight sigue en +10.093054% y cash en 0%.
Buy-and-hold tiene exposición 100%, la estrategia máximo 15%; no es una comparación
de riesgo equivalente. Equal-weight usa capital fijo sobre los 7.132 símbolos y
deja historia faltante en cash, sin redistribución hacia sobrevivientes.

Años del modo principal (PnL log):

- 2013: +0.008554%.
- 2014: +0.311886%.
- 2015: +0.450565%.
- 2016: -0.066002%.
- 2017: +0.235835%.

ETFs: 1284 evaluados, media +0.595913%; acciones: 5848 evaluadas, media +1.016570%.

La distribución, mejores/peores descriptivos, métricas por símbolo, costos,
long/short, Sharpe, DD, trades, exposición y estabilidad anual se regeneraron en
`artifacts/wristwatch/daily_revision/<modo>/`. Los artefactos diarios del directorio
raíz se actualizaron al modo principal. Los agregados pequeños principales están
versionados en `results/2026-10-10/`, y los de comparación en su subdirectorio
`source_label_emulation/`. Los configs incluyen mode y years en el hash efectivo.
No hay sectores verificables; sólo clasificación Stock/ETF por estructura del ZIP.

## Correcciones de calidad y CI

`run_daily()` usa `TemporaryDirectory` y elimina los Parquet temporales al terminar
o al propagarse una excepción. Dos tests reales con un ZIP sintético verifican
cleanup tras éxito y tras fallo de fit después de escribir el cache.
El downloader preserva ZIPs corruptos con sufijo `.corrupt`, valida `.part` y sólo
entonces renombra atómicamente; tests sin HTTP verifican fallo, recuperación,
interrupción y reutilización de un archivo válido.

Se agregó GitHub Actions Python 3.12: instalación `.[dev,research]`, pytest, Ruff
lint/formato y `git diff --check`. Tests sintéticos y offline; el Docker build
smoke existente se omite explícitamente con `QUANTITO_OFFLINE_TESTS=1` porque
puede descargar dependencias. Suite local: 62 passed, 1 skipped, 29 subtests;
unittest 63 tests OK, 1 skipped; Ruff y diff checks OK. Sin datasets, caches,
Parquet grandes ni credenciales incorporados a Git. PR conservado como Draft.

## Conclusión y decisiones pendientes

Se reproduce la cifra histórica con targets guardados, pero el edge BTC no
muestra robustez suficiente: las tres variantes pierden neto en 2025, dos pierden
en 2026 y sus costos erosionan rápidamente los beneficios. La corrección del
label diario aumenta el neto medio a +0,940837% y mantiene +0,302906% a 20 bps:
ya no corresponde afirmar que esos costos eliminan el beneficio del modo diario
principal. Sin embargo, mediana 0%, sólo 48,99% de símbolos rentables, retornos
pequeños y metadata no verificada no demuestran generalización estadísticamente
defendible ni exclusividad BTC. El resultado depende materialmente de alinear
label y ejecución; no se seleccionó el modo por ser el más rentable, sino por
corresponder al intervalo operado. No se calcula significancia sobre un universo
con ajustes, deslistados y derechos de uso sin verificar. La recomendación de
no promover a ejecución se mantiene.

Antes de promoción: resolver los gaps sin selección por precios futuros,
certificar paneles y fuente, confirmar licencia/ajustes/delistados, modelar borrow
y fills ejecutables, corregir contabilidad de cuenta real y declarar un protocolo
con período verdaderamente no inspeccionado y control de múltiples pruebas.
No promover esta POC a ejecución.
