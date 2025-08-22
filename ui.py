# app.py

import os
import streamlit as st
import time

from main import (
    hybrid_response,
    read_text_from_file,
    summarize_document,
    suggest_docs_for_stage,
)

st.set_page_config(page_title="Maritime AI Assistant", page_icon="⚓", layout="wide")

# -----------------------------
# Custom CSS (95% scale + narrowed & left-shifted chat_input)
# -----------------------------
st.markdown("""
<style>
/* Scale the entire app to 95% */
body > div[role="main"] {
    transform: scale(0.95);
    transform-origin: top left;
}

/* General body and font styles */
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

/* Main content container styling */
.main .block-container {
    padding-top: 0.5rem;  
    padding-bottom: 2rem;
    max-width: 1200px;
    margin: 0 auto;
}

/* Cards for the left panel */
.stContainer {
    border: none !important;
    background-color: transparent !important;
}

.card {
    background: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    margin-bottom: 20px;
}
.card h4 {
    margin-top: 0;
    font-weight: 600;
    color: #333;
}

/* Chat bubbles and chat container */
.chat-container {
    height: 60vh; 
    overflow-y: auto; 
    padding-right: 15px; 
    padding-bottom: 15px; 
}

.chat-bubble {
    padding: 15px 19px;
    border-radius: 19px;
    margin: 9px 0;
    max-width: 80%;
    white-space: pre-wrap;
    line-height: 1.4;
    font-size: 0.95rem;
}
.user {
    background: #007bff;
    color: white;
    margin-left: auto;
    border-bottom-right-radius: 5px;
}
.assistant {
    background: #f0f2f6;
    border: 1px solid #e0e0e0;
    color: #333;
    border-bottom-left-radius: 5px;
}

/* Input row styling (for general inputs, not chat_input) */
.input-wrap {
    max-width: 855px;
    margin: 0.95rem auto 0;
}
.stTextInput > div > div {
    max-width: 600px !important;  
    margin: 0 auto;  
}
.stTextInput > div > div > input {
    width: 100% !important;  
    border-radius: 23px;
    border: 1px solid #ccc;
    padding: 9.5px 13.5px;
    font-size: 0.95rem;
}

/* Streamlit chat_input box at the bottom, narrowed & slightly left-shifted */
[data-testid="stChatInput"] {
    display: flex !important;
    justify-content: flex-end !important;
    padding-right: 50px;  /* adjust spacing from right */
}
[data-testid="stChatInput"] > div {
    max-width: 600px !important;  
    width: 100% !important;
    transform: translateX(-110px);  /* move slightly left */
}
[data-testid="stChatInput"] input {
    width: 100% !important;
    padding: 10px 14px;
    font-size: 0.95rem;
    border-radius: 23px;
}

/* Header and captions */
h1 { 
    font-weight: 800; 
    color: #1a237e; 
    font-size: 2.375rem; 
    margin-top: 0.2rem;  
    margin-bottom: 0.2rem;
}
.st-emotion-cache-1avcm0n p {
    color: #6c757d;
    font-size: 0.9rem;
}

/* Buttons */
.stButton button {
    border-radius: 7.5px;
    padding: 9.5px 14px;
    font-weight: 600;
    font-size: 0.95rem;
    transition: background-color 0.3s ease;
}
.stButton button[kind="secondary"] {
    background: #f0f2f6;
    border: 1px solid #e0e0e0;
    color: #333;
}
.stButton button[kind="secondary"]:hover {
    background: #e0e0e0;
}
.stButton button[kind="primary"] {
    background: #007bff;
    color: white;
    border: none;
}
.stButton button[kind="primary"]:hover {
    background: #0056b3;
}

/* Minor component tweaks */
.stSelectbox div[data-baseweb="select"] {
    border-radius: 7.5px;
}
.stFileUploader div[data-baseweb="file-uploader"] {
    border-radius: 7.5px;
}
</style>
""", unsafe_allow_html=True)


