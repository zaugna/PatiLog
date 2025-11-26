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
RECEIVER_EMAILS_LIST = os.environ["EMAIL_TO"].split(",") 

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

# --- HELPER: SEND INVITATION ---
def send_invitation_email(pet, vaccine, due_date_obj, days_left):
    print(f"Preparing Invitation for: {pet} - {vaccine}...")
    
    event_title = f"{pet} - {vaccine}"
    due_date_str = due_date_obj.strftime("%d.%m.%Y")
    gcal_link = create_gcal_link(event_title, due_date_obj)
    urgency = "⚠️" if days_left > 3 else "🚨"
    
    # 1. HTML Body
    html_body = f"""
    <h3>{urgency} PatiLog Hatırlatması</h3>
    <p><strong>{pet}</strong> için <strong>{vaccine}</strong> zamanı geldi.</p>
    <ul>
        <li>Tarih: {due_date_str}</li>
        <li>Saat: 09:00</li>
    </ul>
    <p><a href="{gcal_link}">Google Takvime Ekle</a></p>
    """

    # 2. Build The Invitation (Method: REQUEST)
    dt_start = due_date_obj.strftime("%Y%m%dT090000")
    dt_end = due_date_obj.strftime("%Y%m%dT091500")
    now_str = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    
    uid_raw = f"{pet}-{vaccine}-{due_date_str}"
    unique_id = hashlib.md5(uid_raw.encode()).hexdigest() + "@patilog"

    ics_content = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//PatiLog//Vaccine Check//TR",
        "METHOD:REQUEST", # <--- CHANGE 1: Request = Invitation
        "BEGIN:VEVENT",
        f"UID:{unique_id}",
        f"DTSTAMP:{now_str}",
        f"DTSTART:{dt_start}",
        f"DTEND:{dt_end}",
        f"SUMMARY:{event_title}",
        f"ORGANIZER;CN=PatiLog Bot:mailto:{SENDER_EMAIL}", # <--- CHANGE 2: Organizer is required
    ]
    
    # Add all receivers as attendees so the phone knows "This is for me"
    for email in RECEIVER_EMAILS_LIST:
        clean_email = email.strip()
        ics_content.append(f"ATTENDEE;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=FALSE;CN=Owner:mailto:{clean_email}")

    ics_content.extend([
        "DESCRIPTION:PatiLog Aşı Hatırlatması",
        "STATUS:CONFIRMED",
        "TRANSP:OPAQUE",
        "END:VEVENT",
        "END:VCALENDAR"
    ])
    
    ics_text = "\r\n".join(ics_content)

    # 3. Construct Email
    msg = MIMEMultipart('alternative') # <--- CHANGE 3: Alternative means "The calendar IS the email"
    msg['Subject'] = f"{urgency} {pet}: {vaccine} (Davet)"
    msg['From'] = SENDER_EMAIL
    msg['To'] = ", ".join(RECEIVER_EMAILS_LIST)

    # Part 1: HTML
    msg.attach(MIMEText(html_body, 'html'))

    # Part 2: Calendar
    # We use 'text/calendar' with method=REQUEST so mail clients render buttons
    ical_atch = MIMEText(ics_text, 'calendar; method=REQUEST', 'utf-8')
    ical_atch.add_header('Content-Class', 'urn:content-classes:calendarmessage')
    msg.attach(ical_atch)

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAILS_LIST, msg.as_string())
        print(f"✅ Sent invitation for {pet} - {vaccine}")
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
            
            if 0 <= days_left <= 7:
                pet = clean_text(row["Pet İsmi"])
                vaccine = clean_text(row["Aşı Tipi"])
                send_invitation_email(pet, vaccine, due_date_obj, days_left)
                
        except Exception as e:
            print(f"Skipping row: {e}")
