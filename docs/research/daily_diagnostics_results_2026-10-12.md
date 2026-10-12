# Diagnóstico de señal y calidad del dataset diario

Continuación del Draft PR #14, 12 de octubre de 2026. Se conservan modelo,
parámetros, seed, gate, universo y particiones. El modo principal continúa siendo
execution_aligned (label y ejecución t+1 a t+5). Las señales se generaron una sola
vez y se compararon transformaciones deterministas, sin optimizar por instrumento.
No se implementó ejecución pasiva, activa ni híbrida.

## Estado al retomar

La revisión anterior dejó el PR Draft con CI aprobado en c49141f. La reproducción
BTC con targets guardados coincide en +25,8934% / DD -9,6684%; su regeneración
causal histórica sigue bloqueada por gaps. Todas las variantes pierden neto en
2025 y dos de tres en el período parcial 2026. Este diagnóstico usa sólo el ZIP
diario de Leandro, que termina en noviembre de 2017. No agrega un holdout nuevo.
Portfolio permanece sin commit en su worktree original; engine conserva pendiente
su integración con MySQL y PR1 de mocks. Pipe no recibe cambios de fuente.

## Comparación del universo completo

7.132 símbolos evaluados de 8.431 historias válidas; 108 archivos rechazados
como en la auditoría anterior. Desarrollo hasta 2012, validación 2013–2014 y
análisis retrospectivo 2015–2017 parcial. PnL aditivo logarítmico acumulado, no
retorno anual ni resultado de una cuenta real autofinanciada. Capital fijo 1/N,
historia faltante en cash, sin redistribución hacia sobrevivientes.

| Escenario | Sin costo % | Con 5 bps % | DD log sin costo % | Exposición media por símbolo % |
| --- | ---: | ---: | ---: | ---: |
| Long/short original | +1.153481 | +0.940837 | -0.578809 | 2.3506 |
| Sólo long | +0.407661 | +0.278215 | -0.359835 | 1.1070 |
| Sólo short hipotético | +0.745820 | +0.662622 | -0.729281 | 1.2437 |
| Siempre long, mismas ventanas | -0.338158 | -0.522231 | -1.227564 | 2.3506 |
| Buy-and-hold al 15% | +1.521458 | +1.513958 | -4.983023 | 14.9848 |
| Cash | +0.000000 | +0.000000 | 0.000000 | 0.0000 |

Siempre-long aplica abs(target) a las mismas ventanas: controla la elección de
lado manteniendo exactamente la exposición absoluta y los intervalos operados.
Su turnover puede ser menor al evitar reversals. Buy-and-hold tiene el mismo
máximo 15%, pero mucha más exposición temporal; no es una comparación de riesgo
idéntico. Long-only y short-only mantienen el sizing original, sin reescalar para
igualar retrospectivamente la exposición. Todos los shorts son hipotéticos.

## Estabilidad anual

| Año | Long/short, 0 bps % | Long/short, 5 bps % | Siempre-long mismas ventanas, 0 bps % |
| --- | ---: | ---: | ---: |
| 2013 | +0.056043 | +0.008554 | +0.405209 |
| 2014 | +0.363747 | +0.311886 | -0.103723 |
| 2015 | +0.493572 | +0.450565 | -0.348137 |
| 2016 | -0.033102 | -0.066002 | +0.143562 |
| 2017 | +0.273221 | +0.235835 | -0.435069 |

2017 es parcial. Años ya inspeccionados y universo estático: los resultados son
diagnósticos, no evidencia de un nuevo test fuera de muestra. Cada grupo conserva
su propio denominador fijo y el calendario común de fechas observadas.

| Grupo | Símbolos | Long/short 0 bps % | Long/short 5 bps % |
| --- | ---: | ---: | ---: |
| Stock | 5848 | +1.247772 | +1.016570 |
| ETF | 1284 | +0.724032 | +0.595913 |

## Concentración y cobertura de calidad

