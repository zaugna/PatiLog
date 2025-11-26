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

# --- HELPER: GOOGLE CALENDAR LINK ---
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

# ICS HEADER (Strict Compliance)
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
            
            # Logic: Alert if within next 7 days
            if 0 <= days_left <= 7:
                alerts_found = True
                pet = row["Pet İsmi"]
                vaccine = row["Aşı Tipi"]
                event_title = f"{pet} - {vaccine}"
                
                # 1. Google Link
                gcal_link = create_gcal_link(event_title, due_date)
                
                # 2. Add to ICS (Strict UTC Timestamp)
                dt_start = due_date.strftime("%Y%m%d")
                dt_end = (due_date + timedelta(days=1)).strftime("%Y%m%d")
                # FIX: Use UTC now time for the stamp
                now_str = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
                unique_id = str(uuid.uuid4())
                
                ics_lines.append("BEGIN:VEVENT")
                ics_lines.append(f"UID:{unique_id}")
                ics_lines.append(f"DTSTAMP:{now_str}")
                ics_lines.append(f"DTSTART;VALUE=DATE:{dt_start}")
                ics_lines.append(f"DTEND;VALUE=DATE:{dt_end}")
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

# Close ICS
ics_lines.append("END:VCALENDAR")
ics_full_text = "\r\n".join(ics_lines)

email_html_content += "</ul><p><small>iOS: Ekteki dosyaya tıklayıp 'Hepsini Ekle' diyebilirsiniz.</small></p>"

# --- SEND EMAIL ---
if alerts_found:
    print("Sending email...")
    
    msg = MIMEMultipart()
    msg['Subject'] = "🔔 PatiLog: Aşı Hatırlatması"
    msg['From'] = SENDER_EMAIL
    msg['To'] = ", ".join(RECEIVER_EMAILS)
    
    msg.attach(MIMEText(email_html_content, 'html'))
    
    # ATTACHMENT HANDLING
    part = MIMEBase('text', 'calendar', method='PUBLISH', name='patilog.ics')
    part.set_payload(ics_full_text.encode('utf-8'))
    encoders.encode_base64(part)
    
    # iOS Magic Headers
    part.add_header('Content-Description', 'patilog.ics')
    part.add_header('Content-Disposition', 'attachment; filename="patilog.ics"')
    part.add_header('Content-Type', 'text/calendar; charset="utf-8"; name="patilog.ics"')
    
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
