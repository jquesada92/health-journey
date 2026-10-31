# Despliegue de Health Journey en Hugging Face Spaces

**Repositorio fuente:** [jquesada92/health-journey](https://github.com/jquesada92/health-journey)  
**Space de QA:** [jaqo/health-journey](https://huggingface.co/spaces/jaqo/health-journey)

> **Situación actual:** el Space utiliza `sdk: gradio` con `app.py`, EasyOCR y el módulo `inbody_mvp/`. El dashboard histórico con Plotly está planificado, no implementado.

## 1. Cómo funciona la publicación automática (ya implementada)

Existe el workflow [`.github/workflows/deploy-huggingface.yml`](../.github/workflows/deploy-huggingface.yml), llamado **Sync app to Hugging Face**.

- Se ejecuta al hacer **push a `main`** cuando cambian `app.py`, archivos de `inbody_mvp/`, `README.md`, `requirements.txt` o el propio workflow.
- También se puede iniciar manualmente desde **GitHub → Actions → Sync app to Hugging Face → Run workflow**.
- Envía al Space **`app.py`, `README.md`, `requirements.txt` y los archivos Python de `inbody_mvp/`** mediante `huggingface_hub.HfApi.upload_folder`.
- Una actualización del código en el repositorio del Space inicia automáticamente su reconstrucción/reinicio en Hugging Face.
- Cambios solo en pruebas o documentación fuera del README no activan el despliegue. El directorio `inbody_mvp/` sí está incluido.

### Configuración inicial en GitHub (una sola vez)

1. Genera un **User Access Token** de Hugging Face con permisos **write** para el Space desde [Settings → Access Tokens](https://huggingface.co/settings/tokens). Utiliza un token de permisos mínimos.
2. En GitHub, abre **Settings → Secrets and variables → Actions** del repositorio.
3. En **Secrets**, crea `HF_TOKEN` con el valor del token. **No publiques el token en código, logs o documentos**.
4. En **Variables**, crea `HF_SPACE_ID` con el valor exacto `jaqo/health-journey`.
5. Comprueba que GitHub Actions tenga permiso para ejecutarse en el repositorio.

No se ha comprobado desde esta guía que estas credenciales ya estén configuradas.

### Desplegar después de editar

```bash
git checkout main
git pull origin main
# Edita app.py, inbody_mvp/, README.md o requirements.txt
git add app.py inbody_mvp README.md requirements.txt
git commit -m "Update Gradio InBody Hub"
git push origin main
```

GitHub Actions ejecutará el workflow **si cambió alguno de esos archivos**. El workflow publica únicamente el conjunto permitido; no sube los PDFs o archivos de prueba del equipo local.

### Verificar el despliegue

1. Abre [GitHub Actions del repositorio](https://github.com/jquesada92/health-journey/actions).
2. Selecciona **Sync app to Hugging Face** y comprueba que el job `sync` termine correctamente.
3. Abre [el Space](https://huggingface.co/spaces/jaqo/health-journey) y revisa **Build logs / Container logs** para confirmar que inicia.
4. Comprueba la pestaña **App** e intenta el flujo de OCR con un archivo de prueba anonimizado.

Un workflow exitoso solo confirma que los archivos se subieron; no garantiza que la aplicación haya arrancado sin errores.

## 2. Lanzar manualmente el workflow existente (sin nuevo commit)

Ve a [Actions](https://github.com/jquesada92/health-journey/actions) → **Sync app to Hugging Face** → **Run workflow** → selecciona `main` → **Run workflow**. Esto vuelve a publicar los archivos de la aplicación Gradio y el paquete de extracción.

## 3. Subir manualmente desde tu computadora (alternativa)

Instala el cliente y autentícate en tu máquina:

```bash
python -m pip install --upgrade huggingface_hub
hf auth login
```

Desde la raíz de una copia actualizada del repositorio:

```bash
git pull origin main
hf upload jaqo/health-journey . . --repo-type space \
  --include "app.py" \
  --include "README.md" \
  --include "requirements.txt" \
  --include "inbody_mvp/**"
```

Esto publica los archivos de Gradio y el paquete de extracción, igual que el workflow y evita subir carpetas locales, reportes InBody, `.env` y archivos de desarrollo. No uses `hf upload ... . .` sin filtros sobre un directorio que pueda contener información privada.

Si solamente quieres **reiniciar** el código ya publicado, sin subir cambios:

```bash
hf spaces restart jaqo/health-journey
```

Si necesitas limpiar la caché de construcción:

```bash
hf spaces restart jaqo/health-journey --factory-reboot
```

**Reiniciar no sincroniza GitHub**: el Space ejecuta el código que ya tiene alojado.

## 4. Próxima fase: dashboard con Gradio + Plotly

No es necesario cambiar el SDK a Docker ni incorporar Dash. Se reutilizará el mismo `app.py`, agregando una pestaña con `gr.Plot` y figuras Plotly. Las gráficas históricas requerirán primero almacenamiento seguro, revisión/confirmación de mediciones y consultas de series temporales; por ahora la pestaña Dashboard solo explica el plan.

Para futuras dependencias o cambios de módulos, actualizar `requirements.txt` y, si se agrega un módulo de aplicación obligatorio, ajustar la lista explícita de archivos del workflow. Los datos personales de salud no deben publicarse en el repositorio ni cargarse en un Space público sin controles de acceso.


## 5. Solución de problemas

| Síntoma | Qué revisar |
| --- | --- |
| El push no inició Actions | ¿Cambió un archivo de la lista `paths` en `main`? Si no, usa **Run workflow**. |
| Falta `HF_TOKEN` o `HF_SPACE_ID` | Configura el secret y la variable en GitHub; comprueba que el token pueda escribir en el Space. |
| Actions pasa, pero la app falla | Revisa los logs de construcción/ejecución del Space y las dependencias en `requirements.txt`. |
| El extractor no aparece en el Space | Verifica que la sincronización incluya `inbody_mvp/` y revisa los logs de construcción. |
| Los cambios en GitHub no aparecen | Confirma que el workflow terminó y que Hugging Face reconstruyó el commit subido. |
| El reinicio borró archivos cargados | El filesystem del Space es efímero. Nunca lo uses como almacenamiento durable para datos personales. |

**Referencias oficiales:** [Hugging Face CLI](https://huggingface.co/docs/huggingface_hub/guides/cli) · [Spaces + GitHub Actions](https://huggingface.co/docs/hub/spaces-github-actions) · [Administración de Spaces](https://huggingface.co/docs/huggingface_hub/guides/manage-spaces).
