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

## ZIP de Leandro: adaptación diaria obligatoria

8.539 instrumentos únicos; 8.431 válidos, 108 rechazados explícitamente.
7.132 evaluados, 1.299 sin evaluación elegible tras warmup. Partición común
congelada antes de métricas: desarrollo hasta 2012, validación 2013–2014,
evaluación retrospectiva 2015–2017. Sin datos de 2025 o 2026 en este ZIP.

| Medida cross-sectional, 2013–2017 parcial | Resultado |
| --- | ---: |
| PnL neto medio / equal-weight, 5 bps | +0,3482% |
| Mediana neta | +0,0232% |
| Símbolos rentables | 50,62% |
| Medio neto, costos 0 / 10 / 20 bps | +0,6074% / +0,0889% / -0,4295% |
| Contribución media long / short | -0,1371% / +0,4852% |
| Exposición absoluta media | 2,624% |
| Buy-and-hold equal-weight | +10,0931% |
| Cash | 0% |
| Concentración de PnL absoluto, top 10 | 2,66% |
| ETFs: 1284 evaluados, medio / mediana | +0,4139% / +0,1003% |
| Acciones: 5848 evaluadas, medio / mediana | +0,3337% / 0% |

Buy-and-hold tiene exposición 100%, la estrategia máximo 15% y media 2,624%:
no es una comparación de riesgo equivalente. Años equal-weight con capital fijo:
2013 -0,1099%, 2014 +0,2004%, 2015 +0,3512%, 2016 -0,0639%, 2017 -0,0297%.
Validación suma +0,0905%; evaluación posterior +0,2577%. No se eligieron símbolos
por resultado, ni se redistribuyó capital diariamente hacia sobrevivientes.

La distribución, mejores/peores descriptivos, métricas por símbolo, costos,
long/short, Sharpe, DD, trades, exposición y estabilidad anual están en
`artifacts/wristwatch/`. Los agregados pequeños se versionan en
[`results/2026-10-10`](results/2026-10-10/); datasets y curvas grandes están ignorados.
No hay sectores verificables; sólo clasificación Stock/ETF por estructura del ZIP.

## Conclusión y decisiones pendientes

Se reproduce la cifra histórica con targets guardados, pero el edge no muestra
robustez suficiente: las tres variantes pierden neto en 2025, dos pierden en
2026 y los costos eliminan rápidamente los beneficios. La adaptación diaria
muestra resultados débiles e inestables, sin evidencia estadística suficiente
de generalización ni exclusividad BTC. No se calcula significancia sobre un
universo con ajustes, deslistados y derechos de uso sin verificar.

Antes de promoción: resolver los gaps sin selección por precios futuros,
certificar paneles y fuente, confirmar licencia/ajustes/delistados, modelar borrow
y fills ejecutables, corregir contabilidad de cuenta real y declarar un protocolo
con período verdaderamente no inspeccionado y control de múltiples pruebas.
No promover esta POC a ejecución.
