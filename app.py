import os
import calendar
from flask import Flask, redirect, url_for, session, render_template, request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import pandas as pd
from visualization import generate_pie_chart_only
from web_scraping import (
    list_emails_with_month,
    extract_order_details,
    get_deepest_text_payload
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

@app.route('/')
def index():
    """Ana sayfayı render eder."""
    return render_template('index.html')

@app.route('/login_page')
def login_page():
    """Giriş sayfasını render eder."""
    return render_template('login.html')

@app.route('/login')
def login():
    """Kullanıcıyı Google giriş sayfasına yönlendirir."""
    authorization_url, state = flow.authorization_url()
    session["state"] = state
    return redirect(authorization_url)

@app.route('/callback')
def callback():
    """OAuth geri çağrısını işler ve kimlik bilgilerini kaydeder."""
    try:
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials
        session["credentials"] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        return redirect(url_for('dashboard'))
    except Exception as e:
        return f"Geri çağrım sırasında hata oluştu: {str(e)}"

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    """E-posta verileri ve görselleştirmelerle dashboard'u render eder."""
    if "credentials" not in session:
        return redirect(url_for('index'))

    creds = Credentials(**session["credentials"])
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    service = build('gmail', 'v1', credentials=creds)

    today = pd.Timestamp.now()
    selected_year = today.year
    selected_month = today.month

    if request.method == 'POST':
        selected_month = request.form.get('month', str(selected_month))
        selected_year = request.form.get('year', str(selected_year))

        try:
            selected_month = int(selected_month)
            selected_year = int(selected_year)
        except ValueError:
            selected_month = today.month
            selected_year = today.year

    current_year = today.year
    years_back = 5
    all_years = list(range(current_year, current_year - years_back - 1, -1))
    all_months = [{"number": i, "name": calendar.month_name[i]} for i in range(1, 13)]

    keywords = ['sipariş', 'siparişini aldık']
    emails, month_name = list_emails_with_month(
        service, keywords, selected_year, selected_month
    )

    enriched_emails = []
    for email in emails:
        try:
            msg_data = service.users().messages().get(userId='me', id=email['id']).execute()
            payload = msg_data.get('payload', {})
            body_content = get_deepest_text_payload(payload)
            extracted = extract_order_details(body_content)

            total_amount = 0
            try:
                total_amount = float(extracted['total_amount']) if extracted['total_amount'] != "Tutar bulunamadı" else 0
            except ValueError:
                pass

            enriched_emails.append({
                'subject': email.get('subject', '(Başlık Yok)'),
                'sender': email.get('sender', '(Bilinmeyen Gönderici)'),
                'date': email.get('date', '(Bilinmeyen Tarih)'),
                'total_amount': total_amount,
                'order_id': extracted['order_id']
            })
        except Exception as e:
            print(f"E-posta işlenirken hata oluştu: {e}")
            continue

    seen_order_ids = set()
    unique_emails = []
    for email in enriched_emails:
        if email['order_id'] not in seen_order_ids and email['order_id'] != "Sipariş Numarası bulunamadı":
            seen_order_ids.add(email['order_id'])
            unique_emails.append(email)

    data_for_charts = pd.DataFrame(unique_emails)

    data_for_charts = data_for_charts.loc[:, ~data_for_charts.columns.duplicated()]

    if 'total_amount' not in data_for_charts.columns:
        data_for_charts['total_amount'] = 0
    if 'sender' not in data_for_charts.columns:
        data_for_charts['sender'] = '(Bilinmeyen Gönderici)'

    if data_for_charts.empty:
        return render_template(
            'dashboard.html',
            message="Seçilen dönem için veri mevcut değil.",
            all_months=all_months,
            all_years=all_years,
            selected_month=selected_month,
            selected_year=selected_year
        )

    pie_chart_url = generate_pie_chart_only(data_for_charts)

    return render_template(
        'dashboard.html',
        emails=unique_emails,
        all_months=all_months,
        all_years=all_years,
        selected_month=selected_month,
        selected_year=selected_year,
        month_name=month_name,
        pie_chart_url=pie_chart_url
    )

if __name__ == '__main__':
    app.run(debug=True)
