"""Primary module navigation configuration for Health Journey.

Use Gradio's native collapsible Sidebar for responsive navigation and keep the
existing tab containers mounted, so form values and session consent survive
switching between sections.
"""
from __future__ import annotations

NAV_SECTIONS = (
    ("project", "Proyecto"),
    ("inbody", "Extractor de InBody"),
    ("training", "Captador de logs de entrenamiento"),
    ("coach", "Chat con el asistente fitness"),
)

SIDEBAR_CSS = """
/* Native vertical navigation only. No Gradio Tabs or overflow ellipsis. */
#hj-module-content {
    width: 100%;
    min-width: 0;
}
#hj-module-sidebar {
    width: min(284px, 90vw);
}
#hj-module-sidebar .hj-nav-button {
    width: 100%;
    margin: 0 0 6px;
    text-align: left;
    justify-content: flex-start;
    min-height: 44px;
    white-space: normal;
    overflow-wrap: anywhere;
}
#hj-module-sidebar .hj-sidebar-description {
    color: var(--body-text-color-subdued, #617086);
    font-size: 12px;
    line-height: 1.4;
}
#hj-ai-extraction {
    border: 1px solid var(--border-color-primary, #d9e3e9);
    border-radius: 14px;
    padding: 12px 14px;
    margin: 8px 0 18px;
    background: var(--body-background-fill, #fff);
}
#hj-ai-extraction .hj-ai-help {
    color: var(--body-text-color-subdued, #617086);
}
@media (max-width: 700px) {
    #hj-module-sidebar { width: min(284px, 90vw); }
    #hj-module-content { min-width: 0; }
    #hj-module-content .gr-column { min-width: 0; }
    #hj-ai-extraction { padding: 10px; }
}
"""
