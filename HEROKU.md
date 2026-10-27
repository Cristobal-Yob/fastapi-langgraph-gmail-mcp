# Publicar Gmail mediante MCP STDIO desde cero

**Objetivo: Heroku Cedar con buildpacks clásicos y stack heroku-24. No se afirma compatibilidad Fir/CNB.** Las órdenes de esta guía son acciones futuras del propietario: no se ha creado ninguna app, add-on ni despliegue.

## 1. Preparar herramientas y cuentas

Necesita Python 3.12, Git, GitHub CLI, Heroku CLI y cuentas propias. Este proyecto es autónomo y debe publicarse en un repositorio GitHub **privado nuevo**, sin importar historial, entornos, `.env`, OAuth ni auth de ejemplos anteriores. Consulte [README](README.md) para entorno y pruebas.

## 2. Configurar el agente

Copie `.env.example` a `.env` solo localmente. Genere `AGENT_API_TOKEN` con `secrets.token_urlsafe(32)`. Elija Google Developer API con `GOOGLE_GENAI_USE_VERTEXAI=false` y una clave propia, o Vertex con proyecto/location y ADC configurado expresamente fuera de Git. No use variables/cuentas de otra aplicación. `MODELO` y `FALLBACK_MODEL` deben ser distintos. Las instrucciones y el fallback son los del agente fuente, sin un responder de demostración.

`PUBLIC_ORIGIN` debe ser la URL HTTPS exacta que obtenga para su app, sin slash final. La excepción de ejecución local es la API base en localhost; los controles de navegador seguros requieren HTTPS local con un proxy de confianza o un túnel **solo si usted lo autoriza**. No desactive la validación de Origin para probarlos.

## Preparación específica

El envío empieza desactivado: `EMAIL_ENABLE_REAL_SEND=false`. Antes de habilitarlo, configure PostgreSQL, `STATE_NAMESPACE` estable y una clave Fernet `STATE_ENCRYPTION_KEY` generada con `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. No cree recursos pagados automáticamente.

1. En un proyecto Google propio, habilite Gmail API y configure su pantalla OAuth y los usuarios de prueba.
2. Cree un cliente OAuth de aplicación web. Registre una URI local exacta, por ejemplo `http://localhost:8765/oauth/callback`, y use el [flujo web oficial](https://developers.google.com/identity/protocols/oauth2/web-server) localmente: `access_type=offline`, `prompt=consent`, un `state` aleatorio verificado y **solo** los scopes `openid`, `email`, `https://www.googleapis.com/auth/gmail.send`. Intercambie el código una vez y conserve el refresh token en una ubicación privada fuera del repositorio. Este servidor no expone un callback OAuth público.
Para ejecutar ese flujo sin escribir un cliente OAuth propio, descargue el JSON del cliente web en una carpeta privada fuera de este repositorio y registre exactamente `http://localhost:8765/oauth/callback`. Después ejecute localmente `python -B -m cloud.oauth_setup --client-secrets <archivo-privado-del-cliente> --output <archivo-privado-nuevo> --sender <su-correo>`. El script abre consentimiento, verifica state/PKCE, scopes, correo y sub; no envía correo ni imprime tokens. Use una carpeta privada con permisos exclusivos del usuario en Windows; no una carpeta sincronizada o compartida. Copie el JSON resultante únicamente al Config Var protegido `GMAIL_OAUTH_JSON`. No lo añada a Git.

3. Consulte userinfo con el access token para verificar `email_verified=true`, correo y `sub`. Configure `GMAIL_PROJECT_ID`, `GMAIL_CLIENT_ID`, `GMAIL_SENDER` y, como Config Var protegida, `GMAIL_OAUTH_JSON` con: `type=authorized_user`, esos tres bindings bajo `project_id`, `client_id`, `account_email`, además de `account_sub`, `client_secret`, `refresh_token`, `token_uri=https://oauth2.googleapis.com/token` y `scopes` como lista exacta de los tres scopes. No incluya access tokens, archivos OAuth o cuentas reales en Git. Los refresh tokens de aplicaciones externas en Testing suelen vencer a los siete días para Gmail.
4. Solo con autorización de envío, cambie `EMAIL_ENABLE_REAL_SEND=true`. El bearer del operador autoriza la solicitud HTTP; la gramática literal y la decisión del router todavía deben coincidir. Un ejemplo real de orden es: `Envía un correo a su-destinatario@example.com con un hola`. Use una dirección que controle y un request_id nuevo para esa acción explícita.
5. El grafo genera la respuesta antes de formatear y enviar. El transporte refresca OAuth, verifica scopes/correo/sub y hace como máximo un POST Gmail. PostgreSQL reserva antes del efecto y conserva aceptado, rechazado o incierto. No borre claims ni cambie namespace para forzar un reintento; concilie primero en el buzón. Gmail aceptado no demuestra recepción humana.

