

import streamlit as st
import pandas as pd
from datetime import date, timedelta
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIG ---
st.set_page_config(page_title="PatiLog", page_icon="🐾", layout="wide")

# --- DATABASE CONNECTION ---
@st.cache_resource
def get_db():
    # Load secrets directly (The Bulletproof Way)
    creds_dict = st.secrets["gcp_service_account"]
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open("PatiLog_DB")

# --- FUNCTIONS ---
def load_data():
    try:
        sh = get_db()
        worksheet = sh.get_worksheet(0)
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        return df
    except Exception as e:
        return pd.DataFrame()

def save_entry(pet_name, vaccine, date_applied, next_due_date, weight):
    sh = get_db()
    worksheet = sh.get_worksheet(0)
    # Add headers if empty
    if not worksheet.get_all_values():
        worksheet.append_row(["Pet İsmi", "Aşı Tipi", "Uygulama Tarihi", "Sonraki Tarih", "Kilo (kg)"])
    
    worksheet.append_row([pet_name, vaccine, str(date_applied), str(next_due_date), weight])

# --- APP INTERFACE ---
st.title("🐾 PatiLog")

# 1. Load Data to find existing pets
df = load_data()
existing_pets = []
if not df.empty and "Pet İsmi" in df.columns:
    existing_pets = list(df["Pet İsmi"].unique())

# Sidebar Navigation
menu = st.sidebar.radio("Menü", ["Genel Bakış", "Yeni Kayıt Ekle"])

# --- PAGE: DASHBOARD ---
if menu == "Genel Bakış":
    st.header("📊 Genel Durum")
    
    if not df.empty:
        # Sort by Next Date
        if "Sonraki Tarih" in df.columns:
            df["Sonraki Tarih"] = pd.to_datetime(df["Sonraki Tarih"], format="%Y-%m-%d", errors='coerce')
            df = df.sort_values(by="Sonraki Tarih")

        # Display Data
        st.dataframe(
            df, 
            column_config={
                "Sonraki Tarih": st.column_config.DateColumn("Sonraki Aşı", format="DD.MM.YYYY"),
                "Uygulama Tarihi": st.column_config.DateColumn("Yapılan Tarih", format="DD.MM.YYYY"),
                "Kilo (kg)": st.column_config.NumberColumn("Kilo", format="%.1f kg")
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("Henüz kayıt yok. Yeni kayıt ekleyerek başlayın.")

# --- PAGE: NEW ENTRY ---
elif menu == "Yeni Kayıt Ekle":
    st.header("💉 Yeni Kayıt")
    
    with st.form("entry_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            # Pet Name Selection (Select existing OR type new)
            st.write("Reference: Evcil Hayvan Seçimi")
            pet_selection_mode = st.radio("Seçim Modu", ["Listeden Seç", "Yeni Pet Ekle"], horizontal=True, label_visibility="collapsed")
            
            if pet_selection_mode == "Listeden Seç" and existing_pets:
                pet_name = st.selectbox("Evcil Hayvan", existing_pets)
            else:
                pet_name = st.text_input("Evcil Hayvan İsmi (Örn: Max, Luna)")

            vaccine = st.selectbox("Aşı / İşlem", ["Karma (DHPP)", "Kuduz", "Bronşin", "Lösemi", "İç Parazit", "Dış Parazit", "Lyme", "Muayene/Kontrol"])
            weight = st.number_input("Güncel Kilo (kg)", min_value=0.0, step=0.1, format="%.1f")

        with col2:
            date_applied = st.date_input("Uygulama Tarihi", date.today())
            
            st.write("---")
            st.write("📅 **Hatırlatma Zamanlayıcısı**")
            
            reminder_method = st.radio("Zamanlama Tipi", ["Ay Bazlı (Otomatik)", "Tarih Seçimi (Manuel)"], horizontal=True)
            
            next_due = None
            
            if reminder_method == "Ay Bazlı (Otomatik)":
                months_later = st.slider("Kaç ay sonra hatırlat?", 1, 12, 12)
                next_due = date_applied + timedelta(days=months_later*30)
                st.write(f"👉 **Hesaplanan Tarih:** {next_due.strftime('%d.%m.%Y')}")
            else:
                next_due = st.date_input("Sonraki Aşı Tarihi")

        # SUBMIT BUTTON (Primary Color Fix)
        st.write("")
        submitted = st.form_submit_button("Kaydet", type="primary", use_container_width=True)
        
        if submitted:
            if pet_name:
                try:
                    save_entry(pet_name, vaccine, date_applied, next_due, weight)
                    st.success("✅ Kayıt Başarılı!")
                    st.cache_resource.clear() # Refresh data immediately
                except Exception as e:
                    st.error(f"Kayıt Hatası: {e}")
            else:
                st.warning("Lütfen bir evcil hayvan ismi girin.")
