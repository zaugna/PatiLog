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
import hashlib

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
    return str(text).replace("\n", " ").replace("\r", " ").replace(";", "").replace(",", " ").strip()

# --- HELPER: GOOGLE LINK ---
def create_gcal_link(title, date_obj):
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

# --- HELPER: SEND SINGLE EMAIL ---
def send_alert_email(pet, vaccine, due_date_obj, days_left):
    print(f"Preparing email for: {pet} - {vaccine}...")
    
    # 1. Prepare Data
    event_title = f"{pet} - {vaccine}"
    due_date_str = due_date_obj.strftime("%d.%m.%Y")
    gcal_link = create_gcal_link(event_title, due_date_obj)
    urgency = "⚠️" if days_left > 3 else "🚨"
    
    # 2. Build HTML Body
    html_body = f"""
    <h3>{urgency} PatiLog Hatırlatması</h3>
    <p><strong>{pet}</strong> için <strong>{vaccine}</strong> zamanı geldi.</p>
    <ul>
        <li>Tarih: {due_date_str}</li>
        <li>Kalan Gün: {days_left}</li>
    </ul>
    <p>
        <a href="{gcal_link}" style="background-color: #4285F4; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px;">Google Takvime Ekle</a>
    </p>
    <p><small>iOS kullanıcıları ekteki dosyaya tıklayarak takvime ekleyebilir.</small></p>
    """

    # 3. Build Single-Event ICS
    dt_start = due_date_obj.strftime("%Y%m%dT090000")
    dt_end = due_date_obj.strftime("%Y%m%dT091500")
    now_str = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    
    # Consistent UID based on Pet+Vaccine+Date
    uid_raw = f"{pet}-{vaccine}-{due_date_str}"
    unique_id = hashlib.md5(uid_raw.encode()).hexdigest() + "@patilog"

    ics_content = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//PatiLog//Single Event//TR",
        "METHOD:PUBLISH",
        "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        f"DTSTART:{dt_start}",
        f"DTEND:{dt_end}",
        f"DTSTAMP:{now_str}",
        f"UID:{unique_id}",
        f"SUMMARY:{event_title}",
        "DESCRIPTION:PatiLog Aşı Hatırlatması",
        "STATUS:CONFIRMED",
        "TRANSP:OPAQUE",
        "END:VEVENT",
        "END:VCALENDAR"
    ]
    ics_text = "\r\n".join(ics_content)

    # 4. Construct Email Message
    msg = MIMEMultipart()
    msg['Subject'] = f"{urgency} {pet}: {vaccine} Hatırlatması"
    msg['From'] = SENDER_EMAIL
    msg['To'] = ", ".join(RECEIVER_EMAILS)
    msg.add_header('Content-Class', 'urn:content-classes:calendarmessage')

    msg.attach(MIMEText(html_body, 'html'))

    # 5. Attach ICS (As Plain Text UTF-8)
    attachment = MIMEText(ics_text, 'calendar; method=PUBLISH', 'utf-8')
    attachment.add_header('Content-Disposition', 'attachment; filename="invite.ics"')
    attachment.add_header('Content-Class', 'urn:content-classes:calendarmessage')
    msg.attach(attachment)

    # 6. Send
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAILS, msg.as_string())
        print(f"✅ Sent email for {pet} - {vaccine}")
    except Exception as e:
        print(f"❌ Failed to send for {pet}: {e}")

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
                pet = clean_text(row["Pet İsmi"])
                vaccine = clean_text(row["Aşı Tipi"])
                
                # Send IMMEDIATE individual email
                send_alert_email(pet, vaccine, due_date_obj, days_left)
                
        except Exception as e:
            print(f"Skipping row: {e}")
