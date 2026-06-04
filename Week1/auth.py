import streamlit as st
from config import MOCK_USERS

def login_gate():
    if "authed" not in st.session_state:
        st.session_state.authed = False
    if not st.session_state.authed:
        st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&display=swap');
        html, body, [class*="css"] {
            font-family: 'DM Sans', sans-serif;
            background-color: #0d0f14;
            color: #e8eaf0;
        }
        .main .block-container {
            max-width: 420px;
            padding-top: 8vh;
        }
        .login-logo {
            width: 40px; height: 40px;
            background: linear-gradient(135deg, #f5a623, #e07b00);
            border-radius: 10px;
            display: flex; align-items: center; justify-content: center;
            font-size: 1.1rem; font-weight: 800;
            color: #0d0f14;
            margin-bottom: 1.2rem;
        }
        .login-title {
            font-size: 1.6rem;
            font-weight: 700;
            color: #ffffff;
            letter-spacing: -0.5px;
            margin-bottom: 0.3rem;
        }
        .login-sub {
            font-size: 0.85rem;
            color: #5a6278;
            margin-bottom: 2.5rem;
        }
        div[data-testid="stTextInput"] input {
            background: #13151e !important;
            border: 1px solid #1e2230 !important;
            border-radius: 8px !important;
            color: #e8eaf0 !important;
            font-family: 'DM Sans', sans-serif !important;
            font-size: 0.9rem !important;
            padding: 0.65rem 1rem !important;
        }
        div[data-testid="stTextInput"] input:focus {
            border-color: #f5a623 !important;
            box-shadow: 0 0 0 2px rgba(245,166,35,0.15) !important;
        }
        div[data-testid="stTextInput"] label {
            color: #7a8299 !important;
            font-size: 0.8rem !important;
            font-weight: 500 !important;
            letter-spacing: 0.03em !important;
        }
        [data-testid="stButton"] > button {
            background: linear-gradient(135deg, #f5a623, #e07b00) !important;
            color: #0d0f14 !important;
            font-weight: 700 !important;
            font-size: 0.9rem !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 0.7rem !important;
            width: 100% !important;
            margin-top: 0.5rem !important;
            box-shadow: 0 4px 16px rgba(245,166,35,0.2) !important;
        }
        [data-testid="stButton"] > button:hover {
            box-shadow: 0 6px 24px rgba(245,166,35,0.35) !important;
            transform: translateY(-1px) !important;
        }
        </style>
        """, unsafe_allow_html=True)

        st.markdown('<div class="login-logo">A</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-title">AlphaHire</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-sub">Quant Recruitment Intelligence</div>', unsafe_allow_html=True)

        u = st.text_input("Username")
        p = st.text_input("Password", type="password")

        if st.button("Sign in"):
            if MOCK_USERS.get(u) == p:
                st.session_state.authed = True
                st.session_state.user = u
                st.rerun()
            else:
                st.markdown("""
                <div style='color:#e05252; font-size:0.82rem;
                margin-top:0.5rem; padding:0.6rem 0.9rem;
                background:#1a1010; border:1px solid #3a1a1a;
                border-radius:7px;'>
                    Invalid credentials. Please try again.
                </div>
                """, unsafe_allow_html=True)
        st.stop()