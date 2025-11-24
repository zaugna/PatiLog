import streamlit as st
import pandas as pd
from datetime import date, timedelta
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIG ---
st.set_page_config(page_title="PatiLog", page_icon="🐾", layout="wide")

# --- CSS: FORCE DARK SIDEBAR & HIGH CONTRAST ---
st.markdown("""
<style>
    /* 1. Force Main Background */
    .stApp {
        background-color: #0E1117;
    }
    
    /* 2. Force Sidebar Background & Text */
    [data-testid="stSidebar"] {
        background-color: #262730;
    }
    [data-testid="stSidebar"] * {
        color: #FAFAFA !important;
    }

    /* 3. Global Text Color Fix */
    h1, h2, h3, h4, h5, h6, p, div, span, label, li {
        color: #FAFAFA !important;
    }

    /* 4. Fix Inputs (Make them Dark with White Text) */
    .stTextInput input, .stSelectbox div, .stNumberInput input, .stDateInput input {
        color: #FAFAFA !important;
        background-color: #41444C !important; /* Slightly lighter grey for inputs */
    }
    
    /* 5. Fix Table Headers */
    div[data-testid="stDataFrame"] {
        background-color: #262730;
    }
    
    /* 6. Card/Expander Styling */
    .streamlit-expanderHeader {
        background-color: #262730;
        color: white;
        border-radius: 5px;
    }
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

# --- PAGE 1: INTERACTIVE CARDS & CHARTS ---
if menu == "Genel Bakış (Kartlar)":
    st.header("🐶🐱 Evcil Hayvan Profilleri")
    st.caption("Detayları, kilo geçmişini ve aşıları görmek için karta tıklayın.")
    
    if not df.empty:
        # Process Dates
        if "Sonraki Tarih" in df.columns:
            df["Sonraki Tarih"] = pd.to_datetime(df["Sonraki Tarih"], format="%Y-%m-%d", errors='coerce')
            df = df.sort_values(by="Sonraki Tarih")

        # Get Unique Pets
        pet_names = df["Pet İsmi"].unique()

        for pet in pet_names:
            # Filter data for this specific pet
            pet_df = df[df["Pet İsmi"] == pet]
            
            # Determine Status
            closest_date = pet_df["Sonraki Tarih"].min()
            days_left = (closest_date.date() - date.today()).days if pd.notnull(closest_date) else 999
            
            icon = "🐶" if "Köpek" in pet else "🐱" if "Kedi" in pet else "🐾"
            status_emoji = "✅"
            status_text = "Durum İyi"
            
            if days_left < 7:
                status_emoji = "🚨"
                status_text = f"Dikkat! {days_left} gün kaldı"
            elif days_left < 30:
                status_emoji = "⚠️"
                status_text = f"Yaklaşıyor ({days_left} gün)"

            # --- CARD START ---
            with st.expander(f"{status_emoji} {icon} {pet}  |  {status_text}"):
                
                # Metrics
                m1, m2, m3 = st.columns(3)
                latest_weight = pet_df.iloc[-1]["Kilo (kg)"] if "Kilo (kg)" in pet_df.columns else "?"
                m1.metric("Son Kilo", f"{latest_weight} kg")
                m2.metric("Sıradaki İşlem", pet_df.iloc[0]["Aşı Tipi"])
                m3.metric("Tarih", closest_date.strftime('%d.%m.%Y'))
                
                st.write("---")
                
                # --- NEW: WEIGHT HISTORY CHART ---
                st.subheader("📉 Kilo Geçmişi")
                if "Kilo (kg)" in pet_df.columns and "Uygulama Tarihi" in pet_df.columns:
                    chart_data = pet_df[["Uygulama Tarihi", "Kilo (kg)"]].copy()
                    # Convert to datetime for plotting
                    chart_data["Uygulama Tarihi"] = pd.to_datetime(chart_data["Uygulama Tarihi"], errors='coerce')
                    chart_data = chart_data.dropna()
                    chart_data = chart_data.set_index("Uygulama Tarihi").sort_index()
                    
                    st.line_chart(chart_data)

                st.write("---")
                st.subheader("📜 Aşı Geçmişi")
                
                # History Table
                display_df = pet_df[["Aşı Tipi", "Uygulama Tarihi", "Sonraki Tarih"]].copy()
                display_df["Uygulama Tarihi"] = pd.to_datetime(display_df["Uygulama Tarihi"]).dt.strftime('%d.%m.%Y')
                display_df["Sonraki Tarih"] = pd.to_datetime(display_df["Sonraki Tarih"]).dt.strftime('%d.%m.%Y')
                
                st.table(display_df)
            # --- CARD END ---

    else:
        st.info("Henüz kayıt yok. 'Yeni Kayıt Ekle' menüsünden başlayın.")

# --- PAGE 2: TABLE VIEW (For Deletion) ---
elif menu == "Düzenle / Sil":
    st.header("📝 Kayıt Yönetimi")
    
    if not df.empty:
        df["Sil"] = False
        if "Sonraki Tarih" in df.columns:
            df["Sonraki Tarih"] = pd.to_datetime(df["Sonraki Tarih"], format="%Y-%m-%d", errors='coerce')
            df = df.sort_values(by="Sonraki Tarih")

        column_config = {
            "Sil": st.column_config.CheckboxColumn("Sil?", default=False, width="small"),
            "Pet İsmi": st.column_config.TextColumn("İsim", disabled=True),
            "Aşı Tipi": st.column_config.TextColumn("İşlem", disabled=True),
            "Sonraki Tarih": st.column_config.DateColumn("Tarih", format="DD.MM.YYYY", disabled=True),
        }

        edited_df = st.data_editor(df, column_config=column_config, hide_index=True, use_container_width=True)

        rows_to_delete = edited_df[edited_df["Sil"] == True]
        if not rows_to_delete.empty:
            if st.button(f"🗑️ Seçili {len(rows_to_delete)} Kaydı Sil", type="primary"):
                indexes_to_keep = edited_df[edited_df["Sil"] == False].index.tolist()
                try:
                    delete_rows(indexes_to_keep)
                    st.success("Silindi!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Hata: {e}")

# --- PAGE 3: NEW ENTRY ---
elif menu == "Yeni Kayıt Ekle":
    st.header("💉 Yeni Giriş")
    
    col1, col2 = st.columns(2)
    with col1:
        existing_names = [x for x in df["Pet İsmi"].unique() if str(x).strip() != ""] if not df.empty else []
        options = existing_names + ["➕ Yeni Ekle..."]
        sel = st.selectbox("Evcil Hayvan", options)
        pet_name = st.text_input("İsim Giriniz") if sel == "➕ Yeni Ekle..." else sel

        vaccine = st.selectbox("İşlem Tipi", ["Karma (DHPP)", "Kuduz", "Bronşin", "Lösemi", "Lyme", "İç Parazit", "Dış Parazit", "Check-up"])
        weight = st.number_input("Güncel Kilo (kg)", min_value=0.0, step=0.1, format="%.1f")

    with col2:
        date_applied = st.date_input("Uygulama Tarihi", date.today())
        
        st.write("---")
        st.write("📅 **Geçerlilik Süresi**")
        
        timing = st.selectbox("Süre Seçimi", ["1 Ay", "2 Ay", "3 Ay", "6 Ay", "1 Yıl", "Manuel Tarih"])
        
        final_due_date = None
        if timing == "Manuel Tarih":
            final_due_date = st.date_input("Bitiş Tarihi", min_value=date_applied)
        else:
            months = 12 if "Yıl" in timing else int(timing.split(" ")[0])
            final_due_date = date_applied + timedelta(days=months*30)

        reminder_date = final_due_date - timedelta(days=7)
        st.caption(f"✅ **Aşı Bitiş Tarihi:** {final_due_date.strftime('%d.%m.%Y')}")
        st.info(f"🔔 **Hatırlatma Maili:** {reminder_date.strftime('%d.%m.%Y')} tarihinde gönderilecek.")

    st.write("")
    if st.button("Kaydet", type="primary", use_container_width=True):
        if pet_name:
            save_entry(pet_name, vaccine, date_applied, final_due_date, weight)
            st.success("Kaydedildi!")
            st.rerun()
        else:
            st.warning("İsim giriniz.")
