import calendar
import os
import datetime

from flask import Flask, redirect, url_for, session, render_template, request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials



from web_scraping import (
    list_emails_with_month,
    extract_order_details,
    get_deepest_text_payload, process_email_with_pdf, extract_trendyol_order_details, parse_email_date
)

app = Flask(__name__, static_folder='static')
app.secret_key = "your_secret_key"

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

CLIENT_SECRETS_FILE = "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

flow = Flow.from_client_secrets_file(
    CLIENT_SECRETS_FILE,
    scopes=SCOPES,
    redirect_uri='http://localhost:5000/callback'
)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login')
def login():
    authorization_url, state = flow.authorization_url()
    session["state"] = state
    return redirect(authorization_url)


@app.route('/callback')
def callback():
    try:
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials
        session["credentials"] = credentials_to_dict(credentials)

        with open('token.json', 'w') as token_file:
            token_file.write(credentials.to_json())

        return redirect(url_for('dashboard'))
    except Exception as e:
        return f"Error during callback: {str(e)}"


@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if "credentials" not in session:
        return redirect(url_for('index'))

    creds = Credentials(**session["credentials"])
    service = build('gmail', 'v1', credentials=creds)

    today = datetime.datetime.now()
    selected_year = today.year
    selected_month = today.month

    if request.method == 'POST':
        selected_month = int(request.form.get('month', selected_month))
        selected_year = int(request.form.get('year', selected_year))

    # Yıl aralığını tanımla (örneğin, mevcut yıl ve önceki 5 yıl)
    current_year = today.year
    years_back = 5
    all_years = list(range(current_year, current_year - years_back - 1, -1))

    # Trendyol ve genel sipariş e-postalarını al
    trendyol_keywords = ['siparişini aldık']
    general_keywords = ['sipariş']

    # Her iki tür sipariş için e-postaları al
    trendyol_emails, _ = list_emails_with_month(
        service,
        trendyol_keywords,
        selected_year,
        selected_month,
        query="from:info@trendyolmail.com"
    )

    other_emails, month_name = list_emails_with_month(
        service,
        general_keywords,
        selected_year,
        selected_month,
        query=f"({' OR '.join(general_keywords)})"
    )

    enriched_emails = []
    # Trendyol e-postalarını işle
    for email in trendyol_emails:
        msg_data = service.users().messages().get(
            userId='me',
            id=email['id']
        ).execute()
        payload = msg_data.get('payload', {})

        body_content = get_deepest_text_payload(payload)
        extracted = extract_trendyol_order_details(body_content)

        # Veriler gövdede yoksa PDF'i işle
        if extracted['order_id'] == "Trendyol Sipariş Numarası Bulunamadı":
            pdf_data = process_email_with_pdf(service, 'me', email['id'])
            if pdf_data['order_id'] != "Sipariş Numarası bulunamadı":
                extracted = pdf_data

        enriched_emails.append({
            'subject': email.get('subject', '(No Subject)'),
            'sender': email.get('sender', '(Unknown Sender)'),
            'date': email.get('date', '(Unknown Date)'),
            'total_amount': extracted['total_amount'],
            'order_id': extracted['order_id'],
            'source': 'Trendyol'
        })

    # Diğer e-postaları işle
    for email in other_emails:
        msg_data = service.users().messages().get(
            userId='me',
            id=email['id']
        ).execute()
        payload = msg_data.get('payload', {})

        body_content = get_deepest_text_payload(payload)
        extracted = extract_order_details(body_content)

        # Veriler gövdede yoksa PDF'i işle
        if extracted['order_id'] == "Sipariş Numarası bulunamadı":
            pdf_data = process_email_with_pdf(service, 'me', email['id'])
            if pdf_data['order_id'] != "Sipariş Numarası bulunamadı":
                extracted = pdf_data

        enriched_emails.append({
            'subject': email.get('subject', '(No Subject)'),
            'sender': email.get('sender', '(Unknown Sender)'),
            'date': email.get('date', '(Unknown Date)'),
            'total_amount': extracted['total_amount'],
            'order_id': extracted['order_id'],
            'source': 'Other'
        })

    # Tekrarlayan siparişleri order_id'ye göre kaldır
    seen_order_ids = set()
    unique_emails = []
    for email in enriched_emails:
        if email['order_id'] not in seen_order_ids and email['order_id'] != "Sipariş Numarası bulunamadı":
            seen_order_ids.add(email['order_id'])
            unique_emails.append(email)

    # E-posta tarihlerini datetime nesnelerine dönüştür ve sıralama yap
    for email in unique_emails:
        parsed_date = parse_email_date(email['date'])
        email['parsed_date'] = parsed_date

    # Tarihe göre azalan sırada (en yeni en üstte) sırala
    unique_emails.sort(key=lambda x: x['parsed_date'] or datetime.datetime.min, reverse=True)

    all_months = [
        {"number": i, "name": calendar.month_name[i]} for i in range(1, 13)
    ]

    return render_template(
        'dashboard.html',
        emails=unique_emails,
        all_months=all_months,
        all_years=all_years,
        selected_month=selected_month,
        selected_year=selected_year,
        month_name=month_name
    )


def credentials_to_dict(credentials):
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

if __name__ == '__main__':
    app.run(debug=True)