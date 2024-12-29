import base64
import calendar

from flask import Flask, redirect, url_for, session, render_template, request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import os
import datetime

from web_scraping import (
    list_emails_with_month,
    extract_order_details,
    get_deepest_text_payload
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

    credentials = Credentials(**session["credentials"])
    service = build('gmail', 'v1', credentials=credentials)

    today = datetime.datetime.now()
    selected_year = today.year
    selected_month = today.month

    if request.method == 'POST':
        selected_month = int(request.form.get('month', selected_month))
        selected_year = int(request.form.get('year', selected_year))

    keywords = ['e-fatura', 'e-ticket', 'sipariş']

    emails, month_name = list_emails_with_month(
        service,
        keywords,
        selected_year,
        selected_month
    )

    enriched_emails = []
    for email in emails:
        msg_data = service.users().messages().get(userId='me', id=email['id']).execute()
        payload = msg_data.get('payload', {})

        body_content = get_deepest_text_payload(payload)
        extracted_details = extract_order_details(body_content)

        debug_order_id = extracted_details['order_id']
        print(f"DEBUG -> E-posta konusu: {email.get('subject')} | Order ID: {debug_order_id}")

        total_amount_value = extracted_details['total_amount']

        enriched_emails.append({
            'subject': email.get('subject', '(No Subject)'),
            'sender': email.get('sender', '(Unknown Sender)'),
            'date': email.get('date', '(Unknown Date)'),
            'total_amount': total_amount_value
        })

    all_months = [{"number": i, "name": calendar.month_name[i]} for i in range(1, 13)]

    return render_template(
        'dashboard.html',
        emails=enriched_emails,
        all_months=all_months,
        selected_month=selected_month,
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
