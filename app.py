import streamlit as st
import pandas as pd
from datetime import date, timedelta
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIG ---
st.set_page_config(page_title="PatiLog", page_icon="🐾", layout="wide")

# --- MOBILE CSS TWEAKS ---
# This removes top padding and makes cards look better on mobile
st.markdown("""
<style>
    .stApp {background-color: #0E1117;}
    .block-container {padding-top: 2rem;} 
    div[data-testid="stMetricValue"] {font-size: 1.2rem;}
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

# --- PAGE 1: CARD VIEW (Mobile Friendly) ---
if menu == "Genel Bakış (Kartlar)":
    st.header("🐶🐱 Evcil Hayvanlarım")
    
    if not df.empty:
        # Sort by Date
        if "Sonraki Tarih" in df.columns:
            df["Sonraki Tarih"] = pd.to_datetime(df["Sonraki Tarih"], format="%Y-%m-%d", errors='coerce')
            df = df.sort_values(by="Sonraki Tarih")
        
        # Create Cards
        for index, row in df.iterrows():
            pet_type = "🐶" if "Köpek" in str(row.get("Pet İsmi", "")) else "🐱" if "Kedi" in str(row.get("Pet İsmi", "")) else "🐾"
            
            # Card Container
            with st.container(border=True):
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.subheader(f"{pet_type} {row['Pet İsmi']}")
                    st.write(f"**İşlem:** {row['Aşı Tipi']}")
                    st.caption(f"Kilo: {row['Kilo (kg)']} kg")
                with c2:
                    due_date = row['Sonraki Tarih']
                    if pd.notnull(due_date):
                        days_left = (due_date.date() - date.today()).days
                        date_str = due_date.strftime('%d.%m.%Y')
                        
                        if days_left < 7:
                            st.error(f"{days_left} Gün!")
                            st.caption(date_str)
                        elif days_left < 30:
                            st.warning(f"{days_left} Gün")
                            st.caption(date_str)
                        else:
                            st.success(date_str)
    else:
        st.info("Henüz kayıt yok.")

# --- PAGE 2: TABLE VIEW (For Deletion) ---
elif menu == "Düzenle / Sil":
    st.header("📝 Kayıt Yönetimi")
    st.caption("Silmek istediğiniz satırları seçip alttaki butona basın.")
    
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
            "Kilo (kg)": st.column_config.NumberColumn("Kg", format="%.1f", disabled=True),
            "Uygulama Tarihi": st.column_config.DateColumn("Yapıldı", format="DD.MM.YYYY", disabled=True)
        }

        edited_df = st.data_editor(df, column_config=column_config, hide_index=True, use_container_width=True)

        rows_to_delete = edited_df[edited_df["Sil"] == True]
        if not rows_to_delete.empty:
            st.write("")
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

        # Updated Vaccine List
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

        # THE NOTIFICATION PREVIEW
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
