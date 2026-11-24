"""Interfaz Streamlit del chatbot Uma Musume.

Presenta mensajes, métricas y contexto recibido desde FastAPI.
Conserva un session_id por sesión de Streamlit y permite reiniciar el chat.
Requiere que el backend esté ejecutándose en el puerto indicado por API_URL.
Archivo aportado por el equipo de frontend; integrado sin modificar su lógica.
"""

import base64
import html
import io

import requests
import streamlit as st
from PIL import Image

API_URL = "http://127.0.0.1:8000"

# Avatar incrustado en el propio archivo (WEBP en base64): no depende de ningún archivo externo.
AVATAR_B64 = "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"


def avatar_bot():
    """Avatar del bot para st.chat_message (imagen PIL decodificada del base64)."""
    try:
        return Image.open(io.BytesIO(base64.b64decode(AVATAR_B64)))
    except Exception:
        return "🐴"


st.set_page_config(page_title="Profesor Uma Musume", page_icon="🐴", layout="centered")

# ---------------------------------------------------------------------------
# Estilo: menú "Detalle de Uma Musume" (verde lima, crema, cinta naranja)
# ---------------------------------------------------------------------------
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=M+PLUS+Rounded+1c:wght@500;700;800&display=swap');

:root{
  --verde:#7cc62b;
  --verde-osc:#4fa31c;
  --verde-claro:#eaf7d4;
  --verde-borde:#b9dd8a;
  --naranja:#ffa726;
  --naranja-osc:#f57c16;
  --crema:#f8f4e4;
  --borde-crema:#e4dcc0;
  --sombra-crema:#d9cfa9;
  --texto:#5a4632;
  --gris:#8c8c8c;
}