# -----------------------------
# Session State
# -----------------------------
if "chat" not in st.session_state:
    st.session_state.chat = [
        {"role": "assistant", "content": "Hello! I’m your **Maritime AI Assistant**. I can help with laytime & CP queries, document analysis, and more."}
    ]
if "uploads" not in st.session_state:
    st.session_state.uploads = {}

# -----------------------------
# Core chat processing function
# -----------------------------
def handle_user_query(user_query: str):
    """Adds user query to chat and gets assistant response."""
    st.session_state.chat.append({"role": "user", "content": user_query})
    with st.spinner("Thinking..."):
        reply = hybrid_response(user_query, chat_history=st.session_state.chat)
    st.session_state.chat.append({"role": "assistant", "content": reply})
    st.rerun()

# -----------------------------
# Header (shifted to top)
# -----------------------------
st.markdown('<h1 style="margin-top:0.2rem;">⚓ Maritime Virtual Assistant</h1>', unsafe_allow_html=True)
st.caption("Your dedicated AI partner for charter parties, laytime, weather, and more.")

# -----------------------------
# Layout: Left panel with two cards, main chat area on the right
# -----------------------------
left, right = st.columns([1, 2.5], gap="large")

with left:
    # Combined Card for Documents + Quick Checklists
    # 1) Documents Card
    st.markdown("#### 📄 Document Analysis")
    uploaded_files = st.file_uploader(
        "Upload (PDF, DOCX, TXT, CSV, XLSX)",
        type=["pdf", "docx", "txt", "csv", "xlsx"],
        accept_multiple_files=True,
        key="uploader"
    )

    if uploaded_files:
        with st.spinner("Processing files..."):
            for f in uploaded_files:
                content_bytes = f.read()
                text = read_text_from_file(f.name, content_bytes)
                st.session_state.uploads[f.name] = text
        st.success(f"Successfully uploaded {len(uploaded_files)} file(s).")

    colA, colB = st.columns(2)
    with colA:
        summarize_clicked = st.button("Summarize All", type="primary", use_container_width=True)
    with colB:
        clear_clicked = st.button("Clear Docs", use_container_width=True)

    if summarize_clicked and st.session_state.uploads:
        with st.spinner("Generating summaries..."):
            for fname, txt in st.session_state.uploads.items():
                summary = summarize_document(txt)
                st.session_state.chat.append(
                    {"role": "assistant", "content": f"**Summary for _{fname}_**\n\n{summary}"}
                )
            st.success("Summaries added to chat.")

    if clear_clicked:
        st.session_state.uploads = {}
        st.toast("Cleared uploaded docs")
        st.rerun()

    st.markdown("---")  # Divider between sections

    # 2) Quick Actions Card
    st.markdown("#### ⚡ Quick Checklists")
    st.markdown("Get a checklist of required documents for a specific voyage stage.", unsafe_allow_html=True)

    stage = st.selectbox(
        "Voyage Stage",
        ["—", "Pre-Loading", "Arrival", "At Sea", "Discharge", "Post Voyage"],
        key="stage_select"
    )

    if st.button("Generate Checklist", use_container_width=True):
        if stage != "—":
            with st.spinner(f"Generating checklist for {stage}..."):
                out = suggest_docs_for_stage(stage)
            st.session_state.chat.append({"role": "assistant", "content": out})
            st.success("Checklist added to chat.")
        else:
            st.warning("Please select a stage first.")

    st.markdown('</div>', unsafe_allow_html=True)


with right:
    st.markdown("### 💬 Chat")
    
    chat_container = st.container(height=500)
    with chat_container:
        for m in st.session_state.chat:
            role = m.get("role", "assistant")
            content = m.get("content", "")
            css = "user" if role == "user" else "assistant"
            st.markdown(f'<div class="chat-bubble {css}">{content}</div>', unsafe_allow_html=True)

# Chat input fixed at bottom
user_query = st.chat_input(
    "Ask about laytime, CP clauses, weather, or distances...",
    key="chat_in"
)
if user_query:
    handle_user_query(user_query)
