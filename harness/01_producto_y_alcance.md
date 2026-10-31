# 01 — Especificación del producto y alcance

## 1. Problema

Un usuario realiza mediciones periódicas de composición corporal en clínicas, gimnasios o tiendas diferentes. Sus documentos se encuentran fragmentados, a veces solo como PDF escaneado o JPG, con dispositivos e idiomas diferentes. Necesita consolidarlos sin transcribir manualmente cada valor, comprobar errores de OCR, revisar su evolución y conservar la procedencia.

**Problema central:** 5 pruebas en un establecimiento y 6 en otro deben poder visualizarse como 11 exámenes históricos de una misma persona **cuando la identidad haya sido conciliada**, sin asumir que los modelos miden magnitudes idénticas.

## 2. Visión modular

- **Fase 1 — InBody Hub (prioridad):** ingestión, extracción estructurada, normalización, revisión humana, CSV, persistencia segura y tendencias.
- **Fase 2 — Training Hub:** bitácora de entrenamientos (ejercicio, fecha, series, repeticiones, carga, modalidad, observaciones, objetivos).
- **Fase 2 — Nutrition Hub:** fecha, comidas, macronutrientes, calorías y origen de la observación; vincular con entrenamientos sin atribuir causalidad automáticamente.
- **Fase 3 — Medical Hub:** documentos y valores clínicos con controles adicionales; no diagnosticar ni prescribir.
- **Capacidad transversal futura — Asistente:** consultas justificadas por datos confirmados, con incertidumbre, trazabilidad y supervisión.

Una única aplicación modular puede incluir todos los hubs, sin necesidad de microservicios desde el primer día.

## 3. Alcance funcional obligatorio de InBody Hub

### RF-01 — Carga segura
Admitir `.pdf`, `.jpg`, `.jpeg` y `.png`; distinguir PDF digital de PDF escaneado. Validar firma real, extensión, tamaño, páginas, número de píxeles, tipo y errores de lectura. Parámetros iniciales del código: 15 MB/archivo, hasta 8 páginas, hasta 20 megapíxeles para imagen.

### RF-02 — OCR y metadatos
Extraer texto y posición. Identificar ID como aparece en el reporte, modelo, fecha de examen y hora si existen, fecha de nacimiento o edad, e idioma `ES`/`EN`/`UNKNOWN`. **No completar campos por el nombre del archivo** si no hay evidencia verificable. Cuando la fecha no contiene hora, no asignar medianoche silenciosamente.

### RF-03 — Captura universal de mediciones
Extraer todas las métricas legibles en cada plantilla, tanto conocidas como desconocidas; preservar literal, unidad, valor, dimensión, región, lateralidad, frecuencia, página, método OCR y estado de revisión. Si no se conoce la métrica, usar clasificación pendiente sin descartar su valor.

### RF-04 — Revisión humana
Mostrar tabla editable; permitir corregir datos o descartar candidatos; exigir confirmación explícita antes de persistir en Neon. Advertir de valores faltantes, formatos dudosos, fechas no inequívocas y comparación entre equipos incompatibles.

### RF-05 — Exportación CSV independiente
Mantener **siempre** el botón de exportación a CSV, con o sin Neon. El contenido usa el contrato de **siete columnas** del documento 03; el nombre usa hash del contenido más timestamp UTC de exportación. Exportar borrador no significa confirmar ni guardar.

### RF-06 — Persistencia opcional en Neon
Tras revisión y autenticación, guardar en transacción persona/examen/mediciones, conservar idioma, equipo, origen y SHA-256 del archivo. Detectar duplicado por hash y evitar inserción parcial. No almacenar archivos originales en la tabla. Las identidades reales no deben mezclarse sin conciliación explícita.

