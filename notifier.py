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
import uuid

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

# --- HELPER: CLEAN TEXT (Aggressive) ---
def clean_text(text):
    if not text: return ""
    # Ensure string, strip spaces
    s = str(text).strip()
    # Escape special ICS characters
    s = s.replace("\\", "\\\\").replace(";", "\;").replace(",", "\,")
    return s.replace("\n", " ")

# --- HELPER: GOOGLE LINK ---
def create_gcal_link(title, date_obj):
    # Google Link uses Local Time (09:00)
    start_str = date_obj.strftime("%Y%m%dT090000")
    end_str = date_obj.strftime("%Y%m%dT091500")
    base_url = "https://www.google.com/calendar/render?action=TEMPLATE"
    params = {
        "text": title,
        "dates": f"{start_str}/{end_str}",
        "details": "Hatırlatma: PatiLog",
        "sf": "true",
        "output": "xml"
    }
    return base_url + "&" + urllib.parse.urlencode(params)

# --- HELPER: SEND FILE ---
def send_file_email(pet, vaccine, due_date_obj, days_left):
    print(f"Preparing File for: {pet} - {vaccine}...")
    
    pet_clean = clean_text(pet)
    vaccine_clean = clean_text(vaccine)
    event_title = f"{pet_clean} - {vaccine_clean}"
    
    # 1. HTML Body
    due_date_str = due_date_obj.strftime("%d.%m.%Y")
    gcal_link = create_gcal_link(event_title, due_date_obj)
    urgency = "⚠️" if days_left > 3 else "🚨"
    
    html_body = f"""
    <h3>{urgency} PatiLog Hatırlatması</h3>
    <p><strong>{pet_clean}</strong> için <strong>{vaccine_clean}</strong> zamanı geldi.</p>
    <ul>
        <li>Tarih: {due_date_str}</li>
        <li>Kalan Gün: {days_left}</li>
    </ul>
    <p><a href="{gcal_link}">Google Takvime Ekle (Android/Web)</a></p>
    <p><small>iOS: Ekteki dosyayı açıp 'Add' (Ekle) diyebilirsiniz.</small></p>
    """

    # 2. Build ICS (UTC FIXED)
    # Turkey is UTC+3. So 09:00 TRT = 06:00 UTC.
    # We must use 'Z' to tell iOS this is absolute time.
    dt_start = due_date_obj.strftime("%Y%m%dT060000Z") 
    dt_end = due_date_obj.strftime("%Y%m%dT061500Z")
    now_str = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    
    uid = str(uuid.uuid4())
    
    # Description with explicit newlines handling
    description = f"{pet_clean} icin {vaccine_clean} asisi."

    ics_content = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//PatiLog//Vaccine Check//TR",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now_str}",
        f"DTSTART:{dt_start}",
        f"DTEND:{dt_end}",
        f"SUMMARY:{event_title}",
        f"DESCRIPTION:{description}",
        "STATUS:CONFIRMED",
        "TRANSP:OPAQUE",
        "END:VEVENT",
        "END:VCALENDAR"
    ]
    
    ics_text = "\r\n".join(ics_content)

    # 3. Construct Email
    msg = MIMEMultipart('mixed') 
    msg['Subject'] = f"{urgency} {pet_clean}: {vaccine_clean}"
    msg['From'] = SENDER_EMAIL
    msg['To'] = ", ".join(RECEIVER_EMAILS)

    # Body
    msg.attach(MIMEText(html_body, 'html'))

    # Attachment (Plain Text, explicitly UTF-8)
    attachment = MIMEText(ics_text, 'calendar; method=PUBLISH', 'utf-8')
    attachment.add_header('Content-Disposition', 'attachment', filename='invite.ics')
    msg.attach(attachment)

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAILS, msg.as_string())
        print(f"✅ Sent file for {pet_clean}")
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
            
            if 0 <= days_left <= 7:
                pet = str(row["Pet İsmi"])
                vaccine = str(row["Aşı Tipi"])
                send_file_email(pet, vaccine, due_date_obj, days_left)
                
        except Exception as e:
            print(f"Skipping row: {e}")
