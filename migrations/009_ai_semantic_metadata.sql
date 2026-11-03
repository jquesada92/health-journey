-- migration 009 | Semantic catalog for AI coach
-- Additive, idempotent. Does not copy or update individual exam/training records.
-- Existing catalog descriptions are preserved. Private read roles only.

ALTER TABLE public.hj_measurement_catalog ADD COLUMN IF NOT EXISTS interpretation_guidance text;

ALTER TABLE public.hj_measurement_catalog ADD COLUMN IF NOT EXISTS limitations text;

CREATE TABLE IF NOT EXISTS public.hj_measurement_aliases (
 alias_normalized text PRIMARY KEY,
 canonical_code varchar NOT NULL REFERENCES public.hj_measurement_catalog(canonical_code),
 created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.hj_ai_field_dictionary (
 source_table text NOT NULL,
 field_name text NOT NULL,
 display_label_es text NOT NULL,
 description_es text NOT NULL,
 unit_hint text,
 interpretation_note text,
 exposed_to_ai boolean NOT NULL DEFAULT false,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (source_table, field_name)
);

COMMENT ON TABLE public.hj_measurement_catalog IS 'Catálogo privado de conceptos InBody, definiciones, unidades de referencia y límites interpretativos. No contiene datos de personas.';

COMMENT ON TABLE public.hj_measurement_aliases IS 'Variantes normalizadas de etiquetas InBody que apuntan al concepto canónico. No inferir equivalencia si no existe alias.';

COMMENT ON TABLE public.hj_ai_field_dictionary IS 'Diccionario técnico y semántico de columnas permitidas en el contexto del coach. Solo descripciones, nunca filas personales.';

COMMENT ON TABLE public.hj_measurement_audits IS 'Auditoría inmutable de la extracción InBody: lecturas originales y valores finales revisados. Datos privados.';

COMMENT ON VIEW public.hj_audit_reviewed_private IS 'Vista privada de resultados InBody revisados. No publicarla ni conceder lectura a invitados o writer demo.';

COMMENT ON TABLE public.hj_measurements IS 'Mediciones de exámenes InBody confirmados, una fila por variable y segmento. Mantener unidad y precisión.';

COMMENT ON TABLE public.hj_training_sets IS 'FitNotes guardado a nivel de serie, segregado por owner_key autenticado. No hay RIR, RPE ni técnica medidos.';

COMMENT ON TABLE public.hj_training_imports IS 'Lotes FitNotes importados con huella de origen, conteos y propietario privado.';

COMMENT ON COLUMN public.hj_measurement_audits.original_value IS 'Valor candidato extraído antes de la revisión humana, texto de procedencia inmutable.';

COMMENT ON COLUMN public.hj_measurement_audits.final_value IS 'Valor definitivo revisado por humano. Puede preservar decimales como 8.20 o signo negativo.';

COMMENT ON COLUMN public.hj_measurement_audits.final_unit IS 'Unidad definitiva de la medición revisada, no convertir ni inferir si falta.';

COMMENT ON COLUMN public.hj_measurement_audits.was_corrected IS 'Diferencia entre extracción candidata y valor final, no significa anomalía médica.';

COMMENT ON COLUMN public.hj_audit_reviewed_private.value IS 'Valor final validado, no el valor bruto OCR.';

COMMENT ON COLUMN public.hj_audit_reviewed_private.unit IS 'Unidad específica del resultado, imprescindible para comparaciones.';

COMMENT ON COLUMN public.hj_audit_reviewed_private.anonymous_id IS 'Identificador interno seudónimo. NUNCA enviar a Gemini.';

COMMENT ON COLUMN public.hj_measurements.segmento IS 'Región anatómica medida, debe coincidir para comparar.';

COMMENT ON COLUMN public.hj_measurements.frecuencia_khz IS 'Frecuencia eléctrica del método de impedancia, no un resultado corporal independiente.';

COMMENT ON COLUMN public.hj_training_sets.owner_key IS 'Clave privada de aislamiento por sesión autorizada. NUNCA enviar a Gemini.';

COMMENT ON COLUMN public.hj_training_sets.weight IS 'Carga externa de la serie, no peso corporal. Puede ser negativa según ejercicio asistido.';

COMMENT ON COLUMN public.hj_training_sets.weight_unit IS 'Unidad de la carga externa, por ejemplo kg o lb.';

COMMENT ON COLUMN public.hj_training_sets.reps IS 'Repeticiones registradas, no esfuerzo ni repeticiones en reserva.';

COMMENT ON COLUMN public.hj_training_sets.duration_seconds IS 'Duración de ejercicio anotada en segundos, no descanso inferido.';

COMMENT ON COLUMN public.hj_training_sets.category IS 'Clasificación FitNotes elegida por el usuario, no evidencia de activación muscular.';

COMMENT ON COLUMN public.hj_measurement_catalog.interpretation_guidance IS 'Guía interpretativa descriptiva para la IA, sin poder diagnóstico.';

COMMENT ON COLUMN public.hj_measurement_catalog.limitations IS 'Limitaciones de la métrica InBody y advertencias contra inferencia clínica.';

INSERT INTO public.hj_measurement_catalog (canonical_code, display_label_es, display_label_en, categoria, dimension, canonical_unit, comparability_rule, descripcion_medida, interpretation_guidance, limitations)
VALUES
  ('body_weight', 'Peso corporal', 'Body Weight', 'composición corporal', 'masa', 'kg', 'Comparar fecha, unidad, condiciones de medición y preferentemente mismo equipo.', 'Masa corporal total estimada por la báscula del InBody.', 'Variación del peso refleja grasa, músculo, agua y otros componentes, nunca identifica por sí sola qué tejido cambió.', 'Hidratación y momento de medición pueden alterar el resultado.'),
  ('skeletal_muscle_mass', 'Masa muscular esquelética', 'Skeletal Muscle Mass', 'composición corporal', 'masa', 'kg', 'Misma variable, unidad y modelo de equipo, evitar conclusiones por una sola medición.', 'Estimación de masa muscular esquelética obtenida mediante bioimpedancia.', 'Usar tendencias de varias fechas para complementar la evolución del entrenamiento.', 'No equivale a fuerza, hipertrofia real ni diagnóstico clínico.'),
  ('body_fat_mass', 'Masa grasa', 'Body Fat Mass', 'composición corporal', 'masa', 'kg', 'Misma variable, unidad, método y equipo.', 'Estimación de masa grasa corporal.', 'Interpretar con porcentaje de grasa y peso, sin sumar el porcentaje a los kilogramos.', 'Sensible a las condiciones de bioimpedancia.'),
  ('percent_body_fat', 'Porcentaje de grasa corporal', 'Percent Body Fat', 'composición corporal', 'proporción', '%', 'Mismo equipo y metodología, no comparar con masa grasa expresada en kg.', 'Porcentaje estimado de la masa corporal compuesto por grasa.', 'Interpretar junto con masa grasa y peso corporal.', 'No inferir adiposidad visceral ni riesgo clínico sin contexto.'),
  ('fat_free_mass', 'Masa libre de grasa', 'Fat Free Mass', 'composición corporal', 'masa', 'kg', 'Comparar mismo equipo y condiciones.', 'Masa corporal excluyendo la grasa estimada, incluye agua y otros tejidos.', 'No sustituye la masa muscular esquelética.', 'Cambios de agua modifican la estimación.'),
  ('soft_lean_mass', 'Masa magra blanda', 'Soft Lean Mass', 'composición corporal', 'masa', 'kg', 'Mismo equipo, unidad y región cuando aplique.', 'Masa magra de tejidos blandos estimada por InBody.', 'Distinguir de masa libre de grasa y masa muscular esquelética.', 'Dependiente del estado hídrico.'),
  ('segmental_lean_mass', 'Masa magra segmental', 'Segmental Lean Mass', 'segmental', 'masa', 'kg', 'Comparar el mismo segmento anatómico, unidad y equipo.', 'Estimación de masa magra de brazo, pierna o tronco.', 'Usar diferencias por segmento de forma descriptiva.', 'No es una medida directa de fuerza, hipertrofia ni simetría funcional.'),
  ('total_body_water', 'Agua corporal total', 'Total Body Water', 'agua corporal', 'volumen', 'L', 'Misma unidad, modelo y condiciones de hidratación.', 'Estimación del agua total del organismo.', 'Contextualiza cambios simultáneos de masa magra y peso.', 'Las variaciones agudas pueden deberse a hidratación, ejercicio o ingesta.'),
  ('intracellular_water', 'Agua intracelular', 'Intracellular Water', 'agua corporal', 'volumen', 'L', 'Comparar mismo segmento, equipo y unidad.', 'Agua estimada en el compartimento intracelular.', 'Describir su tendencia sin inferir salud celular individual.', 'No utilizar como diagnóstico de enfermedad o recuperación.'),
  ('extracellular_water', 'Agua extracelular', 'Extracellular Water', 'agua corporal', 'volumen', 'L', 'Comparar mismo segmento y equipo.', 'Agua estimada en el compartimento extracelular.', 'Contrastar cuidadosamente con agua total y relación ECW/TBW.', 'No diagnosticar edema a partir de una cifra aislada.'),
  ('ecw_ratio', 'Relación agua extracelular', 'ECW Ratio', 'agua corporal', 'proporción', NULL, 'Comparar proporción con la misma unidad y segmento, no convertir automáticamente entre % y razón.', 'Proporción de agua extracelular respecto al agua total estimada.', 'Indicar si el reporte usa razón decimal o porcentaje y conservar la unidad original.', 'No diagnosticar retención de líquidos sin evaluación clínica.'),
  ('phase_angle', 'Ángulo de fase', 'Phase Angle', 'bioimpedancia', 'ángulo', '°', 'Comparar igual segmento, frecuencia y modelo de equipo.', 'Ángulo calculado a partir de resistencia y reactancia bioeléctricas.', 'Puede describir cambios en propiedades eléctricas relacionadas con membranas celulares.', 'No interpretar como medición directa de calidad celular, inflamación o diagnóstico.'),
  ('impedance', 'Impedancia eléctrica', 'Impedance', 'bioimpedancia', 'resistencia', 'Ω', 'Comparar solo a igual frecuencia en kHz, segmento y equipo.', 'Oposición de tejidos al paso de corriente alterna medida en ohmios.', 'Debe conservarse la frecuencia y el segmento, no mezclar 20 kHz y 100 kHz.', 'No es masa muscular ni una medición clínica independiente.'),
  ('measurement_frequency', 'Frecuencia de medición', 'Frequency', 'bioimpedancia', 'frecuencia', 'kHz', 'Es configuración de la medición, no resultado fisiológico.', 'Frecuencia eléctrica usada para obtener medidas de bioimpedancia.', 'Usarla como metadato de comparabilidad para impedancia y ángulo de fase.', 'Nunca interpretar subir o bajar la frecuencia como progreso físico.'),
  ('body_mass_index', 'Índice de masa corporal', 'Body Mass Index', 'antropometría', 'índice', 'kg/m²', 'Requiere peso y estatura, comparación descriptiva.', 'Relación entre masa y estatura al cuadrado.', 'Usar junto a composición corporal, no equiparar IMC alto con exceso de grasa.', 'Puede clasificar erróneamente personas musculadas.'),
  ('basal_metabolic_rate', 'Tasa metabólica basal', 'Basal Metabolic Rate', 'metabolismo', 'energía', 'kcal/día', 'Comparar estimaciones calculadas con modelos compatibles.', 'Gasto energético basal estimado por el dispositivo.', 'No confundir con calorías diarias totales ni calorías realmente consumidas.', 'No es medición directa de gasto energético ni una prescripción.'),
  ('inbody_score', 'Puntaje InBody', 'InBody Score', 'puntuación', 'índice', 'puntos', 'Usar solo si el mismo modelo emplea una escala comparable.', 'Puntuación compuesta calculada mediante algoritmo del fabricante.', 'Mostrar su tendencia como indicador del reporte, no como diagnóstico.', 'La fórmula puede ser propietaria y variar entre modelos.'),
  ('bone_mineral_content', 'Contenido mineral óseo', 'Bone Mineral Content', 'composición corporal', 'masa', 'kg', 'Comparar mismas unidades, algoritmo y equipo.', 'Estimación de contenido mineral asociado al componente óseo.', 'Describir sin inferir densidad mineral ósea.', 'No reemplaza una densitometría DEXA ni evalúa osteoporosis.'),
  ('protein_mass', 'Proteínas corporales estimadas', 'Protein', 'composición corporal', 'masa', 'kg', 'Comparar modelo y unidad.', 'Estimación del componente proteico en la composición corporal del reporte.', 'No equivale a gramos de proteína ingeridos.', 'No es biomarcador sanguíneo ni diagnóstico de estado proteico.'),
  ('minerals', 'Minerales estimados', 'Minerals', 'composición corporal', 'masa', 'kg', 'Comparar mismo modelo y unidad.', 'Estimación agregada de minerales del reporte.', 'Interpretar como componente de la composición corporal.', 'No equivale a análisis de minerales en sangre.'),
  ('ffmi', 'Índice de masa libre de grasa', 'Fat-Free Mass Index', 'composición corporal', 'índice', 'kg/m²', 'Misma definición de masa libre de grasa y estatura.', 'Masa libre de grasa normalizada por la estatura al cuadrado.', 'Comparar tendencias si el método no cambia.', 'No equiparar directamente con masa muscular.'),
  ('segmental_reference_percent', 'Porcentaje de referencia segmental', 'Percent of Reference', 'segmental', 'proporción', '%', 'Comparar misma región, fórmula y equipo.', 'Valor relativo a una referencia segmental del fabricante.', 'Interpretar respecto a la referencia usada por el equipo.', 'No confundir con porcentaje de grasa.'),
  ('target_weight', 'Peso objetivo sugerido', 'Target Weight', 'recomendación del equipo', 'masa', 'kg', 'No equivale a una meta del usuario ni a indicación clínica.', 'Peso objetivo calculado o sugerido por el algoritmo InBody.', 'Presentar como sugerencia del dispositivo, no como prescripción.', 'No derivar un plan alimentario automático de este valor.'),
  ('fat_control', 'Control de grasa sugerido', 'Fat Control', 'recomendación del equipo', 'masa', 'kg', 'Cambios estimados sugeridos, no valores observados.', 'Diferencia de grasa recomendada por el dispositivo.', 'Distinguir metas de medidas reales y respetar signo.', 'No usar como indicación obligatoria ni prescripción.'),
  ('muscle_control', 'Control muscular sugerido', 'Muscle Control', 'recomendación del equipo', 'masa', 'kg', 'Cambios sugeridos, no masa muscular observada.', 'Cambio de músculo recomendado por el dispositivo.', 'No confundir con progresión real.', 'No supone que la ganancia propuesta sea fisiológicamente alcanzable.'),
  ('recommended_caloric_intake', 'Ingesta calórica sugerida', 'Recommended Caloric Intake', 'recomendación del equipo', 'energía', 'kcal/día', 'Solo recomendación calculada por dispositivo.', 'Calorías diarias sugeridas por el reporte.', 'Diferenciar de calorías ingeridas o gasto medido.', 'No es un plan clínico ni un ajuste dietético personalizado.'),
  ('degree_of_obesity', 'Grado de obesidad del equipo', 'Degree of Obesity', 'antropometría', 'índice', '%', 'Definición y referencia pueden depender del fabricante.', 'Índice del dispositivo relacionado con peso relativo a referencia.', 'No equiparar directamente con grasa corporal.', 'No usar para diagnosticar obesidad.')
ON CONFLICT (canonical_code) DO UPDATE
SET interpretation_guidance = COALESCE(NULLIF(public.hj_measurement_catalog.interpretation_guidance, ''), EXCLUDED.interpretation_guidance),
    limitations = COALESCE(NULLIF(public.hj_measurement_catalog.limitations, ''), EXCLUDED.limitations);

INSERT INTO public.hj_measurement_aliases (alias_normalized, canonical_code)
VALUES
  ('weight', 'body_weight'),
  ('body weight', 'body_weight'),
  ('skeletal muscle mass', 'skeletal_muscle_mass'),
  ('body fat mass', 'body_fat_mass'),
  ('fat mass', 'body_fat_mass'),
  ('body fat percentage', 'percent_body_fat'),
  ('percent body fat', 'percent_body_fat'),
  ('percentage of body fat', 'percent_body_fat'),
  ('fat free mass', 'fat_free_mass'),
  ('fat-free mass', 'fat_free_mass'),
  ('soft lean mass', 'soft_lean_mass'),
  ('lean mass', 'segmental_lean_mass'),
  ('total body water', 'total_body_water'),
  ('intracellular water', 'intracellular_water'),
  ('inracellular water', 'intracellular_water'),
  ('extracellular water', 'extracellular_water'),
  ('ecw', 'extracellular_water'),
  ('ecw ratio', 'ecw_ratio'),
  ('ecw/tbw', 'ecw_ratio'),
  ('phase angle', 'phase_angle'),
  ('angulo de fase', 'phase_angle'),
  ('impedance', 'impedance'),
  ('frequency', 'measurement_frequency'),
  ('body mass index', 'body_mass_index'),
  ('bmi', 'body_mass_index'),
  ('basal metabolic rate', 'basal_metabolic_rate'),
  ('inbody score', 'inbody_score'),
  ('bone mineral content', 'bone_mineral_content'),
  ('protein', 'protein_mass'),
  ('minerals', 'minerals'),
  ('ffmi', 'ffmi'),
  ('percent of reference', 'segmental_reference_percent'),
  ('target weight', 'target_weight'),
  ('fat control', 'fat_control'),
  ('muscle control', 'muscle_control'),
  ('recommended caloric intake', 'recommended_caloric_intake'),
  ('recommended calorie intake', 'recommended_caloric_intake'),
  ('degree of obesity', 'degree_of_obesity'),
  ('obesity degree', 'degree_of_obesity')
ON CONFLICT (alias_normalized) DO NOTHING;

INSERT INTO public.hj_ai_field_dictionary (source_table, field_name, display_label_es, description_es, unit_hint, interpretation_note, exposed_to_ai)
VALUES
  ('hj_audit_reviewed_private', 'exam_date', 'Fecha del examen', 'Fecha calendario del InBody revisado', NULL, 'No inventar hora si la vista solo trae fecha', true),
  ('hj_audit_reviewed_private', 'section', 'Sección InBody', 'Sección del reporte original', NULL, 'Ayuda a distinguir variables homónimas', true),
  ('hj_audit_reviewed_private', 'measurement', 'Variable medida', 'Etiqueta de la variable del InBody', NULL, 'Cruzar con el catálogo solo si hay alias reconocido', true),
  ('hj_audit_reviewed_private', 'value', 'Valor validado', 'Resultado final después de la revisión humana', 'unidad de la fila', 'No sustituir por original_value ni inferir valor faltante', true),
  ('hj_audit_reviewed_private', 'unit', 'Unidad de medida', 'Unidad explícita del reporte', NULL, 'No sumar unidades distintas', true),
  ('hj_audit_reviewed_private', 'was_corrected', 'Corrección humana', 'Indica si el valor fue cambiado respecto de la extracción candidata', 'booleano', 'Un cambio no implica que la medición sea fisiológicamente anómala', true),
  ('hj_measurements', 'variable_medida', 'Variable del examen confirmado', 'Nombre canónico o etiqueta del resultado', NULL, 'No tiene por qué estar en el catálogo semántico', true),
  ('hj_measurements', 'valor_medida', 'Valor confirmado', 'Número validado del examen', 'unidad_medida', 'Conservar precisión y signo', true),
  ('hj_measurements', 'segmento', 'Segmento anatómico', 'Brazo, pierna, tronco u otra región', NULL, 'Comparar el mismo segmento', true),
  ('hj_measurements', 'unidad_medida', 'Unidad InBody', 'Unidad guardada de cada variable', NULL, 'No asumir unidad si está vacía', true),
  ('hj_training_sets', 'workout_date', 'Fecha de entrenamiento', 'Fecha de la sesión registrada en FitNotes', 'fecha', 'No indica duración ni recuperación', true),
  ('hj_training_sets', 'exercise', 'Ejercicio', 'Nombre del ejercicio tal como se registró en FitNotes', NULL, 'Las variantes no son intercambiables', true),
  ('hj_training_sets', 'category', 'Categoría FitNotes', 'Grupo o categoría del usuario para ese ejercicio', NULL, 'No demuestra cuáles músculos fueron reclutados', true),
  ('hj_training_sets', 'set_number', 'Número de serie', 'Orden de la serie dentro del ejercicio y día', NULL, 'No es número de series semanales', true),
  ('hj_training_sets', 'weight', 'Carga reportada', 'Carga externa anotada para la serie', 'weight_unit', 'No confundir con peso corporal, y los negativos pueden representar asistencia', true),
  ('hj_training_sets', 'weight_unit', 'Unidad de carga', 'Unidad de la carga del ejercicio', NULL, 'No mezclar kg y lb ni asumir conversiones', true),
  ('hj_training_sets', 'reps', 'Repeticiones', 'Número de repeticiones registradas', 'repeticiones', 'No implica proximidad al fallo ni RIR', true),
  ('hj_training_sets', 'distance', 'Distancia', 'Distancia reportada en un ejercicio', 'distance_unit', 'No calcular velocidad sin duración', true),
  ('hj_training_sets', 'distance_unit', 'Unidad de distancia', 'Unidad usada por FitNotes para distancia', NULL, 'No mezclar km, m y millas', true),
  ('hj_training_sets', 'duration_seconds', 'Duración', 'Segundos registrados para esa serie o actividad', 'segundos', 'No siempre representa descanso entre series', true),
  ('hj_measurement_catalog', 'canonical_code', 'Código de variable', 'Identificador lógico del concepto medido', NULL, 'No es identificador de persona', true),
  ('hj_measurement_catalog', 'comparability_rule', 'Regla de comparabilidad', 'Condiciones mínimas para comparar mediciones', NULL, 'Priorizar antes de calcular cambios', true),
  ('hj_measurement_catalog', 'descripcion_medida', 'Definición', 'Significado descriptivo de la variable InBody', NULL, 'No es interpretación clínica', true),
  ('hj_measurement_catalog', 'limitations', 'Limitaciones', 'Advertencias de uso de esa métrica', NULL, 'No diagnosticar a partir de un valor aislado', true)
ON CONFLICT (source_table, field_name) DO NOTHING;

REVOKE ALL ON public.hj_measurement_aliases, public.hj_ai_field_dictionary FROM PUBLIC;

GRANT SELECT ON public.hj_measurement_aliases, public.hj_ai_field_dictionary TO health_journey_app, health_journey_runtime;