A costo cero, top 10 representan 2.9890% del PnL
absoluto por símbolo y top 1% representan 13.0607%.
El top 10 aporta 4.7207% del PnL positivo, con ese
denominador explícito. Estos rankings no excluyen ni seleccionan instrumentos.
Mediana sin costo +0.039542%; proporción rentable
51.1778%. Con 5 bps: mediana +0.000000%
y proporción rentable 48.9905%.

Se inspeccionaron todas las 8431 historias válidas, incluso
las que no tienen evaluación elegible. Saltos usan abs(log ratio) > log(1.4),
volumen cero, cinco cierres consecutivos iguales y gaps mayores a siete días.
Ninguna bandera se usó como feature, filtro de entrenamiento o exclusión.

| Bandera, historia completa | Observaciones | Instrumentos |
| --- | ---: | ---: |
| Salto close/close | 9244 | 1949 |
| Salto open/close anterior | 5905 | 1425 |
| Volumen cero | 27633 | 1711 |
| Al menos 5 cierres iguales | 23962 | 1683 |
| Gap > 7 días | 15180 | 1366 |
| Intervalo open/open con salto | 11153 | 2014 |

476 historias válidas terminan antes de la fecha
final común. Esto no confirma delistings ni terminal payouts. Sin metadata no
podemos verificar splits/dividendos, precios ajustados, historial point-in-time,
licencia o cobertura de sobrevivientes. No corregimos ni rellenamos esos datos.

En long/short, los intervalos anotados ex-post por salto open/open o gap >7 días
aportan -0.054919% al PnL bruto medio y
3.4615% del movimiento absoluto ponderado total. Es
una atribución contable de intervalos ya realizados, no un backtest que permita
excluirlos con conocimiento previo. Su contribución puede ser positiva o negativa.

## Reproducibilidad y límites

La corrida confirmó el mismo hash efectivo de señal
`685bc4861124dbf839c092d676f64f80245253e211247d370247b092f57c619f` y registros de los cinco fits anuales idénticos.
Diferencia absoluta máxima contra las métricas principales previas:
0. El costo cero mantiene el resultado
anterior bruto de +1,153481%, y 5 bps conserva +0,940837%.

Se versionan protocolo, paridad, comparaciones anuales/grupales, concentración y
cuantiles. Detalle por símbolo, curvas y figuras quedan en
`artifacts/wristwatch/daily_diagnostics_2026-10-12/diagnostics/`, ignorado por Git.
El cache temporal se elimina al finalizar o fallar. Suite sintética y offline,
Ruff y comprobaciones de Git antes de publicar; PR sigue Draft sin reviewers.

Los costos 0/5 bps sólo descuentan turnover en la contabilidad actual. No modelan
spread, slippage, préstamo, fills ni posiciones en la cola. La inferencia de
significancia no se valida sobre datos cuyo adjustment/universo no está certificado.

## Próximo trabajo

En este historial, elegir el lado según el modelo mejora el PnL bruto medio
en 1,491639 puntos porcentuales frente a mantener las mismas ventanas siempre
long. Los dos lados aportan positivo, con mayor contribución del short hipotético.
El agregado es positivo en cuatro de cinco años, pero pierde en 2016. El top 10
no domina el PnL absoluto y los intervalos marcados aportan negativamente al
bruto, aunque eso no valida precios ajustados ni descarta otras anomalías.

Estos controles apoyan continuar la investigación de la señal direccional en
este dataset. El tamaño del efecto acumulado es modesto, la mediana baja, el
universo estático y la contabilidad de shorts hipotética: no se demuestra alpha
ejecutable ni generalización a datos actuales. No se eligen instrumentos o
parámetros después de mirar estos resultados.

Resolver procedencia, ajustes y cobertura point-in-time con el proveedor antes de
renovar el universo. Certificar contabilidad de shorts y definir un protocolo
nuevo antes de observar más datos. La etapa de ejecución comparará pasiva,
activa y combinaciones con precio fijado causalmente, timeout, cancelaciones,
fills parciales y salidas explícitas. La barra diaria no prueba que tocar el
precio haya ejecutado nuestra orden. Esta etapa sigue pendiente.
