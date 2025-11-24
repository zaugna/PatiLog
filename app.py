import streamlit as st
import pandas as pd
from datetime import date

# --- CONFIG ---
st.set_page_config(page_title="PatiLog", page_icon="🐾", layout="centered")

# --- DARK MODE CSS HACK (Just in case) ---
st.markdown("""
<style>
    .stApp {
        background-color: #0E1117;
        color: #FAFAFA;
    }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
st.sidebar.title("🐾 PatiLog")
menu = st.sidebar.radio("Menü", ["Genel Bakış", "Aşı Takvimi", "Ayarlar"])

# --- MAIN PAGE ---
if menu == "Genel Bakış":
    st.title("🐶🐱 Evcil Hayvan Takibi")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info("🐕 **Köpek (Max)**\n\n**Son Kilo:** 12.5 kg\n\n⚠️ **Kuduz:** 7 gün kaldı")
        
    with col2:
        st.success("🐈 **Kedi (Luna)**\n\n**Son Kilo:** 4.2 kg\n\n✅ **Karma:** 2 ay var")

    st.write("---")
    st.subheader("Yaklaşan Aşılar")
    
    # Fake data for visual test
    data = {
        'İsim': ['Max', 'Max', 'Luna'],
        'Aşı': ['Kuduz', 'İç Parazit', 'Karma'],
        'Tarih': ['2025-12-01', '2025-12-15', '2026-02-10'],
        'Durum': ['Yaklaşıyor', 'Normal', 'Normal']
    }
    df = pd.DataFrame(data)
    st.table(df)

elif menu == "Aşı Takvimi":
    st.header("💉 Yeni Aşı Girişi")
    st.selectbox("Evcil Hayvan", ["Max", "Luna"])
    st.selectbox("Aşı Tipi", ["Kuduz", "Karma", "Lösemi", "İç Parazit"])
    st.date_input("Uygulama Tarihi", date.today())
    st.button("Kaydet")
