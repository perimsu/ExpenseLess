import calendar
import os
import datetime
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
from flask import Flask, redirect, url_for, session, render_template, request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from web_scraping import (
    list_emails_with_month,
    extract_order_details,
    get_deepest_text_payload,
    extract_trendyol_order_details,
    parse_email_date
)

app = Flask(__name__, static_folder='static')
app.secret_key = os.environ.get("SECRET_KEY", "your_secret_key")

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

CLIENT_SECRETS_FILE = "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

flow = Flow.from_client_secrets_file(
    CLIENT_SECRETS_FILE,
    scopes=SCOPES,
    redirect_uri='http://localhost:5000/callback'
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

def fetch_email_data(service, keywords, year, month):

    emails, _ = list_emails_with_month(service, keywords, year, month)
    email_data = []

    for email in emails:
        msg_data = service.users().messages().get(userId='me', id=email['id']).execute()
        payload = msg_data.get('payload', {})
        sender = email.get('sender', '(Unknown Sender)')
        body_content = get_deepest_text_payload(payload)
        extracted_details = extract_order_details(body_content)
        total_amount = extracted_details['total_amount']

        if total_amount != "Tutar bulunamadı":
            try:
                email_data.append({
                    'sender': sender,
                    'total_amount': float(total_amount)
                })
            except ValueError:
                continue

    return pd.DataFrame(email_data)

def generate_plot(data):

    if data.empty:
        return None

    sender_totals = data.groupby('sender')['total_amount'].sum()

    colors = [
        "#0D1B2A", "#1B263B", "#415A77", "#778DA9", "#FFF8E6", "#1B5E56"
    ]

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.pie(sender_totals, labels=sender_totals.index, autopct='%1.1f%%', startangle=140, colors=colors[:len(sender_totals)])
    ax.set_title('Harcama Dağılımı (Gönderici Bazlı)')
    ax.axis('equal')

    img = io.BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode('utf8')
    plt.close(fig)

    return plot_url

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login_page')
def login_page():
    return render_template('login.html')

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

    current_year = today.year
    years_back = 5
    all_years = list(range(current_year, current_year - years_back - 1, -1))

    trendyol_keywords = ['siparişini aldık']
    general_keywords = ['sipariş']

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
    for email in trendyol_emails:
        msg_data = service.users().messages().get(
            userId='me',
            id=email['id']
        ).execute()
        payload = msg_data.get('payload', {})

        body_content = get_deepest_text_payload(payload)
        extracted = extract_trendyol_order_details(body_content)

        enriched_emails.append({
            'subject': email.get('subject', '(No Subject)'),
            'sender': email.get('sender', '(Unknown Sender)'),
            'date': email.get('date', '(Unknown Date)'),
            'total_amount': extracted['total_amount'],
            'order_id': extracted['order_id'],
            'source': 'Trendyol'
        })

    for email in other_emails:
        msg_data = service.users().messages().get(
            userId='me',
            id=email['id']
        ).execute()
        payload = msg_data.get('payload', {})

        body_content = get_deepest_text_payload(payload)
        extracted = extract_order_details(body_content)

        enriched_emails.append({
            'subject': email.get('subject', '(No Subject)'),
            'sender': email.get('sender', '(Unknown Sender)'),
            'date': email.get('date', '(Unknown Date)'),
            'total_amount': extracted['total_amount'],
            'order_id': extracted['order_id'],
            'source': 'Other'
        })

    seen_order_ids = set()
    unique_emails = []
    for email in enriched_emails:
        if email['order_id'] not in seen_order_ids and email['order_id'] != "Sipariş Numarası bulunamadı":
            seen_order_ids.add(email['order_id'])
            unique_emails.append(email)

    for email in unique_emails:
        parsed_date = parse_email_date(email['date'])
        email['parsed_date'] = parsed_date

    unique_emails.sort(key=lambda x: x['parsed_date'] or datetime.datetime.min, reverse=True)

    data = fetch_email_data(service, general_keywords + trendyol_keywords, selected_year, selected_month)

    plot_url = generate_plot(data)

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
        month_name=month_name,
        plot_url=plot_url
    )

if __name__ == '__main__':
    app.run(debug=True)
