import streamlit as st
import pandas as pd
import altair as alt
from datetime import date, timedelta
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIG ---
st.set_page_config(page_title="PatiLog", page_icon="🐾", layout="wide")

# --- THE "NUKE" CSS FIX ---
st.markdown("""
<style>
    /* 1. FORCE DARK BACKGROUND EVERYWHERE */
    .stApp { background-color: #0E1117; }
    
    /* 2. TEXT COLORS */
    h1, h2, h3, h4, h5, h6, p, div, span, li, label { color: #E0E0E0 !important; }
    
    /* 3. SIDEBAR */
    [data-testid="stSidebar"] { background-color: #262730; }
    
    /* 4. DROPDOWN & DATE PICKER POPUPS (The White Box Fix) */
    div[data-baseweb="popover"], div[data-baseweb="menu"], div[role="listbox"] {
        background-color: #262730 !important;
    }
    div[data-baseweb="select"] > div {
        background-color: #262730 !important;
        color: white !important;
        border-color: #4C4C4C !important;
    }
    /* The actual list items in the dropdown */
    li[role="option"] {
        background-color: #262730 !important;
        color: white !important;
    }
    /* Hover state for list items */
    li[role="option"]:hover {
        background-color: #FF4B4B !important;
    }

    /* 5. INPUT FIELDS (Text, Number, Date) */
    input {
        color: white !important;
        background-color: #262730 !important;
    }

    /* 6. EXPANDER / CARD HEADER (Fixing the White Flash) */
    .streamlit-expanderHeader {
        background-color: #262730 !important;
        color: white !important;
        border: 1px solid #4C4C4C;
    }
    .streamlit-expanderHeader:hover {
        background-color: #363945 !important; /* Slightly lighter on hover */
        color: #FF4B4B !important;
    }
    div[data-testid="stExpander"] {
        border: none;
        background-color: transparent;
    }

    /* 7. TABLE FIXES */
    [data-testid="stDataFrame"] { background-color: #262730; }
</style>
""", unsafe_allow_html=True)

# --- DATABASE CONNECTION ---
@st.cache_resource(ttl=60)
def get_db():
    creds_dict = st.secrets["gcp_service_account"]
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
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
    except Exception:
        return pd.DataFrame()

def save_entry(pet_name, vaccine, date_applied, next_due_date, weight):
    sh = get_db()
    worksheet = sh.get_worksheet(0)
    if not worksheet.get_all_values():
        worksheet.append_row(["Pet İsmi", "Aşı Tipi", "Uygulama Tarihi", "Sonraki Tarih", "Kilo (kg)"])
    worksheet.append_row([pet_name, vaccine, str(date_applied), str(next_due_date), weight])

def delete_rows(indexes_to_keep):
    sh = get_db()
    worksheet = sh.get_worksheet(0)
    df = load_data()
    if not df.empty:
        df_cleaned = df.iloc[indexes_to_keep]
        worksheet.clear()
        worksheet.append_row(["Pet İsmi", "Aşı Tipi", "Uygulama Tarihi", "Sonraki Tarih", "Kilo (kg)"])
        if not df_cleaned.empty:
            worksheet.append_rows(df_cleaned.values.tolist())

# --- SIDEBAR ---
st.sidebar.title("🐾 PatiLog")
menu = st.sidebar.radio("Menü", ["Genel Bakış (Kartlar)", "Düzenle / Sil", "Yeni Kayıt Ekle"])
df = load_data()

# --- PAGE 1: CARDS & PRO CHART ---
if menu == "Genel Bakış (Kartlar)":
    st.header("🐶🐱 Evcil Hayvan Profilleri")
    
    if not df.empty:
        if "Sonraki Tarih" in df.columns:
            df["Sonraki Tarih"] = pd.to_datetime(df["Sonraki Tarih"], format="%Y-%m-%d", errors='coerce')
            df = df.sort_values(by="Sonraki Tarih")

        pet_names = df["Pet İsmi"].unique()

        for pet in pet_names:
            pet_df = df[df["Pet İsmi"] == pet]
            closest_date = pet_df["Sonraki Tarih"].min()
            days_left = (closest_date.date() - date.today()).days if pd.notnull(closest_date) else 999
            
            icon = "🐶" if "Köpek" in pet else "🐱" if "Kedi" in pet else "🐾"
            status_emoji = "✅"
            status_text = "Durum İyi"
            
            if days_left < 7:
                status_emoji = "🚨"
                status_text = f"Dikkat! {days_left} gün"
            elif days_left < 30:
                status_emoji = "⚠️"
                status_text = f"Yaklaşıyor ({days_left} gün)"

            # CARD
            with st.expander(f"{status_emoji} {icon} {pet}  |  {status_text}"):
                
                # METRICS
                m1, m2, m3 = st.columns(3)
                latest_weight = pet_df.iloc[-1]["Kilo (kg)"] if "Kilo (kg)" in pet_df.columns else "?"
                m1.metric("Son Kilo", f"{latest_weight} kg")
                m2.metric("Sıradaki İşlem", pet_df.iloc[0]["Aşı Tipi"])
                m3.metric("Tarih", closest_

