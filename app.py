from urllib import request

from flask import Flask, redirect, url_for, session, render_template,request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from modules.web_scraping import process_email_with_pdf
from modules.visualization import create_visualizations
import os

app = Flask(__name__, template_folder="templates", static_folder='static')

app.secret_key = "your_secret_key"


os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
CLIENT_SECRETS_FILE = "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

flow = Flow.from_client_secrets_file(
    CLIENT_SECRETS_FILE,
    scopes=SCOPES,
    redirect_uri="http://localhost:5000/callback"
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
        return redirect(url_for('dashboard'))
    except Exception as e:
        return f"Error during callback: {str(e)}"


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