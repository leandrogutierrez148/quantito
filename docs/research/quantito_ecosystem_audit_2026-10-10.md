# Auditoría Quantito — 10 de octubre de 2026

Auditoría desde repositorios y worktrees reales. Se leyeron completos AGENTS.md
y reglas aplicables antes de preparar o editar. La autorización posterior del
usuario permite implementar y publicar **sólo la POC en quantito**, preservando
la investigación portfolio. Ningún commit, push o cambio de fuente en pipe o
engine; ningún merge, job EODHD/BigQuery, broker ni servicio pago.

## Estado Git verificado

Se ejecutaron status, remotes, fetch origin --prune, logs, branches, worktrees,
stashes y consultas read-only de PRs. Todos los remotos corresponden a
`github.com/leandrogutierrez148/<repo>` por HTTPS. Sin stashes en los tres repos.
Los HEADs iniciales de la auditoría se registran aquí; los commits de la POC se
identifican en su PR y no alteran estos worktrees originales.

| Directorio | Rama / HEAD | Seguimiento y estado |
| --- | --- | --- |
| quantito | feat/portfolio-research-baseline / b6f472730abe25a4526a18da95db266dcc25ad81 | Sin upstream, cero commits propios sobre base histórica; sucio con Phase 1 sin commit |
| quantito-pipe | main / ef7d0ace3359984d9912e6117c31f6e4ec80e794 | origin/main igual, limpio; clonado como hermano |
| quantito-engine | fix/mockery-generation / 8817c54f1b35fd0629f0a2dafd65c3babbfc517d | origin/fix/mockery-generation igual, limpio; 1 ahead / 14 behind respecto de origin/main |
| quantito-wristwatch-poc | research/wristwatch-btc-poc | Worktree nuevo desde origin/master cef70908e95f4b55324095514e5f64fb87cfbcb0; POC aislada |
| quantito-engine-audit | detached / 02af325cbbdaf01bb6d1f4ac3761113a69b6f96c | Worktree de origin/main actualizado; fuente limpia, mocks generados ignorados |

`quantito/master` local sigue b6f4727, siete commits detrás de origin/master.
También se preservan `fix/p0-docker-exitcodes` (4fde366, cinco detrás de su
upstream) y `research/event-study-v0-recovery` (f3cb728, investigación offline
real sin PR ni upstream). `quantito-engine/main` local sigue 22308a0, catorce
commits detrás de origin/main. No se cambiaron ramas de worktrees sucios ni se
aplicó reset, clean, checkout de archivos, rebase o merge.

Cambios originales preservados en quantito: `pyproject.toml` modificado;
`research/` untracked; `tests/test_portfolio_{config,contracts,errors,hygiene,report,
weights_and_turnover}.py` untracked. La rama existe pero la implementación aún
no está committeada. **No existe PR portfolio**, ni rama remota equivalente:
verificado con pr status, lista all del autor actual, lista all general y head
`feat/portfolio-research-baseline`. El trabajo se encontró localmente.

