"""WhatsApp-inspired, responsive presentation for the Gemini fitness chat.

Only static, locally owned markup and scoped CSS. Conversational logic,
consent, authentication, persistence and Gemini model selection live elsewhere.
"""

COACH_CHAT_HEADER_HTML = """
<section class="hj-chat-header" aria-label="Cabecera del asistente fitness">
  <div class="hj-chat-avatar" aria-hidden="true">HJ</div>
  <div class="hj-chat-heading">
    <strong>Asistente fitness</strong>
    <span>Analista y entrenador virtual · Gemini</span>
  </div>
</section>
"""

COACH_CHAT_CSS = """
/* Chat-only styling: never modify the InBody Gemini selector or other tabs. */
/* Compact InBody trend panel. Charts sit left of the conversation on
   desktop and above it in a short scroll area on small touch screens. */
#hj-coach-layout {
    /* Grid, rather than Gradio Row's wrapping flexbox, keeps the chat
       alongside the charts on desktop even with wide Plotly children. */
    display: grid !important;
    grid-template-columns: minmax(260px, 320px) minmax(0, 1fr);
    align-items: start;
    gap: .75rem;
    width: 100%;
    min-width: 0;
}
#hj-coach-layout > #hj-coach-trends,
#hj-coach-layout > #hj-coach-conversation {
    width: 100% !important;
    max-width: 100% !important;
    min-width: 0 !important;
    flex: none !important;
}
#hj-coach-trends {
    grid-column: 1;
    border: 1px solid var(--border-color-primary, #d7dfda);
    border-radius: 14px;
    padding: .55rem;
    gap: .3rem;
    background: var(--background-fill-secondary, #fafcfb);
    overflow: hidden;
}
#hj-coach-trends-title { font-size: .82rem; }
#hj-coach-trends-status { font-size: .73rem; }
#hj-coach-mini-plots { gap: .16rem; min-width: 0; width: 100%; }
#hj-coach-mini-plots .plot-container { min-height: 0; min-width: 0; }
#hj-coach-mini-plots .plotly { width: 100% !important; min-width: 0; }
#hj-coach-conversation {
    grid-column: 2;
    min-width: 0;
    overflow-wrap: anywhere;
}

@media (max-width: 900px) {
    #hj-coach-layout {
        grid-template-columns: minmax(0, 1fr);
        gap: .55rem;
    }
    #hj-coach-trends,
    #hj-coach-conversation {
        grid-column: 1;
        width: 100%;
        min-width: 0;
    }
    #hj-coach-mini-plots {
        max-height: 295px;
        overflow-y: auto;
        overscroll-behavior: contain;
        scrollbar-width: thin;
    }
}

#hj-panel-coach {
    width: 100%;
    max-width: 1120px;
    margin-inline: auto;
    min-width: 0;
    gap: .6rem;
}

#hj-chat-header-host {
    border: 0;
    background: transparent;
    padding: 0;
}

#hj-chat-header-host .hj-chat-header {
    display: flex;
    align-items: center;
    gap: .8rem;
    padding: .9rem 1rem;
    border-radius: 16px 16px 8px 8px;
    color: #f7fff9;
    background: #155b4b;
    min-height: 72px;
}

#hj-chat-header-host .hj-chat-avatar {
    height: 43px;
    width: 43px;
    flex: 0 0 43px;
    display: grid;
    place-items: center;
    border-radius: 50%;
    background: #d6f3e4;
    color: #155b4b;
    font-size: .95rem;
    font-weight: 800;
}

#hj-chat-header-host .hj-chat-heading {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
}

#hj-chat-header-host .hj-chat-heading strong {
    font-size: 1.05rem;
    line-height: 1.2;
}

#hj-chat-header-host .hj-chat-heading span {
    color: #d8efe5;
    font-size: .83rem;
    line-height: 1.4;
}

#hj-coach-chatbot {
    min-width: 0;
    border: 1px solid #d5ded7;
    border-radius: 14px;
    overflow: hidden;
    background: #eeeae1;
}

/* Gradio 6 bubble layout is the source of truth for left/right alignment.
   Target only the Coach surface; safe fallbacks cover Gradio's message classes. */
#hj-coach-chatbot .message-row.user-row .message,
#hj-coach-chatbot .user-row .message,
#hj-coach-chatbot .message.user {
    background: #d9fdd3 !important;
    color: #15382b !important;
    border-radius: 16px 16px 4px 16px !important;
    max-width: min(83%, 650px);
}
#hj-coach-chatbot .message-row.bot-row .message,
#hj-coach-chatbot .bot-row .message,
#hj-coach-chatbot .message.assistant {
    background: #fff !important;
    color: #202a27 !important;
    border-radius: 16px 16px 16px 4px !important;
    max-width: min(83%, 650px);
}

#hj-chat-utilities {
    align-items: center;
    gap: .6rem;
    flex-wrap: wrap;
}
#hj-coach-data-status {
    flex: 1 1 260px;
    min-width: 0;
    color: var(--body-text-color-subdued, #53665a);
    font-size: .83rem;
}
#hj-chat-clear { flex: 0 0 auto; }

/* The composer holds both the message and its model picker, as one bubble. */
#hj-chat-composer {
    position: sticky;
    bottom: max(8px, env(safe-area-inset-bottom));
    z-index: 10;
    gap: .35rem;
    min-width: 0;
    border: 1px solid #d7dfda;
    border-radius: 18px;
    padding: .55rem .7rem;
    background: var(--body-background-fill, #fff);
    box-shadow: 0 5px 22px rgb(30 54 43 / 10%);
}
#hj-chat-composer #hj-chat-input {
    width: 100%;
    min-width: 0;
}
#hj-chat-composer #hj-chat-input textarea,
#hj-chat-composer #hj-chat-input input {
    border: 0 !important;
    box-shadow: none !important;
    border-radius: 12px !important;
    background: transparent !important;
}
#hj-chat-composer-actions {
    align-items: center;
    gap: .45rem;
    flex-wrap: nowrap;
    min-width: 0;
}
#hj-chat-composer #hj-chat-model {
    flex: 0 1 235px;
    max-width: 235px;
    min-width: 0 !important;
}
#hj-chat-composer #hj-chat-refresh-models {
    flex: 0 0 auto;
    min-width: 40px !important;
    width: 40px;
    padding-inline: .3rem;
    min-height: 40px;
}
#hj-chat-composer #hj-chat-send {
    flex: 0 0 auto;
    margin-left: auto;
    min-width: 88px;
    min-height: 42px;
    border-radius: 13px;
}

@media (max-width: 700px) {
    #hj-panel-coach {
        padding-inline: 0;
        width: 100%;
    }
    #hj-chat-header-host .hj-chat-header {
        border-radius: 12px;
        padding: .7rem .8rem;
        min-height: 62px;
    }
    #hj-coach-chatbot { border-radius: 12px; }
    #hj-chat-composer {
        padding: .4rem .5rem;
        border-radius: 14px;
        bottom: max(4px, env(safe-area-inset-bottom));
    }
    #hj-chat-composer-actions { gap: .3rem; }
    #hj-chat-composer #hj-chat-model { flex-basis: 165px; }
    #hj-chat-composer #hj-chat-send {
        min-width: 70px;
        padding-inline: .55rem;
    }
    #hj-coach-chatbot .message-row.user-row .message,
    #hj-coach-chatbot .user-row .message,
    #hj-coach-chatbot .message.user,
    #hj-coach-chatbot .message-row.bot-row .message,
    #hj-coach-chatbot .bot-row .message,
    #hj-coach-chatbot .message.assistant {
        max-width: 89%;
    }
}
"""
