import pandas as pd
from datetime import date, timedelta, datetime
import gspread
from google.oauth2.service_account import Credentials
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart # <--- NEW: For attachments
from email.mime.base import MIMEBase # <--- NEW: For file handling
from email import encoders # <--- NEW: For encoding the file
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

# We will build the ICS file content string line by line
ics_content = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//PatiLog//Vaccine Check//EN"
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
                
                # 2. Add to ICS Content (For Apple/Outlook)
                dt_start = due_date.strftime("%Y%m%d")
                dt_end = (due_date + timedelta(days=1)).strftime("%Y%m%d")
                
                ics_content.append("BEGIN:VEVENT")
                ics_content.append(f"SUMMARY:{event_title}")
                ics_content.append(f"DTSTART;VALUE=DATE:{dt_start}")
                ics_content.append(f"DTEND;VALUE=DATE:{dt_end}")
                ics_content.append("DESCRIPTION:PatiLog Hatırlatması")
                ics_content.append("END:VEVENT")
                
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

# Close the ICS file format
ics_content.append("END:VCALENDAR")
ics_text = "\n".join(ics_content)

email_html_content += "</ul><p><small>Apple/iOS kullanıcıları ekteki dosyaya tıklayarak takvime ekleyebilir.</small></p>"

# --- SEND EMAIL (MULTIPART) ---
if alerts_found:
    print("Sending email with attachment...")
    
    # Create the complex email object
    msg = MIMEMultipart()
    msg['Subject'] = "🔔 PatiLog: Aşı Hatırlatması"
    msg['From'] = SENDER_EMAIL
    msg['To'] = ", ".join(RECEIVER_EMAILS)
    
    # Attach the HTML body
    msg.attach(MIMEText(email_html_content, 'html'))
    
    # Create the Attachment
    part = MIMEBase('text', 'calendar')
    part.set_payload(ics_text)
    encoders.encode_base64(part)
    part.add_header(
        'Content-Disposition',
        f'attachment; filename=patilog_takvim.ics',
    )
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
