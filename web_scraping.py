from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import re
import base64
from bs4 import BeautifulSoup
import calendar


def get_deepest_text_payload(payload):
    if 'parts' in payload:
        for part in payload['parts']:
            sub_result = get_deepest_text_payload(part)
            if sub_result:
                return sub_result
    else:
        mime_type = payload.get('mimeType')
        data = payload.get('body', {}).get('data')
        if mime_type in ['text/plain', 'text/html'] and data:
            try:
                return base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
            except Exception:
                return ""
    return ""


def extract_order_id(full_text):
    order_id_patterns = [
        r'(Sipariş Numarası[:]?|Sipariş No[:]?|Order ID[:]?|Order Number[:]?)[^\d]*(\d+)',  # klasik kalıplar
        r'(SİPARİŞ NO[:\.]?)[^\d]*(\d+)',
        r'(\d+)\s+numaralı siparişini aldık'
    ]

    for pattern in order_id_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            if match.lastindex == 2:
                return match.group(2)
            else:
                return match.group(1)

    return None


def extract_amount(full_text):
    trendyol_patterns = [
        r'(?:Sepet Tutarı|Toplam Tutar|Toplam)[^\d]*?([0-9]+(?:[,.][0-9]{2})?)\s*(?:TL|TRY)',
        r'([0-9]+(?:[,.][0-9]{2})?)\s*(?:TL|TRY)',
        r'₺\s*([0-9]+(?:[,.][0-9]{2})?)',
    ]

    general_patterns = [
        r'(?:Toplam|Tutar|Amount|Total)[^0-9₺TL]*?((?:\d{1,3}(?:[.,]\d{3})*|(?:\d+))(?:[.,]\d{2})?)\s*(?:TL|TRY|₺)',
        r'((?:\d{1,3}(?:[.,]\d{3})*|(?:\d+))(?:[.,]\d{2})?)\s*(?:TL|TRY|₺)',
        r'₺\s*((?:\d{1,3}(?:[.,]\d{3})*|(?:\d+))(?:[.,]\d{2})?)',
    ]

    for pattern in trendyol_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            amount = match.group(1)
            try:
                amount = amount.replace(',', '.')
                return f"{float(amount):.2f}"
            except ValueError:
                continue

    for pattern in general_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            amount = match.group(1)
            try:
                amount = amount.replace(',', '.')
                return f"{float(amount):.2f}"
            except ValueError:
                continue

    return None


def extract_order_details(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')

    full_text = ' '.join(soup.get_text(separator=' ', strip=True).split())

    order_id = extract_order_id(full_text)
    total_amount = extract_amount(full_text)

    return {
        'order_id': order_id or "Sipariş Numarası bulunamadı",
        'total_amount': total_amount or "Tutar bulunamadı"
    }


def list_emails_with_details(service, keywords, max_results=10, query=None):
    keyword_query = " OR ".join(keywords)
    query = f"{keyword_query} {query}" if query else keyword_query

    results = service.users().messages().list(
        userId='me',
        q=query,
        maxResults=max_results
    ).execute()
    messages = results.get('messages', [])

    email_details = []
    for message in messages:
        msg = service.users().messages().get(userId='me', id=message['id']).execute()
        payload = msg.get('payload', {})
        headers = payload.get('headers', [])

        subject = "(No Subject)"
        sender = "(Unknown Sender)"
        formatted_date = "(Unknown Date)"

        for header in headers:
            if header['name'] == 'Subject':
                subject = header['value']
            elif header['name'] == 'From':
                sender_match = re.match(r"^(.*?)(<.*?>)?$", header['value'])
                sender = sender_match.group(1).strip() if sender_match else header['value']
            elif header['name'] == 'Date':
                date_match = re.search(
                    r"([A-Za-z]{3}), (\d{1,2} [A-Za-z]{3} \d{4}) (\d{2}:\d{2})",
                    header['value']
                )
                if date_match:
                    day = date_match.group(1)
                    date_ = date_match.group(2)
                    time_ = date_match.group(3)
                    formatted_date = f"{day}, {date_} {time_}"

        email_details.append({
            'id': message['id'],
            'subject': subject,
            'sender': sender,
            'date': formatted_date
        })

    return email_details


def get_date_range_for_month(year, month):
    _, last_day = calendar.monthrange(year, month)
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month:02d}-{last_day}"
    return start_date, end_date


def list_emails_with_month(service, keywords, year, month, max_results=10):
    start_date, end_date = get_date_range_for_month(year, month)

    query = f"after:{start_date} before:{end_date}"
    emails = list_emails_with_details(service, keywords, query=query, max_results=max_results)

    month_name = calendar.month_name[month]
    return emails, month_name


def process_emails(service, query):

    results = service.users().messages().list(userId='me', q=query).execute()
    messages = results.get('messages', [])

    email_data = []
    for message in messages:
        msg_data = service.users().messages().get(userId='me', id=message['id']).execute()
        payload = msg_data.get('payload', {})
        headers = payload.get('headers', [])

        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
        date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown')
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'Unknown')

        body_content = get_deepest_text_payload(payload)
        extracted_data = extract_order_details(body_content)

        email_data.append({
            "subject": subject,
            "sender": sender,
            "date": date,
            "order_id": extracted_data['order_id'],
            "amount": extracted_data['total_amount']
        })

    return email_data