PR engine [#1, Fix reproducible Mockery generation](https://github.com/leandrogutierrez148/quantito-engine/pull/1)
OPEN, dos archivos (.mockery.yaml y README), sin comentarios/reviews; único check
visible GitGuardian SUCCESS. Se revisó el diff completo. PRs engine #2–4 y
quantito #9–13 ya están merged; pipe no tiene PR abierto al momento de consulta.
No se escribió comentario o review remoto.

## Preparación y validaciones

| Superficie | Resultado |
| --- | --- |
| quantito original, portfolio incluido | unittest 105 OK, 1 skipped; Ruff check y format --check OK, 43 archivos |
| quantito-pipe nuevo .venv, editable [dev] | unittest 26 OK, 1 skipped; Ruff check y format --check OK, 17 archivos |
| engine rama original con mocks existentes | go test ./... OK |
| engine origin/main recién checkout | No puede testear: mocks ignorados faltantes; .mockery.yaml usa pkgname incompatible con Mockery v2.53.7 |
| engine audit preparado con config PR1 temporal | Mockery v2.53.7 genera mocks compatibles; make unit-tests OK, 10 paquetes |
| engine audit go test ./... fuera de sandbox | Unit tests OK; cuatro integration tests fallan por tests/integration/configs/config.toml ausente |
| POC quantito, tras corrección de review | pytest: 62 passed, 1 skipped, 29 subtests; unittest: 63 tests OK, 1 skipped; Ruff check/format y diff --check OK |

Se usa Go /opt/homebrew/bin/go, go1.27.1 darwin/arm64. Config temporal de Mockery:
`git show fix/mockery-generation:.mockery.yaml > /tmp/quantito-engine-audit-mockery.yaml`.
No se parcheó el archivo del repo. Se evitó la falsa conclusión de que main es
reproducible sólo porque existen mocks ignorados en el clon viejo.
Los tests de integración requieren MySQL desechable y configuración local;
sus helpers borran tablas. No se ejecutaron contra un servidor real ni se
leyeron credenciales. Un error inicial de httptest por sandbox se resolvió al
repetir fuera del sandbox; el bloqueo restante es configuración de integración.
Docker smoke tests Python fueron skipped, no presentados como aprobados.
La revisión del Draft PR añadió CI Python 3.12 offline, dos modos explícitos de
label diario, cleanup de caches y recuperación de ZIPs corruptos. Las métricas
diarias actuales y el cambio contra el resultado anterior se documentan en el
reporte de resultados. `execution_aligned` es principal; la emulación del label
original queda sólo como comparación. No se solicitaron reviewers.

## Diff portfolio Phase 1 y revisión

`research/portfolio/` contiene contratos, config, errores, validación long-only
con CASH, turnover one-way y RebalanceReport; seis archivos de tests. No hay
market data, optimizador, backtest ni provider implementados. Se revisaron todos
los módulos y pruebas, además del diff de pyproject. Los 105 tests pasan pero
no cubren los siguientes defectos detectados con contraejemplos ejecutados.

### Bloqueantes antes de Phase 2

- `validate_weights` acepta NaN: sumas/comparaciones no garantizan pesos finitos.
  Rechazar NaN/inf en cada peso, límites y sumas antes de tolerancias.
- Config admite `lambda_mu=inf` y conteos fraccionarios como lookback/scenarios
  2.5. Validar finitud, rangos y enteros estrictos (incluyendo bool) en cada campo.
- RebalanceReport debe proteger invariantes numéricos e inmutabilidad: una
  dataclass frozen no impide mutar dicts internos y NaN puede evadir validaciones.

### Importantes

- La base migró a src/quantito. El research flat uncommitted no queda incluido
  automáticamente en el packaging actual. Migrarlo en su propia rama antes de
  publicarlo; no mezclar ese diff con Wristwatch.
- CASH-first sólo fija la primera entrada, no ordena el resto. Igualdad de dicts
  en tests no demuestra bytes/order reproducibles. Definir orden de símbolos y
  probar JSON determinista con distintas inserciones.
- Pandas en dependencia principal no es necesario para contratos Phase 1;
  evaluar extra research. TYPE_CHECKING ya evita el import runtime básico.
- DECISION_CLOSE es una convención idealizada de mismo cierre. No reutilizarla
  para ejecución estricta t+1, ni los pesos long-only/turnover CASH para shorts.
- El PR1 engine sigue pendiente y main conserva el fallo de generación. Conviene
  revisar compatibilidad con interfaces actuales y resolución del PR por Leandro.
- Documentación pipe heredada menciona antiguo quantito/cloudbuild y heurísticas
  de estrategia; alinearla con ingestión, sin trasladar backtesting allí.

### Menores

- Hygiene usa exploración sólo del nivel superior; futuros submódulos quedarían
  fuera. Hacer recursiva la comprobación y no depender sólo de regex de imports.
- Si consumidores requieren get_type_hints runtime, TYPE_CHECKING requiere un
  contrato explícito para resolver pd; el import normal actual sí funciona.
- README histórico contenía un ejemplo con apariencia de credencial. No se usó
  ni se reproduce. Confirmar si era ficticio; si era real, invalidarlo y auditar
  historial. La base actual ya eliminó ese contenido heredado.

## Compatibilidad y responsabilidad

| Repositorio | Debe alojar |
| --- | --- |
| quantito-pipe | Clientes EODHD, ingestión incremental, jobs Cloud Run, validación de ingestión, persistencia BigQuery, metadatos de procedencia |
| quantito | Contratos research provider-agnostic, candidatos, features, walk-forward, simulaciones, métricas, reportes y evaluación stateless FastAPI de modelos validados |
| quantito-engine | Registro/orquestación de experimentos, locks y concurrencia, ledger, dispatch, lifecycle de ejecución y MySQL |

Portfolio research-only es compatible; no duplica pipe ni ledger engine.
Provider futuro debe entregar snapshots normalizados con procedencia, sin un
cliente EODHD dentro de la estrategia. La POC usa un downloader **research** de
archivos públicos reproducibles, sin infraestructura de ingestión productiva.
No se importó el portfolio uncommitted porque sus contratos no aplican a shorts.
La discrepancia de roles en el cierre del PDF se resuelve siguiendo la
arquitectura explícita del usuario y AGENTS actuales.

## Catálogo propuesto

| Categoría | Candidato | Artefacto / condición |
| --- | --- | --- |
| Reportes | Calidad/cobertura/procedencia | Manifest con hashes, calendarios, gaps, ajustes, licencias, point-in-time |
| Reportes | Ficha de experimento | Config/code/data hash, particiones, costos, PnL/DD/turnover, diferencias contra referencia |
| Reportes | Robustez y atribución | Lado, régimen causal, sesión, año, volatilidad, costos/delay y múltiples pruebas |
| Reportes | Portfolio rebalance | CASH primero, pesos antes/después, turnover discrecional y liquidaciones separados |
| Simulaciones | Walk-forward causal | Freeze, refits previos, t+1, metamorphic no-lookahead y datos faltantes explícitos |
| Simulaciones | Portfolio bootstrap | Stationary block bootstrap multivariado con seed y dependencia cross-asset |
| Simulaciones | Stress y transiciones | Liquidez/universo/gaps, costos, forced liquidation y drift |
| Estrategias | Benchmarks | Cash, buy-and-hold, equal-weight, inverse-vol, minimum variance, CVaR sin retorno |
| Estrategias | Portfolio CVaR | CVXPY/Clarabel tras completar los contratos y validación causal |
| Estrategias | BTC Wristwatch | POC recuperada; evidencia insuficiente para promoción |
| Estrategias | Event study recuperado | Revisar rama f3cb728 antes de reutilizar utilidades o formular otro candidato |

Cada candidato debe declarar estado proposed/implemented/evaluated/validated,
owner, hypothesis, datos permitidos, config/seed y gate de promoción. Una lista
de mejores instrumentos observados es descriptiva y no un catálogo de ganadores.

## Plan incremental y acciones recomendadas

1. Revisar el Draft PR Wristwatch y los resultados separados; no aprobar ejecución.
2. En worktree propio de portfolio, portar Phase 1 a src y resolver finitud,
   enteros, reportes y serialización. Preservar originales hasta integrar su diff.
3. Phase 2A: datos/retornos y calendario causal; 2B estimadores/covarianza; 2C
   bootstrap multivariado; 2D transiciones y liquidaciones; 2E CVXPY/Clarabel;
   2F benchmarks. Entregables pequeños con contratos y pruebas pertinentes.
4. Phase 3: backtest causal, CASH, costos, métricas y metamorphic test.
   Phase 4: provider de snapshots con procedencia. Phase 5: CLI/reportes versionados.
5. Resolver pipeline reproducible de mocks engine mediante revisión PR1 actual;
   configurar sólo MySQL de tests desechable y correr integración. No fusionar
   automáticamente por el resultado de esta auditoría.
6. Wristwatch: certificar datos y paridad de features, gaps sin filtro futuro,
   contabilidad executable y costos. Fijar un protocolo nuevo antes de observar
   más resultados; 2025/2026 ya no son holdouts frescos.
7. Para promover un modelo validado: bundle versionado con features/schema,
   parámetros, hashes, entrenamiento/cutoff, contrato de señales y límites;
   adapter stateless en quantito y luego PR operativo específico. Engine conserva
   ledger, idempotencia, concurrencia y dispatch; pipe conserva ingestión.

Comandos de la POC están en [wristwatch_btc_poc.md](wristwatch_btc_poc.md).
Comandos de validación adicionales:

```sh
cd ~/Code/quantito-pipe
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m unittest discover tests
cd ~/Code/quantito-engine-audit
GOCACHE=/tmp/quantito-go-cache make unit-tests
# go test ./... solamente tras disponer de configuración de MySQL desechable.
```

Decisiones humanas pendientes: licencia/ajustes/delistados del ZIP; resolución
del PR1 y configuración de integración engine; tratamiento recuperable de gaps
BTC; protocolo estadístico y accounting de shorts antes de promoción. Ninguna
de estas decisiones justifica inventar una estrategia o métricas para el PR.
