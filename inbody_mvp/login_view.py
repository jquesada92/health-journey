"""Presentation shown by Gradio's built-in password login.

Keep the login informational: authentication is still performed server-side by
`authenticate_master_demo`. Future capabilities are explicitly labelled so the
landing screen does not claim an AI coach or medical analysis already exists.

Gradio renders auth_message as HTML inside its own login panel, so styles are
inline, responsive, and scoped to this static content.
"""

LOGIN_AUTH_MESSAGE = """
<section aria-label="Bienvenida a Health Journey"
         style="box-sizing:border-box;width:100%;max-width:100%;text-align:left;
                padding:6px 0 2px;font-family:inherit;color:#203046;">
  <div style="display:inline-block;border-radius:999px;padding:6px 10px;
              font-size:11px;line-height:1.3;letter-spacing:1.1px;
              font-weight:700;background:#e8f6f2;color:#11685e;">
    HEALTH JOURNEY · TU ESPACIO PERSONAL
  </div>
  <h1 style="font-size:clamp(23px,5vw,31px);line-height:1.18;letter-spacing:-0.7px;
             margin:14px 0 10px;font-weight:800;color:#152b3c;">
    Tu asistente virtual de fitness y bienestar
  </h1>
  <p style="font-size:14px;line-height:1.65;margin:0 0 17px;color:#43536a;">
    Reúne tu información de salud y entrenamiento en un solo lugar
    para entender tu progreso y tomar decisiones acordes con tus objetivos.
  </p>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,170px),1fr));
              gap:10px;margin:0 0 14px;">
    <div style="box-sizing:border-box;min-width:0;padding:14px;border-radius:12px;
                background:#edf8f4;border:1px solid #cae7dc;">
      <div style="font-size:12px;font-weight:800;color:#11685e;margin-bottom:7px;">
        DISPONIBLE HOY
      </div>
      <div style="font-size:13px;line-height:1.5;color:#244538;">
        Registros de entrenamiento, exámenes InBody,
        historial y gráficas de progreso.
      </div>
    </div>
    <div style="box-sizing:border-box;min-width:0;padding:14px;border-radius:12px;
                background:#f5f7fb;border:1px solid #e0e6ef;">
      <div style="font-size:12px;font-weight:800;color:#4b5b74;margin-bottom:7px;">
        EN DESARROLLO
      </div>
      <div style="font-size:13px;line-height:1.5;color:#43536a;">
        Registro de dieta, exámenes médicos, integración de más fuentes
        y chat con un asistente de IA.
      </div>
    </div>
  </div>
  <p style="box-sizing:border-box;padding:13px 14px;margin:0 0 15px;
            border-left:3px solid #168d79;border-radius:0 9px 9px 0;
            font-size:13px;line-height:1.6;background:#f2f8f7;color:#28483f;">
    <strong>Hacia dónde vamos:</strong> un asistente con el que puedas conversar
    sobre tus datos, recibir sugerencias de qué cambiar y
    priorizar acciones según tus metas y necesidades.
  </p>
  <p style="font-size:12px;line-height:1.5;color:#617086;margin:0 0 2px;">
    Inicia sesión con tu cuenta autorizada para acceder a tu información.
    Las futuras recomendaciones serán orientativas y no reemplazarán
    la valoración de un profesional de salud.
  </p>
</section>
"""