.stApp, .stApp p, .stApp label, .stApp button, .stApp textarea,
.stApp div[data-testid="stMarkdownContainer"]{
  font-family:'M PLUS Rounded 1c','Nunito',sans-serif;
}
.stApp{
  background-color:var(--crema);
  background-image:radial-gradient(#eadfb8 1.2px, transparent 1.2px);
  background-size:20px 20px;
  color:var(--texto);
}
header[data-testid="stHeader"]{background:transparent;}
.block-container{max-width:760px; padding-top:1rem; padding-bottom:6rem;}

/* Barra de título verde */
.uma-header{
  background:linear-gradient(#9ddc3f,#6cc31f);
  border-bottom:4px solid var(--verde-osc);
  border-radius:0 0 18px 18px;
  color:#fff;
  text-align:center;
  font-weight:800;
  font-size:1.6rem;
  padding:.7rem 1rem;
  text-shadow:0 2px 0 rgba(0,90,0,.35);
  box-shadow:0 3px 6px rgba(0,0,0,.15);
  margin-bottom:.9rem;
}

/* Tarjeta de perfil */
.st-key-perfil{
  background:#fff;
  border:2px solid var(--borde-crema);
  border-radius:18px;
  padding:.9rem;
  box-shadow:0 3px 0 var(--sombra-crema);
  margin-bottom:.9rem;
}
.uma-profile{display:flex; gap:1rem; align-items:center;}
.uma-avatar{
  position:relative; flex:0 0 auto;
  width:96px; height:96px;
}
.uma-avatar .uma-face{
  width:100%; height:100%; border-radius:50%;
  background-size:cover; background-position:center; background-repeat:no-repeat;
  filter:drop-shadow(0 2px 3px rgba(0,0,0,.25));
}
.uma-rank{
  position:absolute; bottom:-4px; right:-10px;
  width:40px; height:40px; border-radius:50%;
  background:linear-gradient(#b9a4ff,#6a8cff);
  border:2px solid #fff;
  color:#fff; font-weight:800; font-size:.85rem;
  display:flex; align-items:center; justify-content:center;
  box-shadow:0 2px 4px rgba(0,0,0,.25);
}
.uma-name small{display:block; color:var(--gris); font-size:.8rem; font-weight:700;}
.uma-name b{display:block; font-size:1.3rem; color:var(--texto); margin-bottom:.35rem;}
.uma-ribbon{
  display:inline-block;
  background:linear-gradient(#ffc04d,#f5891f);
  border:2px solid #fff1c2;
  border-radius:6px;
  color:#fff; font-weight:800; font-size:.95rem;
  padding:.2rem 1.2rem;
  text-shadow:0 1px 0 rgba(150,70,0,.5);
}

/* Fila de estadísticas (etiqueta verde + valor) */
.uma-stats{display:grid; grid-template-columns:repeat(4,1fr); gap:.4rem; margin-top:.8rem;}
.uma-stat .lbl{
  background:linear-gradient(#8bd04a,#62b52a);
  color:#fff; font-weight:800; font-size:.75rem; text-align:center;
  border-radius:10px 10px 0 0; padding:.2rem .3rem;
}
.uma-stat .val{
  background:#fff; border:2px solid var(--verde-borde); border-top:none;
  border-radius:0 0 10px 10px;
  color:#e8741a; font-weight:800; font-size:.95rem; text-align:center;
  padding:.25rem .3rem;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}

/* Filas tipo "aptitud" para el contexto */
.uma-apt{display:grid; grid-template-columns:repeat(2,1fr); gap:.5rem .7rem;}
.uma-apt .row{
  display:flex; align-items:stretch;
  border:2px solid var(--verde-borde); border-radius:999px; overflow:hidden; background:#fff;
}
.uma-apt .k{
  background:linear-gradient(#8bd04a,#62b52a);
  color:#fff; font-weight:800; font-size:.8rem; padding:.25rem .8rem;
  display:flex; align-items:center;
}
.uma-apt .v{
  flex:1; text-align:center; color:#e8741a; font-weight:800; font-size:.9rem;
  padding:.25rem .6rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}

/* Pestañas */
.stTabs [data-baseweb="tab-list"]{
  gap:0; background:#fff;
  border:2px solid var(--verde); border-radius:12px; overflow:hidden;
  margin-bottom:.7rem;
}
.stTabs [data-baseweb="tab"]{
  flex:1; justify-content:center; height:2.6rem;
  background:transparent; color:var(--verde-osc);
}
.stTabs [data-baseweb="tab"] p{color:inherit; font-weight:800; margin:0;}
.stTabs [aria-selected="true"]{background:linear-gradient(#8bd04a,#62b52a); color:#fff;}
.stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-border"]{display:none;}

/* Burbujas de chat */
div[data-testid="stChatMessage"]{
  background:#fff;
  border:2px solid var(--borde-crema);
  border-radius:16px;
  padding:.7rem .9rem;
  box-shadow:0 2px 0 var(--sombra-crema);
}
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]),
div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]){
  background:var(--verde-claro);
  border-color:var(--verde-borde);
  box-shadow:0 2px 0 #a7cf75;
}

/* Botones naranjas con forma de píldora */
div.stButton > button{
  background:linear-gradient(#ffb74d,var(--naranja-osc));
  color:#fff; font-weight:800;
  border:2px solid #fff1c2; border-radius:999px;
  padding:.4rem 1.2rem;
  box-shadow:0 3px 0 #c75f0a;
  text-shadow:0 1px 0 rgba(150,70,0,.5);
}
div.stButton > button:hover{filter:brightness(1.07); color:#fff; border-color:#fff1c2;}
div.stButton > button:active{transform:translateY(2px); box-shadow:0 1px 0 #c75f0a; color:#fff;}
div.stButton > button:focus-visible{outline:3px solid var(--verde-osc); outline-offset:2px; color:#fff;}

/* Campo de texto: el contenedor exterior ES la píldora; todo lo de dentro queda transparente */
div[data-testid="stChatInput"]{
  background:#fff !important;
  border:2.5px solid var(--verde) !important;
  border-radius:999px !important;
  box-shadow:0 3px 0 var(--verde-osc) !important;
  padding:.15rem .5rem .15rem 1.1rem !important;
  overflow:hidden !important;
}
div[data-testid="stChatInput"]:focus-within{
  border-color:var(--verde-osc) !important;
  box-shadow:0 0 0 4px rgba(124,198,43,.28), 0 3px 0 var(--verde-osc) !important;
}
div[data-testid="stChatInput"] div,
div[data-testid="stChatInput"] textarea{
  background:transparent !important;
  background-color:transparent !important;
  border:none !important;
  box-shadow:none !important;
  outline:none !important;
  border-radius:0 !important;
}
div[data-testid="stChatInput"] textarea{color:var(--texto) !important;}
div[data-testid="stChatInput"] textarea::placeholder{color:#a79a80 !important; opacity:1;}
div[data-testid="stChatInput"] button{
  background:linear-gradient(#8bd04a,#62b52a) !important;
  color:#fff !important;
  border:2px solid #fff !important;
  border-radius:50% !important;
  box-shadow:0 2px 0 var(--verde-osc) !important;
}
div[data-testid="stChatInput"] button:disabled{opacity:.45;}
div[data-testid="stBottom"],
div[data-testid="stBottom"] > div,
div[data-testid="stBottomBlockContainer"]{background:transparent !important;}

/* Ayuda */
.uma-help{
  background:#fff; border:2px solid var(--borde-crema); border-radius:14px;
  padding:.8rem 1rem; box-shadow:0 2px 0 var(--sombra-crema);
}
.uma-help li{margin:.2rem 0;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)
st.markdown(
    f"<style>.uma-face{{background-image:url('data:image/webp;base64,{AVATAR_B64}');}}</style>",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Estado
# ---------------------------------------------------------------------------
def meta_inicial():
    return {"intencion": "—", "confianza": None, "fuente": "—", "turnos": 0, "slots": {}, "tema": None}


if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "meta" not in st.session_state:
    st.session_state.meta = meta_inicial()


def esc(valor):
    return html.escape(str(valor))


def reiniciar_chat():
    if st.session_state.session_id:
        try:
            requests.post(
                f"{API_URL}/api/reset",
                json={"session_id": st.session_state.session_id},
                timeout=10,
            )
        except requests.RequestException:
            pass
    st.session_state.messages = []
    st.session_state.session_id = None
    st.session_state.meta = meta_inicial()


def enviar_a_la_api(prompt):
    """Envía el mensaje al backend y devuelve el texto de respuesta."""
    payload = {"mensaje": prompt}
    if st.session_state.session_id:
        payload["session_id"] = st.session_state.session_id

    try:
        response = requests.post(f"{API_URL}/api/chat", json=payload, timeout=30)

        if response.status_code == 200:
            data = response.json()
            st.session_state.session_id = data["session_id"]
            ctx = data.get("contexto") or {}
            st.session_state.meta = {
                "intencion": data.get("intencion", "—"),
                "confianza": data.get("confianza"),
                "fuente": data.get("fuente", "—"),
                "turnos": ctx.get("turnos", 0),
                "slots": ctx.get("slots") or {},
                "tema": ctx.get("tema"),
            }
            return data["respuesta"]

        if response.status_code == 404:
            # Sesión expirada (30 min de inactividad)
            st.session_state.session_id = None
            return "La sesión expiró. Vuelve a enviar tu mensaje para iniciar una nueva."

        return f"Error en la API del servidor (Código: {response.status_code}): {response.text}"
    except requests.RequestException as e:
        return (
            "No se pudo conectar con el servidor en el puerto 8000. "
            f"Asegúrate de que el backend siga abierto. (Error: {e})"
        )


# ---------------------------------------------------------------------------
# Entrada del usuario (se procesa antes de dibujar, para que las
# estadísticas y el historial ya reflejen la última respuesta)
# ---------------------------------------------------------------------------
prompt = st.chat_input("Escribe tu consulta...")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.spinner("Pensando..."):
        respuesta = enviar_a_la_api(prompt)
    st.session_state.messages.append({"role": "assistant", "content": respuesta})

# ---------------------------------------------------------------------------
# Interfaz
# ---------------------------------------------------------------------------
st.markdown('<div class="uma-header">Profesor Uma Musume</div>', unsafe_allow_html=True)

meta = st.session_state.meta
conf = meta["confianza"]
conf_txt = f"{conf * 100:.0f}%" if isinstance(conf, (int, float)) else "—"
intencion_txt = str(meta["intencion"]).replace("_", " ")

with st.container(key="perfil"):
    col_info, col_btn = st.columns([4, 1.3], vertical_alignment="center")
    with col_info:
        st.markdown(
            '<div class="uma-profile">'
            '<div class="uma-avatar"><div class="uma-face"></div><span class="uma-rank">A</span></div>'
            '<div class="uma-name">'
            "<small>Tutor académico</small>"
            "<b>Profesor Uma Musume</b>"
            '<span class="uma-ribbon">Listo para ayudarte</span>'
            "</div></div>",
            unsafe_allow_html=True,
        )
    with col_btn:
        if st.button("Nuevo chat", use_container_width=True):
            reiniciar_chat()
            st.rerun()

    st.markdown(
        '<div class="uma-stats">'
        f'<div class="uma-stat"><div class="lbl">Intención</div><div class="val" title="{esc(intencion_txt)}">{esc(intencion_txt)}</div></div>'
        f'<div class="uma-stat"><div class="lbl">Confianza</div><div class="val">{esc(conf_txt)}</div></div>'
        f'<div class="uma-stat"><div class="lbl">Fuente</div><div class="val" title="{esc(meta["fuente"])}">{esc(meta["fuente"])}</div></div>'
        f'<div class="uma-stat"><div class="lbl">Turnos</div><div class="val">{esc(meta["turnos"])}</div></div>'
        "</div>",
        unsafe_allow_html=True,
    )

tab_chat, tab_contexto, tab_ayuda = st.tabs(["Chat", "Contexto", "Ayuda"])

with tab_chat:
    if not st.session_state.messages:
        st.info("Escribe tu primera pregunta en el campo de abajo para empezar.")
    for message in st.session_state.messages:
        avatar = avatar_bot() if message["role"] == "assistant" else "🧑‍🎓"
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])

with tab_contexto:
    slots = meta["slots"]

    def valor(v):
        return esc(v) if v else "—"

    st.markdown(
        '<div class="uma-apt">'
        f'<div class="row"><span class="k">Personaje</span><span class="v">{valor(slots.get("personaje"))}</span></div>'
        f'<div class="row"><span class="k">Card</span><span class="v">{valor(slots.get("card"))}</span></div>'
        f'<div class="row"><span class="k">Escenario</span><span class="v">{valor(slots.get("escenario"))}</span></div>'
        f'<div class="row"><span class="k">Tema</span><span class="v">{valor(meta["tema"])}</span></div>'
        "</div>",
        unsafe_allow_html=True,
    )
    st.caption("Lo que el bot recuerda de esta conversación. Se borra con «Nuevo chat».")

with tab_ayuda:
    st.markdown(
        '<div class="uma-help"><b>Prueba con preguntas como:</b>'
        "<ul>"
        "<li>Háblame de Gold Ship</li>"
        "<li>¿Qué son las support cards?</li>"
        "<li>¿Y sus aptitudes? (el bot recuerda el personaje anterior)</li>"
        "</ul></div>",
        unsafe_allow_html=True,
    )