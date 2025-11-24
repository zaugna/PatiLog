import streamlit as st
import pandas as pd
from datetime import date, timedelta
import gspread
from google.oauth2.service_account import Credentials
import json  # <--- NEW: Added this library

# --- CONFIG & STYLE ---
st.set_page_config(page_title="PatiLog", page_icon="🐾", layout="wide")

st.markdown("""
<style>
    .stApp {background-color: #0E1117; color: #FAFAFA;}
    div.stButton > button {background-color: #FF4B4B; color: white; border-radius: 8px;}
</style>
""", unsafe_allow_html=True)

# --- DATABASE CONNECTION ---
@st.cache_resource
def get_db():
    # --- UPDATED SECTION START ---
    # We grab the text block we created in secrets
    json_str = st.secrets["gcp_service_account"]["info"]
    # We convert that text back into a dictionary Python can understand
    creds_dict = json.loads(json_str)
    # --- UPDATED SECTION END ---
    
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open("PatiLog_DB")

# --- FUNCTIONS ---
def load_data():
    try:
        sh = get_db()
        worksheet = sh.get_worksheet(0)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame()

def save_entry(pet_name, vaccine, date_applied, next_due_date, weight):
    sh = get_db()
    worksheet = sh.get_worksheet(0)
    if not worksheet.get_all_values():
        worksheet.append_row(["Pet İsmi", "Aşı Tipi", "Uygulama Tarihi", "Sonraki Tarih", "Kilo (kg)"])
    
    worksheet.append_row([pet_name, vaccine, str(date_applied), str(next_due_date), weight])

# --- SIDEBAR MENU ---
st.sidebar.header("🐾 PatiLog Menü")
menu = st.sidebar.radio("Seçiniz", ["Genel Bakış", "Yeni Kayıt Ekle"])

# --- PAGE: DASHBOARD (Genel Bakış) ---
if menu == "Genel Bakış":
    st.title("📊 Genel Durum")
    
    df = load_data()
    
    if not df.empty:
        # Check if 'Sonraki Tarih' exists and handle sorting safely
        if "Sonraki Tarih" in df.columns:
             # Force convert to datetime, errors='coerce' turns bad data into NaT (Not a Time)
            df["Sonraki Tarih"] = pd.to_datetime(df["Sonraki Tarih"], format="%Y-%m-%d", errors='coerce')
            df = df.sort_values(by="Sonraki Tarih")

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
        st.info("Henüz kayıt bulunamadı. Lütfen 'Yeni Kayıt Ekle' menüsünden veri girişi yapın.")

# --- PAGE: NEW ENTRY (Yeni Kayıt) ---
elif menu == "Yeni Kayıt Ekle":
    st.title("💉 Yeni Aşı / Sağlık Girişi")
    
    with st.form("entry_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            pet_name = st.selectbox("Evcil Hayvan", ["Köpek (Max)", "Kedi (Luna)", "Diğer"])
            vaccine = st.selectbox("Aşı / İşlem", ["Kuduz", "Karma (DHPP)", "Karma (Kedi)", "Bronşin", "Lösemi", "İç Parazit", "Dış Parazit"])
            weight = st.number_input("Güncel Kilo (kg)", min_value=0.0, step=0.1, format="%.1f")
        
        with col2:
            date_applied = st.date_input("Uygulama Tarihi", date.today())
            
            reminder_type = st.selectbox("Hatırlatma Sıklığı", ["1 Yıl Sonra", "3 Ay Sonra", "1 Ay Sonra", "Hatırlatma Yok"])
            
            if reminder_type == "1 Yıl Sonra":
                next_due = date_applied + timedelta(days=365)
            elif reminder_type == "3 Ay Sonra":
                next_due = date_applied + timedelta(days=90)
            elif reminder_type == "1 Ay Sonra":
                next_due = date_applied + timedelta(days=30)
            else:
                next_due = "" 
            
            st.write(f"📅 **Planlanan Sonraki Tarih:** {next_due}")

        submitted = st.form_submit_button("Kaydet")
        
        if submitted:
            try:
                save_entry(pet_name, vaccine, date_applied, next_due, weight)
                st.success(f"✅ {pet_name} için {vaccine} kaydı başarıyla eklendi!")
                # Clear cache so the new data shows up immediately
                st.cache_resource.clear()
            except Exception as e:
                st.error(f"Hata oluştu: {e}")
