import pandas as pd
from datetime import date, timedelta, datetime
import gspread
from google.oauth2.service_account import Credentials
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
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

# --- HELPER: CLEAN TEXT ---
def clean_text(text):
    if not text: return ""
    # Remove dangerous characters for ICS
    return str(text).replace("\n", " ").replace("\r", " ").replace(";", "").replace(",", " ")

# --- HELPER: GOOGLE LINK ---
def create_gcal_link(title, date_obj):
    date_str = date_obj.strftime("%Y%m%d")
    next_day_str = (date_obj + timedelta(days=1)).strftime("%Y%m%d")
    base_url = "https://www.google.com/calendar/render?action=TEMPLATE"
    params = {
        "text": title,
        "dates": f"{date_str}/{next_day_str}",
        "details": "Hatırlatma: PatiLog",
        "sf": "true",
        "output": "xml"
    }
    return base_url + "&" + urllib.parse.urlencode(params)

# --- LOGIC ---
today = date.today()
print(f"--- Running PatiLog Check for {today} ---")

email_html_content = "<h3>🐾 PatiLog Aşı Hatırlatması</h3><ul>"
alerts_found = False

# ICS HEADER (Strict RFC 5545 Compliance)
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
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            except:
                due_date = datetime.strptime(due_date_str, "%d.%m.%Y").date()

            days_left = (due_date - today).days
            
            if 0 <= days_left <= 7:
                alerts_found = True
                pet = clean_text(row["Pet İsmi"])
                vaccine = clean_text(row["Aşı Tipi"])
                event_title = f"{pet} - {vaccine}"
                
                # Links
                gcal_link = create_gcal_link(event_title, due_date)
                
                # ICS Event Construction
                dt_start = due_date.strftime("%Y%m%d")
                dt_end = (due_date + timedelta(days=1)).strftime("%Y%m%d")
                now_str = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
                unique_id = str(uuid.uuid4()) + "@patilog"
                
                ics_lines.append("BEGIN:VEVENT")
                ics_lines.append(f"DTSTART;VALUE=DATE:{dt_start}")
                ics_lines.append(f"DTEND;VALUE=DATE:{dt_end}")
                ics_lines.append(f"DTSTAMP:{now_str}")
                ics_lines.append(f"UID:{unique_id}")
                ics_lines.append(f"SUMMARY:{event_title}")
                ics_lines.append("DESCRIPTION:PatiLog Aşı Hatırlatması")
                ics_lines.append("STATUS:CONFIRMED")
                ics_lines.append("TRANSP:TRANSPARENT")
                ics_lines.append("END:VEVENT")
                
                urgency = "⚠️" if days_left > 3 else "🚨"
                email_html_content += f"""
                <li style="margin-bottom: 15px;">
                    <strong>{urgency} {pet} - {vaccine}</strong><br>
                    Tarih: {due_date_str}<br>
                    <a href="{gcal_link}">Google Takvime Ekle</a>
                </li>
                """
                print(f"Alert: {pet} - {vaccine}")
                
        except Exception as e:
            print(f"Skipping row: {e}")

ics_lines.append("END:VCALENDAR")

# CRITICAL FIX 1: Join with CRLF (\r\n) strictly
ics_full_text = "\r\n".join(ics_lines)

email_html_content += "</ul>"

# --- SEND EMAIL (iOS Optimized Structure) ---
if alerts_found:
    print("Sending email with iOS-Optimized Inline Calendar...")
    
    msg = MIMEMultipart('mixed') # 'mixed' allows attachments + inline
    msg['Subject'] = "🔔 PatiLog: Aşı Hatırlatması"
    msg['From'] = SENDER_EMAIL
    msg['To'] = ", ".join(RECEIVER_EMAILS)
    
    # CRITICAL FIX 2: Set Content-Class on the main header
    msg.add_header('Content-Class', 'urn:content-classes:calendarmessage')

    # Part 1: The HTML Body
    msg.attach(MIMEText(email_html_content, 'html'))
    
    # Part 2: The Calendar File
    # CRITICAL FIX 3: Use 'inline' disposition so iOS renders it immediately
    part = MIMEBase('text', 'calendar', method='PUBLISH', name='patilog.ics')
    part.set_payload(ics_full_text.encode('utf-8'))
    encoders.encode_base64(part)
    
    part.add_header('Content-Description', 'patilog.ics')
    part.add_header('Content-Class', 'urn:content-classes:calendarmessage')
    part.add_header('Content-Type', 'text/calendar; charset="utf-8"; method=PUBLISH')
    # 'inline' forces the calendar UI to appear inside the mail app
    part.add_header('Content-Disposition', 'inline; filename="patilog.ics"')
    
    msg.attach(part)

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAILS, msg.as_string())
        print("✅ Email sent successfully!")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
else:
    print("No vaccines due.")
