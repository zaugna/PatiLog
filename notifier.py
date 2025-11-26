import pandas as pd
from datetime import date, timedelta, datetime
import gspread
from google.oauth2.service_account import Credentials
import smtplib
from email.mime.text import MIMEText
import os
import json
import urllib.parse # <--- NEW: For creating safe URLs

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

# --- HELPER: GENERATE GOOGLE CALENDAR LINK ---
def create_gcal_link(title, date_obj):
    # Google Calendar expects dates in YYYYMMDD format
    date_str = date_obj.strftime("%Y%m%d")
    # Events need a start and end date (we make it an all-day event by using the same day + 1)
    next_day_str = (date_obj + timedelta(days=1)).strftime("%Y%m%d")
    
    base_url = "https://www.google.com/calendar/render?action=TEMPLATE"
    params = {
        "text": title,
        "dates": f"{date_str}/{next_day_str}",
        "details": "Hatırlatma: PatiLog Evcil Hayvan Takip Sistemi",
        "sf": "true",
        "output": "xml"
    }
    return base_url + "&" + urllib.parse.urlencode(params)

# --- LOGIC ---
today = date.today()
print(f"--- Running PatiLog Check for {today} ---")

# We will build an HTML email now (to support clickable links)
email_html_content = "<h3>🐾 PatiLog Aşı Hatırlatması</h3><ul>"
alerts_found = False

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
                
                # Create the Magic Link
                event_title = f"{pet} - {vaccine} Aşısı"
                gcal_link = create_gcal_link(event_title, due_date)
                
                urgency = "⚠️" if days_left > 3 else "🚨"
                
                # Add list item to HTML
                email_html_content += f"""
                <li style="margin-bottom: 15px;">
                    <strong>{urgency} {pet} - {vaccine}</strong><br>
                    Kalan Süre: {days_left} gün ({due_date_str})<br>
                    <a href="{gcal_link}" style="background-color: #4285F4; color: white; padding: 5px 10px; text-decoration: none; border-radius: 4px; font-size: 12px;">📅 Takvime Ekle</a>
                </li>
                """
                print(f"Alert: {pet} - {vaccine}")
                
        except Exception as e:
            print(f"Skipping row: {e}")

email_html_content += "</ul><p><small>PatiLog Botu Tarafından Gönderilmiştir.</small></p>"

# --- SEND EMAIL ---
if alerts_found:
    print("Sending email...")
    
    # Switch MIME type to HTML
    msg = MIMEText(email_html_content, 'html')
    msg['Subject'] = "🔔 PatiLog: Aşı Hatırlatması (+Takvim Linki)"
    msg['From'] = SENDER_EMAIL
    msg['To'] = ", ".join(RECEIVER_EMAILS)

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAILS, msg.as_string())
        print("✅ Email sent successfully!")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
else:
    print("No vaccines due.")
