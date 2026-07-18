# Skill: CRO

## Objetivo

Reducir fricción y aumentar una acción valiosa mediante experimentos éticos. CRO no es cambiar botones al azar ni maximizar clics a costa de confianza.

## Entradas

- etapa del funnel;
- segmento;
- acción objetivo;
- baseline y fuente;
- evidencia cualitativa/cuantitativa;
- restricciones técnicas y de marca;
- volumen o ventana disponible.

## Procedimiento

1. Dibuja el journey y localiza el mayor punto de abandono observable.
2. Separa síntoma de causa.
3. Resume evidencia a favor y en contra.
4. Formula: para segmento, si cambio, entonces métrica, porque evidencia.
5. Cambia una variable principal por experimento.
6. Define control, variante, unidad de asignación y ventana.
7. Elige métrica primaria y guardrails.
8. Define stop conditions por daño, costo o señal suficiente.
9. Revisa consentimiento, accesibilidad y reversibilidad.
10. Al terminar, decide keep, iterate o stop y registra limitaciones.

## Salida

- funnel_stage;
- friction;
- evidence_ids;
- hypothesis;
- control;
- variant;
- primary_metric;
- guardrails;
- allocation;
- time_window;
- sample_caveat;
- stop_conditions;
- implementation_notes;
- result_interpretation_template.

## Guardrails éticos

- Sin cuenta regresiva falsa.
- Sin opción de rechazo escondida.
- Sin consentimiento preseleccionado.
- Sin costos, condiciones o patrocinio ocultos.
- Sin spam ni captación de datos innecesarios.
- Sin declarar causalidad cuando sólo existe correlación.

## Métricas

La conversión siempre tiene numerador, denominador, ventana y fuente. CAC requiere gasto y conversiones atribuibles; si conversiones es cero, CAC no se representa como cero.

