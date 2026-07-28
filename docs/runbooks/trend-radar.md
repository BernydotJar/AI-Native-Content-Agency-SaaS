# Radar gratuito de tendencias y piloto editorial

CampaignOS consulta señales públicas para Guatemala sin usar una clave de API, créditos
de X ni efectos externos. El radar sirve para descubrir una señal, revisar evidencia y
precargar una misión editorial gobernada. No sustituye la validación humana de hechos,
fuentes, derechos, tono o riesgo.

## Líneas de investigación

El parámetro `topic` es una enumeración cerrada. El usuario no puede convertir el radar
en un buscador o proxy arbitrario.

| `topic` | Fuente fija | Consulta editorial fija | Uso |
| --- | --- | --- | --- |
| `general` | Google Trends RSS | tendencias de búsqueda para `geo=GT` | atención inmediata |
| `ai` | Google News RSS | `inteligencia artificial Guatemala` | tecnología e IA |
| `marketing` | Google News RSS | `marketing digital Guatemala` | marcas, creadores y audiencias |
| `business` | Google News RSS | `emprendimiento Guatemala` | negocios y economía local |

Contrato autenticado:

```text
GET /api/v1/trends?geo=GT&limit=8&topic=general
GET /api/v1/trends?geo=GT&limit=8&topic=ai
GET /api/v1/trends?geo=GT&limit=8&topic=marketing
GET /api/v1/trends?geo=GT&limit=8&topic=business
```

La respuesta incluye:

- fuente y hora de consulta;
- tipo de señal (`search_trend` o `news_signal`);
- título, fecha, medio y volumen aproximado cuando existe;
- hasta tres enlaces HTTPS de evidencia para cada tendencia de búsqueda;
- un enlace HTTPS de evidencia para cada señal de noticias.

Costo directo de API: ninguno. El radar no requiere credenciales de Google ni consulta la
API de X.

## Flujo de piloto en la UI

1. Inicia sesión en CampaignOS.
2. Abre **Radar gratuito · Guatemala**.
3. Elige **Ahora**, **IA**, **Marketing** o **Negocios**.
4. Abre **Revisar evidencia** antes de convertir la señal en contenido.
5. Pulsa **Preparar piloto**.
6. CampaignOS precarga una misión editable con:
   - X e Instagram seleccionados;
   - presupuesto `0`;
   - campaña comercial y orgánica;
   - `campaign_goal=trend_response_pilot`;
   - una afirmación marcada `unverified` y ligada al enlace de evidencia;
   - instrucciones explícitas de no publicar.
7. Revisa el brief y pulsa **Ejecutar campaña** para generar artefactos internos.
8. El output muestra **Piloto de tendencia · sólo revisión**. Copiar el borrador está
   permitido; publicar sigue sujeto a Greenlight, conexiones, switches y confirmación
   externa.

Preparar o ejecutar un piloto no habilita:

- publicación social;
- publicación política;
- pauta política;
- inferencia remota de modelos;
- gasto o recursos cloud.

## Comportamiento fail-closed

El servidor no genera tendencias sintéticas ni reutiliza listas de ejemplo. Devuelve
`503 trend_radar_unavailable` cuando ocurre cualquiera de estas condiciones:

- error de red o timeout;
- respuesta HTTP distinta de `200`;
- redirección inesperada;
- documento mayor de 512 KiB;
- XML inválido o con `DOCTYPE`/`ENTITY`;
- documento que no sea RSS;
- respuesta sin elementos verificables.

La interfaz muestra **Radar temporalmente no disponible** y conserva la lista vacía.

## Límites de seguridad

- Los hosts, rutas y consultas están definidos en código.
- Sólo `GT` y los cuatro topics enumerados son válidos.
- El cliente HTTP no sigue redirecciones, ignora proxies del entorno y usa timeout
  acotado.
- Sólo se exponen enlaces HTTPS sin usuario, contraseña ni fragmento.
- La sesión deriva tenant, identidad y permisos en el servidor.
- Nunca se devuelven cookies, tokens, credenciales ni cuerpos de error del proveedor.
- Las señales son insumos de investigación, no hechos verificados ni recomendaciones
  automáticas.

## Verificación

```bash
PYTHONPATH=backend /tmp/ai-native-content-agency-runtime/bin/python \
  -m unittest discover -s backend/tests
npm test
npm run lint
npm run build
npm run verify:accessibility-browser
npm run validate:program
npm run validate:compliance
npm run validate:operability
```

La comprobación manual segura debe demostrar:

- cuatro líneas de investigación con ocho resultados cuando la fuente responde;
- evidencia HTTPS visible;
- brief precargado con X e Instagram y presupuesto cero;
- output marcado como piloto;
- todos los botones **Publicar** deshabilitados mientras los switches sigan cerrados.
