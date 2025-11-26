import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIG ---
st.set_page_config(page_title="PatiLog", page_icon="🐾", layout="wide")

# --- CSS: DARK MODE & UI POLISH ---
st.markdown("""
<style>
    /* 1. Main Background */
    .stApp { background-color: #0E1117; }
    
    /* 2. Text Colors */
    h1, h2, h3, h4, h5, h6, p, div, span, li, label { color: #E0E0E0 !important; }
    
    /* 3. Sidebar */
    [data-testid="stSidebar"] { background-color: #262730; }
    
    /* 4. Dropdowns & Popups */
    div[data-baseweb="popover"], div[data-baseweb="menu"], div[role="listbox"] {
        background-color: #262730 !important;
    }
    div[data-baseweb="select"] > div {
        background-color: #262730 !important;
        color: white !important;
        border-color: #4C4C4C !important;
    }
    li[role="option"] {
        background-color: #262730 !important;
        color: white !important;
    }
    li[role="option"]:hover {
        background-color: #FF4B4B !important;
    }

    /* 5. Inputs */
    input {
        color: white !important;
        background-color: #262730 !important;
    }

    /* 6. Cards */
    .streamlit-expanderHeader {
        background-color: #262730 !important;
        color: white !important;
        border: 1px solid #4C4C4C;
    }
    div[data-testid="stExpander"] {
        border: none;
        background-color: transparent;
    }
    
    /* 7. Plotly Chart Background Fix */
    .js-plotly-plot .plotly .main-svg {
        background-color: transparent !important;
    }
    
    /* 8. Table Background */
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

# --- SIDEBAR ---
st.sidebar.title("🐾 PatiLog")
# REMOVED: "Düzenle / Sil" from the menu list
menu = st.sidebar.radio("Menü", ["Genel Bakış (Kartlar)", "Yeni Kayıt Ekle"])
df = load_data()

# --- PAGE 1: CARDS & NEW PLOTLY CHART ---
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
                status_text = f"{days_left} gün!"
            elif days_left < 30:
                status_emoji = "⚠️"
                status_text = f"{days_left} gün"

            # CARD
            with st.expander(f"{status_emoji} {icon} {pet}  |  {status_text}"):
                
                # METRICS
                m1, m2, m3 = st.columns(3)
                latest_weight = pet_df.iloc[-1]["Kilo (kg)"] if "Kilo (kg)" in pet_df.columns else "?"
                m1.metric("Son Kilo", f"{latest_weight} kg")
                m2.metric("Sıradaki İşlem", pet_df.iloc[0]["Aşı Tipi"])
                m3.metric("Tarih", closest_date.strftime('%d.%m.%Y'))
                
                st.write("---")
                
                # --- NEW PLOTLY CHART ---
                if "Kilo (kg)" in pet_df.columns and "Uygulama Tarihi" in pet_df.columns:
                    st.caption("📉 Kilo Değişimi")
                    chart_data = pet_df[["Uygulama Tarihi", "Kilo (kg)"]].copy()
                    chart_data["Uygulama Tarihi"] = pd.to_datetime(chart_data["Uygulama Tarihi"], errors='coerce')
                    chart_data = chart_data.dropna().sort_values("Uygulama Tarihi")
                    
                    if not chart_data.empty:
                        fig = go.Figure()
                        
                        fig.add_trace(go.Scatter(
                            x=chart_data["Uygulama Tarihi"], 
                            y=chart_data["Kilo (kg)"],
                            mode='lines+markers',
                            line=dict(color='#FF4B4B', width=3, shape='spline'),
                            marker=dict(size=8, color='#0E1117', line=dict(color='#FF4B4B', width=2)),
                            fill='tozeroy',
                            fillcolor='rgba(255, 75, 75, 0.1)',
                            name='Kilo'
                        ))

                        fig.update_layout(
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            margin=dict(l=0, r=0, t=10, b=0),
                            height=250,
                            xaxis=dict(showgrid=False, showline=False, tickformat="%d.%m"),
                            yaxis=dict(showgrid=True, gridcolor='#262730', zeroline=False),
                            hovermode="x unified"
                        )
                        
                        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

                st.write("---")
                st.caption("📜 Geçmiş İşlemler")
                display_df = pet_df[["Aşı Tipi", "Uygulama Tarihi", "Sonraki Tarih"]].copy()
                display_df["Uygulama Tarihi"] = pd.to_datetime(display_df["Uygulama Tarihi"]).dt.strftime('%d.%m.%Y')
                display_df["Sonraki Tarih"] = pd.to_datetime(display_df["Sonraki Tarih"]).dt.strftime('%d.%m.%Y')
                
                st.dataframe(display_df, hide_index=True, use_container_width=True)

    else:
        st.info("Kayıt yok.")

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
