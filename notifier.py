import pandas as pd
from datetime import date, timedelta, datetime
import gspread
from google.oauth2.service_account import Credentials
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import json
import urllib.parse

# --- SETUP ---
json_creds = os.environ["GCP_CREDENTIALS"]
creds_dict = json.loads(json_creds)
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
client = gspread.authorize(creds)
sheet = client.open("PatiLog_DB").sheet1

# Load Data
data = sheet.get_all_records()
df = pd.DataFrame(data)

# Email Settings
SENDER_EMAIL = os.environ["EMAIL_USER"]
SENDER_PASSWORD = os.environ["EMAIL_PASS"]
RECEIVER_EMAILS = os.environ["EMAIL_TO"].split(",") 

# --- HELPER: CLEAN TEXT ---
def clean_text(text):
    if not text: return ""
    return str(text).strip()

# --- HELPER: GOOGLE CALENDAR LINK ---
def create_gcal_link(title, date_obj):
    # Set event for 09:00 AM Local Time
    start_str = date_obj.strftime("%Y%m%dT090000")
    end_str = date_obj.strftime("%Y%m%dT091500")
    
    base_url = "https://www.google.com/calendar/render?action=TEMPLATE"
    params = {
        "text": title,
        "dates": f"{start_str}/{end_str}",
        "details": "Hatırlatma: PatiLog Aşı Takibi",
        "sf": "true",
        "output": "xml"
    }
    return base_url + "&" + urllib.parse.urlencode(params)

# --- HELPER: SEND EMAIL ---
def send_alert_email(pet, vaccine, due_date_obj, days_left):
    print(f"Sending alert for: {pet} - {vaccine}...")
    
    pet_clean = clean_text(pet)
    vaccine_clean = clean_text(vaccine)
    event_title = f"{pet_clean} - {vaccine_clean}"
    due_date_str = due_date_obj.strftime("%d.%m.%Y")
    
    # Create the Magic Link
    gcal_link = create_gcal_link(event_title, due_date_obj)
    
    urgency = "⚠️" if days_left > 3 else "🚨"
    
    # Clean, Mobile-Friendly HTML Design
    html_body = f"""
    <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
        <h2 style="color: #d32f2f;">{urgency} PatiLog Hatırlatması</h2>
        <p style="font-size: 16px;">
            <strong>{pet_clean}</strong> için <strong>{vaccine_clean}</strong> zamanı geldi.
        </p>
        <div style="background-color: #f5f5f5; padding: 15px; border-radius: 8px; margin: 20px 0;">
            <p style="margin: 5px 0;">📅 <strong>Tarih:</strong> {due_date_str}</p>
            <p style="margin: 5px 0;">⏳ <strong>Kalan Gün:</strong> {days_left}</p>
        </div>
        <a href="{gcal_link}" style="
            background-color: #4285F4; 
            color: white; 
            padding: 12px 24px; 
            text-decoration: none; 
            border-radius: 5px; 
            font-weight: bold; 
            display: inline-block;">
            📅 Google Takvime Ekle
        </a>
        <p style="margin-top: 20px; font-size: 12px; color: #888;">
            Bu otomatik bir mesajdır. - PatiLog
        </p>
    </div>
    """

    msg = MIMEMultipart()
    msg['Subject'] = f"{urgency} {pet_clean}: {vaccine_clean}"
    msg['From'] = SENDER_EMAIL
    msg['To'] = ", ".join(RECEIVER_EMAILS)

    msg.attach(MIMEText(html_body, 'html'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAILS, msg.as_string())
        print(f"✅ Sent email for {pet_clean}")
    except Exception as e:
        print(f"❌ Failed to send: {e}")

# --- MAIN LOOP ---
today = date.today()
print(f"--- Running PatiLog Check for {today} ---")

if not df.empty and "Sonraki Tarih" in df.columns:
    for index, row in df.iterrows():
        try:
            due_date_str = str(row["Sonraki Tarih"])
            try:
                due_date_obj = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            except:
                due_date_obj = datetime.strptime(due_date_str, "%d.%m.%Y").date()

            days_left = (due_date_obj - today).days
            
            # Logic: Alert if within next 7 days
            if 0 <= days_left <= 7:
                pet = str(row["Pet İsmi"])
                vaccine = str(row["Aşı Tipi"])
                send_alert_email(pet, vaccine, due_date_obj, days_left)
                
        except Exception as e:
            print(f"Skipping row: {e}")
