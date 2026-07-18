# DDIA-Inspired Trade-off Lens

## Procedencia y límite

Este documento resume S2, una reseña audiovisual de Designing Data-Intensive Applications; no sustituye el libro. Las atribuciones o citas destinadas a publicación deben validarse en una edición autorizada. Los conceptos usados aparecen en S2, líneas 15–123 y 175–329.

## Regla central

No existe una decisión técnica adecuada para todos los contextos. La pregunta correcta no es “¿cuál herramienta es mejor?”, sino “¿qué garantías requiere esta misión y qué costo aceptamos?”.

## Cinco preguntas antes de diseñar

1. **Carga dominante:** ¿la misión es compute-intensive, como procesar video, o data-intensive, como agregar investigación y métricas?
2. **Fiabilidad:** ¿qué debe seguir funcionando cuando una herramienta o red falla?
3. **Escalabilidad:** ¿qué crece: número de assets, tamaño de archivos, concurrencia, fuentes o retención?
4. **Mantenibilidad:** ¿puede otro agente o humano comprender, verificar y cambiar el flujo?
5. **Resiliencia y auditoría:** ¿podemos reconstruir qué ocurrió sin depender del estado mutable actual?

## Decision record mínimo

Cada decisión relevante debe registrar:

- contexto y restricción;
- opciones consideradas;
- opción elegida;
- beneficio esperado;
- trade-off aceptado;
- señal que invalidaría la decisión;
- evidencia o experimento;
- responsable y fecha.

## Aplicación al runtime

### Eventos antes que acoplamiento oculto

S2, 219–285 presenta flujos asíncronos y eventos auditables. Una estación debe emitir un evento trazable con rol, acción, estado, detalle y referencias a artefactos/evidencia. La estación siguiente reacciona a ese contrato; no debe depender de variables implícitas.

### Fallos parciales son normales

S2, 175–218 subraya redes y relojes como puntos de fallo. Por tanto:

- timestamps explícitos y en una zona acordada;
- timeouts acotados;
- reintentos idempotentes con límite;
- estado blocked cuando falta una dependencia;
- no asumir que ausencia de respuesta equivale a éxito;
- recibos para cualquier efecto externo.

### Historial auditable

Un event stream permite reconstruir una ejecución (S2, 251–277). Los eventos no deben sobrescribirse; las correcciones se agregan como nuevos eventos. Los artefactos se referencian por ID y versión.

### Cuellos de botella visibles

La reseña usa el ejemplo de una cocina para explicar límites de capacidad (S2, 88–123). Medir por estación:

- queue time;
- processing time;
- tasa de fallo;
- tamaño de artefacto;
- costo estimado;
- espera de aprobación.

## Scholar: patrón de tres puntos

Cuando Research entrega un concepto técnico, añade:

1. **Reencuadre cognitivo:** qué supuesto común cuestiona.
2. **Tensión del trade-off:** qué ganamos y qué sacrificamos.
3. **Resolución operativa:** qué decisión o experimento pequeño puede ejecutar la audiencia.

Este formato organiza la explicación; no prueba la veracidad del concepto. La evidencia sigue siendo obligatoria.

