# Conexión segura de X e Instagram

El runtime admite dos formas de conectar una cuenta social:

1. **OAuth interactivo**, recomendado para clientes y operación SaaS.
2. **Bootstrap server-side de tokens existentes**, útil para pruebas controladas o
   migraciones. Los tokens nunca se introducen en el navegador.

La conexión de una cuenta no habilita publicación automática. `Publicar` continúa
bloqueado hasta que exista una intención/receipt durable de publicación y Greenlight
válido para el artefacto y canal exactos.

## Preparación local

```bash
cp .env.example .env.local
npm run generate:social-key
```

El generador reemplaza únicamente las dos asignaciones de cifrado vacías dentro de
`.env.local`, oculta el valor y fija permisos `0600`. Se niega a sobrescribir una clave
existente, un symlink o un archivo que Git esté rastreando. No redirijas la salida de
`npm run` hacia el archivo: npm también imprime encabezados de ejecución.

El archivo está ignorado por Git y `npm run start:local` lo carga automáticamente. El
runner se niega a utilizar un archivo local que Git esté rastreando.

Verifica antes de guardar valores:

```bash
git check-ignore -v .env.local
git status --short
```

## OAuth interactivo

Configura la aplicación y las callback URLs exactas:

```dotenv
AGENCY_X_CONSUMER_KEY=
AGENCY_X_CONSUMER_SECRET=
AGENCY_X_REDIRECT_URI=http://127.0.0.1:4175/api/v1/social-channels/x/oauth/callback

AGENCY_INSTAGRAM_APP_ID=
AGENCY_INSTAGRAM_APP_SECRET=
AGENCY_INSTAGRAM_REDIRECT_URI=http://127.0.0.1:4175/api/v1/social-channels/instagram/oauth/callback
```

Inicia el producto:

```bash
npm run start:local
```

Después:

1. conecta el espacio con la credencial local del tenant;
2. abre **Configuración → Canales de publicación**;
3. pulsa **Conectar cuenta** como administrador;
4. autoriza la cuenta en X o Instagram;
5. vuelve al mismo navegador y sesión;
6. confirma que aparece `@usuario` y `tokens cifrados server-side`.

X usa OAuth 1.0a user context de tres pasos. Instagram usa Authorization Code y sólo
acepta cuentas Professional (Business o Creator). El state OAuth es single-use, expira
a los diez minutos y está ligado a tenant, sesión y canal.

## Bootstrap de tokens existentes

Configura siempre el tenant receptor y el grupo completo del canal. Una configuración
parcial hace fallar el arranque.

For OAuth-only setup, keep `AGENCY_SOCIAL_BOOTSTRAP_TENANT_ID` empty.

```dotenv
# Set this only when at least one complete token group below is configured.
AGENCY_SOCIAL_BOOTSTRAP_TENANT_ID=local-tenant

AGENCY_X_USER_ACCESS_TOKEN=
AGENCY_X_USER_ACCESS_TOKEN_SECRET=
AGENCY_X_ACCOUNT_ID=
AGENCY_X_ACCOUNT_USERNAME=

AGENCY_INSTAGRAM_ACCESS_TOKEN=
AGENCY_INSTAGRAM_ACCOUNT_ID=
AGENCY_INSTAGRAM_ACCOUNT_USERNAME=
AGENCY_INSTAGRAM_TOKEN_EXPIRES_AT=
```

Al iniciar, los tokens se cifran con AES-GCM antes de persistirse. El bootstrap es
idempotente y registra `social.bootstrapped` una sola vez por tenant/canal/cuenta.

No mezcles valores parciales. Para X se requieren los cuatro campos. Para Instagram se
requieren token, account ID y username; la expiración es opcional.

## Cifrado y rotación

```dotenv
AGENCY_SOCIAL_TOKEN_ACTIVE_KEY_ID=local-social-v1
AGENCY_SOCIAL_TOKEN_ENCRYPTION_KEYS_JSON='{"local-social-v1":"<base64url-32-bytes>"}'
```

El JSON puede contener varias claves durante una rotación. El key ID activo cifra datos
nuevos y las claves anteriores permiten leer ciphertext existente hasta completar la
rotación. El AAD liga cada ciphertext a tenant, canal y tipo de registro.

Nunca elimines una clave antigua antes de re-cifrar los registros que la utilizan.

## Seguridad y roles

- Sólo `admin` puede iniciar OAuth o desconectar una cuenta.
- Inicio y disconnect requieren sesión HttpOnly y CSRF.
- El callback exige la misma sesión y consume state una sola vez.
- Viewer, operator, approver y bearer API key no pueden iniciar OAuth.
- Access tokens, refresh tokens, request-token secrets y claves AES no aparecen en API,
  auditoría, logs ni browser storage.
- Desconectar sobrescribe y elimina el ciphertext local; PostgreSQL elimina la fila.
- Errores upstream son sanitizados y no se reintentan automáticamente.

## Kubernetes y Terraform

Crea un Secret fuera de Terraform. El chart sólo referencia nombres de data keys:

```text
x-consumer-key
x-consumer-secret
instagram-app-id
instagram-app-secret
social-token-encryption-keys.json
social-token-active-key-id

# opcionales para bootstrap
x-user-access-token
x-user-access-token-secret
x-account-id
x-account-username
instagram-access-token
instagram-account-id
instagram-account-username
instagram-token-expires-at
```

Terraform recibe únicamente:

- nombre del Secret;
- nombres de las data keys;
- callback URLs;
- tenant de bootstrap opcional.

Ningún valor secreto entra al state de Terraform.

## Estado de publicación

La cuenta puede quedar conectada y visible, pero publicación permanece deshabilitada.
El siguiente límite obligatorio es una intención de publicación durable con:

- tenant, cuenta, run, artefacto/version/hash y canal;
- Greenlight y fencing token exactos;
- receipt del proveedor;
- replay sin segunda publicación;
- estado `unknown` que bloquea retry automático;
- reconciliación y revocación.

Instagram además requiere una imagen, reel o carrusel accesible por el proveedor; un
caption sin asset nunca se marca como publicable.
