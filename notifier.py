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
import hashlib # <--- NEW: To create consistent IDs

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
    # Google Calendar link also updated to 09:00 AM
    start_str = date_obj.strftime("%Y%m%dT090000")
    end_str = date_obj.strftime("%Y%m%dT091500") # 15 min duration
    
    base_url = "https://www.google.com/calendar/render?action=TEMPLATE"
    params = {
        "text": title,
        "dates": f"{start_str}/{end_str}",
        "details": "Hatırlatma: PatiLog",
        "sf": "true",
        "output": "xml"
    }
    return base_url + "&" + urllib.parse.urlencode(params)

# --- HELPER: GENERATE CONSISTENT UID ---
def generate_uid(pet, vaccine, due_date):
    # Creates a unique ID that stays the same if we run the script twice
    raw = f"{pet}-{vaccine}-{due_date}"
    return hashlib.md5(raw.encode()).hexdigest() + "@patilog"

# --- LOGIC ---
today = date.today()
print(f"--- Running PatiLog Check for {today} ---")

email_html_content = "<h3>🐾 PatiLog Aşı Hatırlatması</h3><ul>"
alerts_found = False

# ICS HEADER
ics_lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//PatiLog//Vaccine Check//TR",
    "METHOD:PUBLISH",
    "CALSCALE:GREGORIAN"
]

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
                alerts_found = True
                pet = clean_text(row["Pet İsmi"])
                vaccine = clean_text(row["Aşı Tipi"])
                event_title = f"{pet} - {vaccine}"
                
                # Links
                gcal_link = create_gcal_link(event_title, due_date_obj)
                
                # ICS Event Construction (TIMED EVENT)
                # 09:00 AM to 09:15 AM local time
                dt_start = due_date_obj.strftime("%Y%m%dT090000")
                dt_end = due_date_obj.strftime("%Y%m%dT091500")
                now_str = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
                
                # Consistent UID
                unique_id = generate_uid(pet, vaccine, due_date_str)
                
                ics_lines.append("BEGIN:VEVENT")
                ics_lines.append(f"DTSTART:{dt_start}")
                ics_lines.append(f"DTEND:{dt_end}")
                ics_lines.append(f"DTSTAMP:{now_str}")
                ics_lines.append(f"UID:{unique_id}")
                ics_lines.append(f"SUMMARY:{event_title}")
                ics_lines.append("DESCRIPTION:PatiLog Aşı Hatırlatması")
                ics_lines.append("STATUS:CONFIRMED")
                ics_lines.append("TRANSP:OPAQUE") # Opaque means "Busy" time, forcing calendar attention
                ics_lines.append("END:VEVENT")
                
                urgency = "⚠️" if days_left > 3 else "🚨"
                email_html_content += f"""
                <li style="margin-bottom: 15px;">
                    <strong>{urgency} {pet} - {vaccine}</strong><br>
                    Tarih: {due_date_str} (09:00)<br>
                    <a href="{gcal_link}">Google Takvime Ekle</a>
                </li>
                """
                print(f"Alert: {pet} - {vaccine}")
                
        except Exception as e:
            print(f"Skipping row: {e}")

ics_lines.append("END:VCALENDAR")
ics_full_text = "\r\n".join(ics_lines)

email_html_content += "</ul>"

# --- SEND EMAIL ---
if alerts_found:
    print("Sending email with Timed Event ICS...")
    
    msg = MIMEMultipart()
    msg['Subject'] = "🔔 PatiLog: Aşı Hatırlatması"
    msg['From'] = SENDER_EMAIL
    msg['To'] = ", ".join(RECEIVER_EMAILS)
    msg.add_header('Content-Class', 'urn:content-classes:calendarmessage')
    
    # 1. HTML Body
    msg.attach(MIMEText(email_html_content, 'html'))
    
    # 2. ICS Attachment (PlainText, UTF-8, Method=PUBLISH)
    ics_attachment = MIMEText(ics_full_text, 'calendar; method=PUBLISH', 'utf-8')
    ics_attachment.add_header('Content-Disposition', 'attachment; filename="patilog.ics"')
    ics_attachment.add_header('Content-Class', 'urn:content-classes:calendarmessage')
    
    msg.attach(ics_attachment)

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAILS, msg.as_string())
        print("✅ Email sent successfully!")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
else:
    print("No vaccines due.")
