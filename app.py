
import streamlit as st

st.set_page_config(
    page_title="KickPredict AI",
    page_icon="⚽",
    layout="wide"
)

st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #07111f, #102a36);
    color: white;
}
</style>
""", unsafe_allow_html=True)

st.title("⚽ KickPredict AI")
st.subheader("Erstellt von Tiago Faruk und Yigit")

st.success("Die Website funktioniert!")

st.write("Wenn du diesen Text siehst, kann Streamlit deine Seite anzeigen.")

st.markdown("### 🔐 Anmeldung")

username = st.text_input("Benutzername")
password = st.text_input("Passwort", type="password")

if st.button("Anmelden"):
    st.info("Die Testseite funktioniert. Die Anmeldung ist noch nicht aktiviert.")
