import streamlit as st
from config import MOCK_USERS

def login_gate():
    if "authed" not in st.session_state:
        st.session_state.authed = False
    if not st.session_state.authed:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("## 🧠 AlphaHire")
            st.caption("AI Talent Engine — Quant Trading | Delhi-NCR")
            st.divider()
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.button("Login", use_container_width=True):
                if MOCK_USERS.get(u) == p:
                    st.session_state.authed = True
                    st.session_state.user = u
                    st.rerun()
                else:
                    st.error("Invalid credentials")
            st.caption("Demo → user: `admin` / pass: `alphahire2024`")
        st.stop()