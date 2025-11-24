import streamlit as st
import pandas as pd
from datetime import date, timedelta
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIG ---
st.set_page_config(page_title="PatiLog", page_icon="🐾", layout="wide")

# --- DATABASE CONNECTION ---
# We use ttl=0 to force it to check for new connections often to avoid stale data
@st.cache_resource(ttl=60)
def get_db():
    creds_dict = st.secrets["gcp_service_account"]
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open("PatiLog_DB")

# --- DATA FUNCTIONS ---
def load_data():
    try:
        sh = get_db()
        worksheet = sh.get_worksheet(0)
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        return df
    except Exception:
        return pd.DataFrame()

def save_entry(pet_name, vaccine, date_applied, next_due_date, weight):
    sh = get_db()
    worksheet = sh.get_worksheet(0)
    
    # Headers check
    if not worksheet.get_all_values():
        worksheet.append_row(["Pet İsmi", "Aşı Tipi", "Uygulama Tarihi", "Sonraki Tarih", "Kilo (kg)"])
    
    worksheet.append_row([pet_name, vaccine, str(date_applied), str(next_due_date), weight])

def delete_rows(indexes_to_keep):
    """
    Rewrites the google sheet with only the rows we want to keep.
    This is safer than deleting by index which can shift during operation.
    """
    sh = get_db()
    worksheet = sh.get_worksheet(0)
    
    # Get all data as dataframe
    df = load_data()
    
    # Filter dataframe
    if not df.empty:
        # We keep rows that are in the 'indexes_to_keep' list
        # We adjust for 0-based index vs 1-based sheet
        df_cleaned = df.iloc[indexes_to_keep]
        
        # Clear Sheet
        worksheet.clear()
        
        # Write Headers
        worksheet.append_row(["Pet İsmi", "Aşı Tipi", "Uygulama Tarihi", "Sonraki Tarih", "Kilo (kg)"])
        
        # Write Data
        if not df_cleaned.empty:
            worksheet.append_rows(df_cleaned.values.tolist())

# --- SIDEBAR ---
st.sidebar.header("🐾 PatiLog")
menu = st.sidebar.radio("Menü", ["Genel Bakış ve Düzenleme", "Yeni Kayıt Ekle"])

# Always load fresh data
df = load_data()

# --- PAGE 1: GENEL BAKIŞ & DELETE ---
if menu == "Genel Bakış ve Düzenleme":
    st.header("📊 Genel Durum ve Düzenleme")
    
    if not df.empty:
        # Pre-processing for display
        if "Sonraki Tarih" in df.columns:
            df["Sonraki Tarih"] = pd.to_datetime(df["Sonraki Tarih"], format="%Y-%m-%d", errors='coerce')
            df = df.sort_values(by="Sonraki Tarih")
        
        # Add a "Sil" column for the editor (Starts as False)
        df["Sil"] = False
        
        # Configure columns for the editor
        column_config = {
            "Sil": st.column_config.CheckboxColumn("Sil?", help="Silmek için işaretleyin", default=False),
            "Pet İsmi": st.column_config.TextColumn("Evcil Hayvan", disabled=True),
            "Aşı Tipi": st.column_config.TextColumn("İşlem", disabled=True),
            "Sonraki Tarih": st.column_config.DateColumn("Sonraki Randevu", format="DD.MM.YYYY", disabled=True),
            "Kilo (kg)": st.column_config.NumberColumn("Kilo", format="%.1f kg", disabled=True),
            "Uygulama Tarihi": st.column_config.DateColumn("Yapılan Tarih", format="DD.MM.YYYY", disabled=True)
        }

        # EDITABLE DATA FRAME
        st.info("Kayıt silmek için tablodaki 'Sil' kutucuğunu işaretleyin ve alttaki butona basın.")
        edited_df = st.data_editor(
            df,
            column_config=column_config,
            hide_index=True,
            use_container_width=True,
            num_rows="fixed" # User cannot add rows here, only check boxes
        )

        # DELETE BUTTON LOGIC
        # We check which rows have 'Sil' == True in the edited version
        rows_to_delete = edited_df[edited_df["Sil"] == True]
        
        if not rows_to_delete.empty:
            st.write("")
            if st.button(f"🗑️ Seçili {len(rows_to_delete)} Kaydı Sil", type="primary"):
                # Find indexes of rows where Sil is FALSE (The ones to keep)
                # We use the original index from the loaded dataframe
                indexes_to_keep = edited_df[edited_df["Sil"] == False].index.tolist()
                
                try:
                    with st.spinner("Kayıtlar güncelleniyor..."):
                        delete_rows(indexes_to_keep)
                    st.success("Kayıtlar silindi!")
                    st.rerun() # Force Reload
                except Exception as e:
                    st.error(f"Silme hatası: {e}")

    else:
        st.info("Henüz kayıt bulunmuyor.")

# --- PAGE 2: YENI KAYIT ---
elif menu == "Yeni Kayıt Ekle":
    st.header("💉 Yeni Kayıt Girişi")

    col1, col2 = st.columns(2)
    
    with col1:
        # --- SMART PET SELECTOR ---
        # Get unique pet names
        existing_names = []
        if not df.empty and "Pet İsmi" in df.columns:
            existing_names = [x for x in df["Pet İsmi"].unique() if str(x).strip() != ""]
        
        # Add "Add New" option to the list
        options = existing_names + ["➕ Yeni Ekle..."]
        
        selected_option = st.selectbox("Evcil Hayvan", options)
        
        if selected_option == "➕ Yeni Ekle...":
            pet_name = st.text_input("Evcil Hayvan İsmi Giriniz")
        else:
            pet_name = selected_option # Use selected name

        vaccine = st.selectbox("İşlem Tipi", ["Karma (DHPP)", "Kuduz", "Bronşin", "Lösemi", "İç Parazit", "Dış Parazit", "Genel Kontrol"])
        weight = st.number_input("Güncel Kilo (kg)", min_value=0.0, step=0.1, format="%.1f")

    with col2:
        date_applied = st.date_input("Uygulama Tarihi", date.today())
        
        st.divider()
        st.write("📅 **Sonraki Tarih**")
        
        # Dropdown for Timing
        timing_choice = st.selectbox(
            "Hatırlatma Zamanı", 
            ["1 Ay Sonra", "2 Ay Sonra", "3 Ay Sonra", "6 Ay Sonra", "12 Ay Sonra", "📅 Manuel Tarih Seçimi"]
        )
        
        final_due_date = None
        
        if timing_choice == "📅 Manuel Tarih Seçimi":
            final_due_date = st.date_input("Tarih Seçiniz", min_value=date_applied)
        else:
            # Extract number from string (e.g., "3 Ay Sonra" -> 3)
            months = int(timing_choice.split(" ")[0])
            final_due_date = date_applied + timedelta(days=months*30)
            st.info(f"👉 Hedef Tarih: {final_due_date.strftime('%d.%m.%Y')}")

    st.write("")
    if st.button("Kaydet", type="primary", use_container_width=True):
        if pet_name:
            try:
                save_entry(pet_name, vaccine, date_applied, final_due_date, weight)
                st.success("✅ Kayıt eklendi! Tablo güncelleniyor...")
                # The Golden Fix: Force Rerun
                st.rerun() 
            except Exception as e:
                st.error(f"Hata: {e}")
        else:
            st.warning("Lütfen bir isim giriniz.")
