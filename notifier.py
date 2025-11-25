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
json_creds = os.environ["GCP_CREDENTIALS"] # We will store this in GitHub Secrets
creds_dict = json.loads(json_creds)
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
client = gspread.authorize(creds)
sheet = client.open("PatiLog_DB").sheet1

# 2. Load Data
data = sheet.get_all_records()
df = pd.DataFrame(data)

# 3. Email Settings
SENDER_EMAIL = os.environ["EMAIL_USER"]
SENDER_PASSWORD = os.environ["EMAIL_PASS"]
# You mentioned sending to yourself AND your wife. We split by comma if multiple.
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
            # Try parsing multiple formats just in case
            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            except:
                due_date = datetime.strptime(due_date_str, "%d.%m.%Y").date()

            # Check if due in exactly 7 days
            days_left = (due_date - today).days
            
            if days_left == 7:
                alerts_found = True
                pet = row["Pet İsmi"]
                vaccine = row["Aşı Tipi"]
                msg = f"⚠️ {pet} için {vaccine} zamanı yaklaşıyor! (Tarih: {due_date_str})\n"
                email_body += msg
                print(msg)
                
        except Exception as e:
            print(f"Skipping row due to error: {e}")

# --- SEND EMAIL ---
if alerts_found:
    print("Alerts found! Sending email...")
    
    msg = MIMEText(f"Merhaba,\n\nAşağıdaki aşıların zamanı yaklaşıyor (7 gün kaldı):\n\n{email_body}\n\nLütfen randevu almayı unutmayın.\n\n- PatiLog Botu 🐾")
    msg['Subject'] = "🔔 PatiLog Hatırlatıcısı"
    msg['From'] = SENDER_EMAIL
    msg['To'] = ", ".join(RECEIVER_EMAILS)

    try:
        # Connect to Gmail SMTP
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAILS, msg.as_string())
        print("✅ Email sent successfully!")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
else:
    print("No vaccines due in exactly 7 days.")
