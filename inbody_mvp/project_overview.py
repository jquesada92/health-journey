"""Human-friendly project landing page; no private health data or README dump."""
PROJECT_OVERVIEW = """# Health Journey
### Tu información, tu progreso, mejores decisiones

**Health Journey** nace de un problema común: las mediciones de composición corporal
y los registros del gimnasio suelen vivir en aplicaciones, archivos y reportes
separados. Sin un historial comparable es difícil saber qué está cambiando,
cómo evoluciona tu rendimiento o si tus entrenamientos se acercan a tus objetivos.

Nuestra motivación es convertir esa información dispersa en **conocimiento útil y
personal**, manteniendo la posibilidad de revisar, corregir y controlar los datos.

### ¿Para qué sirve esta aplicación?

- **Extractor de InBody:** importa PDF e imágenes de diferentes equipos; utiliza
  Gemini para reconocer mediciones, que tú verificas antes de guardar.
- **Captador de logs de entrenamiento:** recibe exportaciones CSV de FitNotes,
  preserva cada serie y evita duplicados al guardar en tu cuenta privada.
- **Chat con el asistente fitness:** cruza las mediciones revisadas de InBody y
  los entrenamientos que tengas registrados; analiza tendencias y ofrece
  recomendaciones en función de los objetivos y restricciones que tú indiques.
  El chat no sustituye una valoración clínica.
- **Gráficas de progreso:** las visualizaciones de composición corporal
  se consultan desde el módulo de InBody, sin duplicar la navegación.

### Arquitectura y flujo de datos

```text
Reportes InBody PDF/JPG/PNG ----> Extracción Gemini ----> Revisión humana
                                                          |
FitNotes CSV -------------------> Validación y deduplicación
                                                          |
                                                   Neon PostgreSQL
                                                          |
                                     Consultas privadas y agregaciones Python
                                                          |
                                   Chat Gemini (con consentimiento independiente)
                                                          |
                                        Recomendaciones y seguimiento personal
```

### Componentes tecnológicos

| Componente | Tecnología y propósito |
| --- | --- |
| Interfaz y navegación | **Gradio 6** y CSS responsive: un único Space adaptado a móvil y escritorio |
| Hosting | **Hugging Face Spaces**: ejecuta la aplicación; conserva compatibilidad de arranque con **ZeroGPU**, pero la extracción y el chat Gemini usan API |
| Backend | **Python**: valida archivos, calcula tendencias y orquesta consultas y llamadas a IA |
| Modelos de IA | **Google Gemini Flash**, vía `google-genai`: extrae InBody e interpreta resúmenes agregados para el asistente; modelos y cuotas dependen de la clave y la cuenta |
| Base de datos | **Neon PostgreSQL**: exámenes y auditorías InBody, catálogos de medidas, cargas y series FitNotes |
| Acceso a datos | **SQLAlchemy + psycopg**: operaciones parametrizadas, permisos privados y transacciones |
| Validación y análisis | **Pydantic**, **Pandas**, **Decimal** y **Plotly**: control de campos, precisión numérica, series temporales y gráficas |
| Documentos | **PyMuPDF** y **Pillow**: lectura y preparación de reportes para la extracción |
| Seguridad | Consentimientos independientes, autenticación de la aplicación u OAuth de Hugging Face, accesos mínimos y secretos del servidor |
| Desarrollo | **GitHub**, pruebas automatizadas y despliegue controlado mediante GitHub Actions |

### Principios de Health Journey

**Privacidad por diseño.** Los archivos InBody originales no se envían al chat de
fitness. El envío de resúmenes de datos personales a Gemini exige una autorización
diferente de la extracción y del almacenamiento. No se publica información
privada al guardarla.

**Datos verificables.** Se usan fechas, valores y unidades reales; se conserva
la precisión decimal, no se inventan mediciones y no se comparan directamente
resultados incompatibles entre equipos, segmentos o unidades.

**Asistente, no diagnóstico.** La IA es una herramienta de análisis deportivo
y educación. Las recomendaciones requieren contexto y no sustituyen a médicos,
fisioterapeutas ni entrenadores cualificados.

**Evolución incremental.** Las funciones se construyen con validación y pruebas;
una función descrita en esta página puede depender de la configuración del
servidor, permisos o disponibilidad de datos.
"""
