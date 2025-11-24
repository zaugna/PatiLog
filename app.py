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
    creds_dict = st.secrets["gcp_service_account"]
    # Broader scopes to find the file
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
        # expected_headers helps if sheet is empty/weird
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()

def save_entry(pet_name, vaccine, date_applied, next_due_date, weight):
    sh = get_db()
    worksheet = sh.get_worksheet(0)
    
    # If header is missing, add it
    if not worksheet.get_all_values():
        worksheet.append_row(["Pet İsmi", "Aşı Tipi", "Uygulama Tarihi", "Sonraki Tarih", "Kilo (kg)"])
    
    worksheet.append_row([pet_name, vaccine, str(date_applied), str(next_due_date), weight])

# --- SIDEBAR & SETUP ---
st.sidebar.header("🐾 PatiLog")
menu = st.sidebar.radio("Menü", ["Genel Bakış", "Yeni Kayıt Ekle"])

# Load data once at the start
df = load_data()

# --- PAGE 1: GENEL BAKIŞ ---
if menu == "Genel Bakış":
    st.header("📊 Genel Durum")
    
    if not df.empty:
        # Clean Data Types for Display
        display_df = df.copy()
        
        # Ensure correct column ordering
        cols = ["Pet İsmi", "Aşı Tipi", "Sonraki Tarih", "Kilo (kg)"]
        # Only keep columns that actually exist in the sheet
        cols = [c for c in cols if c in display_df.columns]
        display_df = display_df[cols]

        # Sort Logic
        if "Sonraki Tarih" in display_df.columns:
            display_df["Sonraki Tarih"] = pd.to_datetime(display_df["Sonraki Tarih"], format="%Y-%m-%d", errors='coerce')
            display_df = display_df.sort_values(by="Sonraki Tarih")

        # Table with Explicit Headers
        st.dataframe(
            display_df,
            column_config={
                "Pet İsmi": st.column_config.TextColumn("Evcil Hayvan"),
                "Aşı Tipi": st.column_config.TextColumn("Yapılan İşlem"),
                "Sonraki Tarih": st.column_config.DateColumn("Sonraki Randevu", format="DD.MM.YYYY"),
                "Kilo (kg)": st.column_config.NumberColumn("Kilo", format="%.1f kg")
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("Kayıt bulunamadı.")

# --- PAGE 2: YENİ KAYIT (No Form Wrapper) ---
elif menu == "Yeni Kayıt Ekle":
    st.header("💉 Yeni Kayıt Girişi")

    col1, col2 = st.columns(2)
    
    with col1:
        # 1. Pet Name Logic
        existing_pets = []
        if not df.empty and "Pet İsmi" in df.columns:
            existing_pets = [p for p in df["Pet İsmi"].unique() if p] # Filter out empty strings
            
        # Toggle between existing or new
        is_new_pet = st.checkbox("Listede yok (Yeni Pet Ekle)")
        
        if not is_new_pet and existing_pets:
            pet_name = st.selectbox("Evcil Hayvan Seç", existing_pets)
        else:
            pet_name = st.text_input("Evcil Hayvan İsmi Giriniz")

        vaccine = st.selectbox("İşlem Tipi", ["Karma (DHPP)", "Kuduz", "Bronşin", "Lösemi", "İç Parazit", "Dış Parazit", "Genel Kontrol"])
        weight = st.number_input("Güncel Kilo (kg)", min_value=0.0, step=0.1, format="%.1f")

    with col2:
        date_applied = st.date_input("Uygulama Tarihi", date.today())
        
        st.divider()
        st.write("📅 **Hatırlatma Ayarları**")
        
        # Radio button to switch modes
        timing_mode = st.radio("Süre Belirleme:", ["Otomatik (Ay Seçimi)", "Manuel (Tarih Seçimi)"], horizontal=True)
        
        final_due_date = None
        
        if timing_mode == "Otomatik (Ay Seçimi)":
            # Bug fix: Dropdown for months
            month_choice = st.selectbox("Kaç ay sonra?", [1, 2, 3, 12], format_func=lambda x: f"{x} Ay Sonra")
            
            # Real-time calculation
            final_due_date = date_applied + timedelta(days=month_choice*30)
            st.info(f"👉 **Hesaplanan Sonraki Tarih:** {final_due_date.strftime('%d.%m.%Y')}")
            
        else:
            # Bug fix: Calendar appears instantly
            final_due_date = st.date_input("Lütfen Tarih Seçiniz", min_value=date_applied)

    st.write("")
    # Submit Button (Outside of form, triggers manual save)
    if st.button("Kaydet", type="primary", use_container_width=True):
        if pet_name:
            try:
                save_entry(pet_name, vaccine, date_applied, final_due_date, weight)
                st.success(f"✅ {pet_name} için kayıt oluşturuldu!")
                # Force reload to update the list immediately
                st.cache_resource.clear() 
            except Exception as e:
                st.error(f"Hata: {e}")
        else:
            st.warning("Lütfen bir isim giriniz.")
