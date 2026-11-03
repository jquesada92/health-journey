"""Accessible, responsive InBody progress indicator.

Rendered only from trusted, fixed labels. Progress is controlled by the actual
upload, extraction, review, validation and save events (not scroll position).
The Gradio HTML component uses `elem_id="hj-inbody-flow"` inside
a top-level Gradio Column `hj-inbody-fixedbar`. Its visibility is driven by
the selected module, not scroll state. Fixed placement is viewport-relative,
not sticky within the scrolling InBody form.
"""
from __future__ import annotations

STEPS = ("Cargar", "Extraer", "Revisar", "Validar", "Guardar")

INBODY_FLOW_CSS = """
/* The navbar belongs to the top-level Blocks tree (NOT the InBody scrolling
   panel). position:fixed anchors it to the viewport at all scroll positions.
   Gradio visibility toggles it off in Project/Training/Coach. */
#hj-panel-inbody {
    /* Reserve space so the title, upload and buttons never sit under the bar. */
    padding-top: 180px !important;
}
#hj-inbody-fixedbar {
    position: fixed !important;
    top: 0 !important;
    left: 308px;
    right: 16px;
    width: auto !important;
    min-width: 0;
    height: auto;
    max-width: none !important;
    z-index: 200;
    display: flex;
    align-items: stretch;
    padding: 8px 0 10px !important;
    margin: 0 !important;
    gap: 0 !important;
    background: var(--body-background-fill, #fff);
    box-sizing: border-box;
}
/* On browsers with CSS anchor positioning, match the content area's actual
   left/right bounds as the sidebar expands, collapses or changes width. */
@supports (left: anchor(--hj-main-content left)) {
    #hj-module-content {
        anchor-name: --hj-main-content;
    }
    #hj-inbody-fixedbar {
        left: anchor(--hj-main-content left);
        right: calc(100vw - anchor(--hj-main-content right));
    }
}
#hj-inbody-flow {
    position: relative;
    width: 100%;
    padding: 7px 10px 9px;
    border: 1px solid var(--border-color-primary, #d9e3e9);
    border-radius: 12px;
    background: var(--body-background-fill, #fff);
    box-shadow: 0 3px 12px rgba(19, 42, 49, 0.09);
}
#hj-inbody-flow .hj-flow-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 5px;
    color: var(--body-text-color, #203046);
    font-size: 12px;
}
#hj-inbody-flow .hj-flow-caption {
    font-size: 11px;
    color: var(--body-text-color-subdued, #617086);
    text-align: right;
}
#hj-inbody-flow .hj-flow-track {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    list-style: none;
    padding: 0;
    margin: 0;
}
#hj-inbody-flow .hj-flow-step {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 3px;
    min-width: 0;
    padding: 4px 0 1px;
    text-align: center;
    font-size: 11px;
    font-weight: 600;
    color: var(--body-text-color-subdued, #697887);
}
#hj-inbody-flow .hj-flow-step:not(:first-child)::before {
    content: "";
    position: absolute;
    top: 18px;
    right: calc(50% + 17px);
    width: calc(100% - 34px);
    height: 2px;
    border-radius: 999px;
    background: var(--border-color-primary, #d9e3e9);
}
#hj-inbody-flow .hj-flow-step.done::before,
#hj-inbody-flow .hj-flow-step.current::before {
    background: #159279;
}
#hj-inbody-flow .hj-flow-dot {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: 2px solid var(--border-color-primary, #d9e3e9);
    border-radius: 50%;
    background: var(--body-background-fill, #fff);
    font-size: 12px;
    font-weight: 800;
}
#hj-inbody-flow .hj-flow-step.current {
    color: var(--body-text-color, #203046);
}
#hj-inbody-flow .hj-flow-step.current .hj-flow-dot {
    border-color: #107c70;
    background: #107c70;
    color: #fff;
    box-shadow: 0 0 0 3px rgba(16, 124, 112, .17);
}
#hj-inbody-flow .hj-flow-step.done {
    color: #107c70;
}
#hj-inbody-flow .hj-flow-step.done .hj-flow-dot {
    border-color: #159279;
    background: #def4ed;
    color: #0b6758;
}
#hj-inbody-flow .hj-flow-label {
    display: block;
    white-space: nowrap;
}
@media (max-width: 700px) {
    #hj-panel-inbody {
        padding-top: 146px !important;
    }
    #hj-inbody-fixedbar {
        top: 0 !important;
        left: 8px !important;
        right: 8px !important;
        padding: 5px 0 7px !important;
    }
}
@media (max-width: 600px) {
    #hj-inbody-flow {
        padding: 6px 4px 8px;
        border-radius: 0 0 10px 10px;
    }
    #hj-inbody-flow .hj-flow-head {
        padding: 0 5px;
        margin-bottom: 3px;
        font-size: 11px;
    }
    #hj-inbody-flow .hj-flow-caption {
        font-size: 10px;
    }
    #hj-inbody-flow .hj-flow-step {
        font-size: 10px;
    }
    #hj-inbody-flow .hj-flow-dot {
        width: 25px;
        height: 25px;
        font-size: 11px;
    }
    #hj-inbody-flow .hj-flow-step:not(:first-child)::before {
        top: 16px;
        right: calc(50% + 15px);
        width: calc(100% - 30px);
    }
}
"""


def render_inbody_flow(active_step: int = 1, *, saved: bool = False) -> str:
    """Show completed steps, a single current step, and upcoming steps.

    During a successful save all five steps become completed; subsequent file
    uploads reset the progress to step 2. No user document data is displayed.
    """
    if not isinstance(active_step, int) or isinstance(active_step, bool) or not 1 <= active_step <= 5:
        raise ValueError("Invalid InBody progress step.")

    nodes = []
    for index, label in enumerate(STEPS, start=1):
        status = (
            "done" if saved or index < active_step
            else "current" if index == active_step
            else "pending"
        )
        current = ' aria-current="step"' if status == "current" else ""
        icon = "✓" if status == "done" else str(index)
        nodes.append(
            f'<li class="hj-flow-step {status}"{current}>'
            f'<span class="hj-flow-dot" aria-hidden="true">{icon}</span>'
            f'<span class="hj-flow-label">{label}</span>'
            "</li>"
        )
    caption = "Examen guardado" if saved else f"Paso {active_step} de 5"
    return (
        '<nav aria-label="Progreso del registro InBody" aria-live="polite" '
        'aria-atomic="true">'
        '<div class="hj-flow-head"><strong>Registro InBody</strong>'
        f'<span class="hj-flow-caption">{caption}</span></div>'
        '<ol class="hj-flow-track">'
        + "".join(nodes)
        + "</ol></nav>"
    )