Además genere `MCP_BOUNDARY_KEY` con otro secreto aleatorio de 32 bytes. El host firma una orden expirable y arranca `python -B -m cloud.mcp_server` como **proceso STDIO** mediante el SDK MCP oficial. La herramienta verifica firma, vencimiento y una segunda reserva PostgreSQL antes de llamar Gmail. `python -B -m cloud.mcp_client` comprueba inicialización, descubrimiento de dos herramientas y salud sin OAuth ni envío. No hay servidor MCP HTTP ni fallback silencioso a envío directo en el host.

## 3. Verificar antes de publicar

```sh
python -B -m unittest discover -s tests -v
```

En WhatsApp añada `npm test`. Los tests de PostgreSQL se habilitan únicamente contra una base **sintética aislada** con `RUN_DATABASE_TESTS=true`, `DATABASE_URL` y `STATE_ENCRYPTION_KEY` de prueba. Los tests no deben tocar la cuenta/base real. El resultado omitido no equivale a una prueba de durabilidad.

## 4. Crear repositorio privado y app, con aprobación

Revise primero el contenido: solo código, tests, manifiestos y estas guías. No publique `.env`, claves, QR, sesiones, ledgers, uploads, entornos ni node_modules. Inicialice Git **dentro de esta carpeta nueva**, añada el allowlist revisado, haga un commit convencional y cree el repositorio privado mediante `gh repo create <su-organizacion>/<nombre> --private --source=. --remote=origin`. Empuje solo ese historial limpio tras su aprobación. No copie el `.git` original.

Cree explícitamente una aplicación **Cedar** en Heroku con stack `heroku-24`, no Fir. Asigne `heroku/python` como buildpack clásico. Su `Procfile` raíz ejecuta `web: python -B -m cloud.run`; no es un comando de desarrollo ni usa reload. `$PORT` lo lee el supervisor y el proceso público escucha en `0.0.0.0:$PORT`.

Complete las Config Vars desde un canal privado seguro, no desde un archivo versionado ni comandos que queden en capturas. Use la URL de la app en `PUBLIC_ORIGIN`. Las dependencias están fijadas en los manifiestos. No hay add-ons automáticos: use únicamente un PostgreSQL externo previamente autorizado cuando corresponda. Verifique TLS y acceso restringido de esa base con su proveedor.

Solo después de revisar configuración, alcance y coste, conecte la app al repositorio privado y despliegue la rama elegida, o añada el remoto Heroku y haga el push manual aprobado. Escale a **un solo dyno web** y un solo proceso del core. No habilite autoscaling, workers extra ni despliegues automáticos antes de validar seguridad y presupuesto. El filesystem del dyno es efímero; no use SQLite para estado de seguridad.

## 5. Aceptación y operación

1. Consulte `/health`: debe responder sin datos privados. Verifique que una solicitud de chat/control sin autenticación sea rechazada.
2. Pruebe primero una consulta inocua con su propio operador. El cliente debe recibir 202 y consultar estado; no mantenga una petición bloqueada más de 30 segundos.
3. Solo si está autorizado, habilite por separado correo, pairing o sesión pagada y pruebe con destinatario/cuenta propios. Registre aceptación del proveedor separada de recepción humana o reproducción audiovisual.
4. Compruebe reinicio, reservas inciertas y limpieza con datos sintéticos antes de usar un proveedor real. Un restart borra memoria conversacional; **no** borra PostgreSQL.
5. Si hay incertidumbre, detenga operaciones y concilie. No reintente envíos ni creaciones ciegamente. Copias de seguridad y rotación de claves requieren preservar la capacidad de descifrar estado existente.

## Fuentes oficiales

- [Procfile](https://devcenter.heroku.com/articles/procfile), [Python y .python-version](https://devcenter.heroku.com/articles/python-runtimes).
- [Disco efímero y SQLite](https://devcenter.heroku.com/articles/sqlite3), [timeout HTTP](https://devcenter.heroku.com/articles/request-timeout), [apagado](https://devcenter.heroku.com/articles/dyno-shutdown-behavior).
- [Chainlit archivado](https://docs.chainlit.io/get-started/project-status), [Open WebUI](https://docs.openwebui.com/getting-started/quick-start/).

La entrega de estas fuentes no demuestra build Linux, tamaño de slug, rendimiento cloud ni integración con cuentas. Esas comprobaciones requieren un despliegue y autorización separados.