### RF-07 — Dashboard de dos fuentes
Ofrecer **Fuente: Neon / Archivos CSV**:
- Neon: consultar exámenes autorizados y confirmados.
- CSV: seleccionar varios CSV exportados, validarlos, combinarlos y visualizar su historial sin escritura en Neon.
Ambas rutas usan el mismo modelo visual para filtrar persona, fecha, variable, modelo, unidad, segmento y frecuencia cuando esté disponible. Nunca sumar automáticamente fuentes sin un flujo de reconciliación explícito.

### RF-08 — Análisis longitudinal
Gráficas **de líneas** de peso, grasa corporal kg/%, masa muscular esquelética, masa magra segmental, grasa segmental y ángulo de fase. Permitir contraste entre grasa y masa magra/músculo en paneles o ejes correctamente etiquetados; no ocultar diferencias de definición o dispositivo. Filtrar fechas y mostrar tabla subyacente.

### RF-09 — Observabilidad y mensajes
Mostrar número de archivos, mediciones candidatas, válidas/omitidas/duplicadas, advertencias y procedencia **sin revelar datos sensibles en logs**. Los estados de conexión, autenticación y exportación deben ser claros.

### RF-10 — Recuperación
La documentación, migraciones y pruebas deben permitir reconstruir local y remotamente la app y BD desde cero, sin copiar secretos al repositorio.

## 4. Requisitos no funcionales

| Código | Criterio |
| --- | --- |
| RNF-01 | Privacidad por defecto: Space privado para datos reales; nunca publicar informes identificables. |
| RNF-02 | Autenticación y autorización verificadas por cada lectura/escritura del servidor; una variable de usuario no sustituye la sesión OAuth. |
| RNF-03 | Credenciales únicamente en Secrets/entorno; TLS con Neon; rol de aplicación de mínimo privilegio. |
| RNF-04 | Procesamiento reproducible y pruebas deterministas usando únicamente archivos sintéticos. |
| RNF-05 | Módulos Python desacoplados de la interfaz Gradio; Plotly reutilizable. |
| RNF-06 | Manejo controlado de cargas grandes, número de filas, número de CSV y consultas paginadas/limitadas. |
| RNF-07 | No confundir «dato extraído» con «dato confirmado» ni desconocidos con 0. |
| RNF-08 | UI y documentación en español; etiquetas originales ES/EN del documento conservadas. |
| RNF-09 | Nunca activar tecnologías de pago o servicios externos de IA sin aprobación. |
| RNF-10 | Evitar cambios destructivos en datos o despliegues sin aprobación y plan de reversión. |

## 5. Actores y permisos

- **Visitante/usuario sin sesión:** solo funcionalidad de prueba con datos sintéticos si el Space está configurado para ello. Nunca acceso a datos privados.
- **Usuario HF autenticado y autorizado:** OCR, revisión, guardado y consultas sobre datos que tenga permiso de ver.
- **Operador/desarrollador:** configuración y despliegue; el rol de BD de la aplicación no debe tener funciones administrativas.
- **Futuro multiusuario:** identidades verificadas por usuario propietario y autorización a nivel de fila; no confiar solo en `id_persona` ingresado en un formulario.

## 6. Fuera de alcance inmediato

Integración directa con terceros, autodiagnóstico, interpretaciones clínicas, TrOCR en producción no validado, ingesta automática de historiales gráficos impresos, captura de biometría desde el teléfono, RAG, CDC/archivado Databricks y recomendaciones médicas. Pueden formar parte del roadmap, pero no se deben describir como implementados.

## 7. Términos clave

- **Examen:** una evaluación InBody, con fecha y procedencia.
- **Medición:** magnitud cuantitativa asociada a un examen, opcionalmente a un segmento y frecuencia.
- **Candidato:** resultado del OCR aún no confirmado.
- **Confirmado:** dato revisado por una persona autorizada.
- **Modelo InBody:** equipo identificado por evidencia, **no** deducido del diseño cuando no hay certeza.
- **Idioma:** `ES`, `EN` o `UNKNOWN`; corresponde a la plantilla/etiquetas, no a la nacionalidad del paciente.
- **Fuente:** documento, exportación CSV o consulta a Neon, según la etapa.
