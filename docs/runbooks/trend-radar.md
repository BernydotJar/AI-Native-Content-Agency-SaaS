# Radar gratuito de tendencias

El radar de CampaignOS consulta señales públicas de Google Trends para Guatemala sin
usar una clave de API ni habilitar efectos externos. Su objetivo es aportar contexto a
la investigación inicial; no reemplaza la validación editorial, legal o de fuentes.

## Contrato operativo

- Endpoint autenticado: `GET /api/v1/trends?geo=GT&limit=8`.
- Fuente fija: `https://trends.google.com/trending/rss?geo=GT`.
- Geografía permitida: `GT`.
- Operación: sólo lectura.
- Costo directo de API: ninguno; no requiere credencial de Google.
- Publicación, inferencia y pauta: no se habilitan.
- La respuesta incluye fuente, hora de consulta, título, volumen aproximado, fecha y
  medio relacionado cuando la fuente lo publica.

## Comportamiento fail-closed

El servidor no genera tendencias sintéticas ni reutiliza una lista de ejemplo cuando la
fuente falla. Devuelve `503 trend_radar_unavailable` si ocurre cualquiera de estas
condiciones:

- error de red o timeout;
- respuesta HTTP distinta de 200;
- redirección inesperada;
- documento mayor de 512 KiB;
- XML inválido o con declaraciones prohibidas;
- documento que no sea RSS;
- respuesta sin elementos verificables.

La interfaz transforma ese error en un estado visible de indisponibilidad y conserva la
lista vacía. No presenta resultados inventados.

## Límites de seguridad

- El host y la ruta están definidos en código; el usuario no puede convertir el endpoint
  en un proxy arbitrario.
- El cliente HTTP ignora proxies del entorno, no sigue redirecciones y usa timeout
  acotado.
- La sesión deriva tenant, identidad y permisos en el servidor.
- La respuesta nunca incluye contraseñas, cookies, tokens ni cuerpos de error del
  proveedor.
- Los resultados son señales de atención, no recomendaciones automáticas de contenido.

## Verificación

```bash
./scripts/verify-python-locks.sh
npm test
npm run lint
npm run build
```

Para una comprobación manual segura, inicia el producto, autentícate y abre **Radar
gratuito · Guatemala**. El pie debe mostrar la hora de actualización y el enlace a la
fuente. Si Google no responde con RSS verificable, debe mostrarse **Radar temporalmente
no disponible** sin tarjetas de tendencias.
