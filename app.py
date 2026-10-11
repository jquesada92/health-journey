from pathlib import Path

import os

import spaces  # Importar antes de torch para ZeroGPU.
import torch
import easyocr
import gradio as gr
import numpy as np

README_PATH = Path(__file__).resolve().with_name("README.md")


def read_readme() -> str:
    if not README_PATH.is_file():
        return "# Health Journey\n\nREADME.md no está disponible."
    text = README_PATH.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    if lines and lines[0].strip() == "---":
        for index, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                return "".join(lines[index + 1:]).lstrip()
    return text



# En Spaces, los modelos se cargan en CUDA antes de solicitar GPU.
# En local sin CUDA, EasyOCR funciona en CPU.
DEVICE = "cuda" if os.environ.get("SPACE_ID") or torch.cuda.is_available() else "cpu"
reader = easyocr.Reader(["es", "en"], gpu=DEVICE, verbose=False)


@spaces.GPU
def extract_text(image) -> str:
    if image is None:
        raise gr.Error("Carga una imagen del reporte.")
    if image.width * image.height > 20_000_000:
        raise gr.Error("La imagen es demasiado grande; usa un recorte o una imagen menor.")
    results = reader.readtext(
        np.asarray(image.convert("RGB")), detail=0, paragraph=False
    )
    return "\n".join(results) if results else "No se detectó texto. Prueba una imagen más nítida."


def validate_image(image):
    if image is None:
        raise gr.Error("Carga una imagen del reporte.")
    if image.width * image.height > 20_000_000:
        raise gr.Error("La imagen es demasiado grande; usa un recorte o una imagen menor.")


with gr.Blocks(
    title="Health Journey", analytics_enabled=False, delete_cache=(60, 60)
) as demo:
    with gr.Tab("InBody Hub"):
        gr.Markdown(
            "# InBody Hub · QA\n"
            "Carga una imagen de prueba o anonimizada. Revisa el texto extraído: "
            "todavía no se convierte en mediciones ni se guarda en una base de datos. "
            "Los archivos temporales se limpian periódicamente."
        )
        image = gr.Image(type="pil", sources=["upload"], label="Reporte InBody (imagen)")
        button = gr.Button("Extraer texto")
        output = gr.Textbox(label="Texto para revisión", lines=20, interactive=True)
        button.click(validate_image, inputs=image, outputs=None).success(
            extract_text, inputs=image, outputs=output, concurrency_limit=1
        )
        gr.ClearButton([image, output], value="Limpiar")
    with gr.Tab("Proyecto"):
        gr.Markdown(value=read_readme)


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False, ssr_mode=False)
