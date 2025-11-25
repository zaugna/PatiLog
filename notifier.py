import pandas as pd
from datetime import date, timedelta, datetime
import gspread
from google.oauth2.service_account import Credentials
import smtplib
from email.mime.text import MIMEText
import os
import json

# --- SETUP ---
# 1. Connect to Database
json_creds = os.environ["GCP_CREDENTIALS"]
creds_dict = json.loads(json_creds)
# Drive scope added to fix the 403 error
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
client = gspread.authorize(creds)
sheet = client.open("PatiLog_DB").sheet1

# 2. Load Data
data = sheet.get_all_records()
df = pd.DataFrame(data)

# 3. Email Settings
SENDER_EMAIL = os.environ["EMAIL_USER"]
SENDER_PASSWORD = os.environ["EMAIL_PASS"]
RECEIVER_EMAILS = os.environ["EMAIL_TO"].split(",") 

# --- LOGIC ---
today = date.today()
print(f"--- Running PatiLog Check for {today} ---")

email_body = ""
alerts_found = False

if not df.empty and "Sonraki Tarih" in df.columns:
    for index, row in df.iterrows():
        try:
            # Parse Date
            due_date_str = str(row["Sonraki Tarih"])
            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            except:
                due_date = datetime.strptime(due_date_str, "%d.%m.%Y").date()

            # Check days remaining
            days_left = (due_date - today).days
            
            # LOGIC CHANGE: Alert if within the next 7 days (inclusive)
            if 0 <= days_left <= 7:
                alerts_found = True
                pet = row["Pet İsmi"]
                vaccine = row["Aşı Tipi"]
                
                urgency = "⚠️" if days_left > 3 else "🚨"
                msg = f"{urgency} {pet} - {vaccine}: {days_left} gün kaldı ({due_date_str})\n"
                email_body += msg
                print(msg)
                
        except Exception as e:
            print(f"Skipping row due to error: {e}")

# --- SEND EMAIL ---
if alerts_found:
    print("Alerts found! Sending email...")
    
    msg = MIMEText(f"Merhaba,\n\nAşağıdaki aşıların zamanı geldi veya yaklaşıyor:\n\n{email_body}\n\nLütfen randevu almayı unutmayın.\n\n- PatiLog Botu 🐾")
    msg['Subject'] = "🔔 PatiLog: Aşı Hatırlatması"
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
    print("No vaccines due in the next 7 days.")
