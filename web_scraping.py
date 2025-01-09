import base64
import calendar
import re
from datetime import datetime

from bs4 import BeautifulSoup
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from pdf_processor import extract_pdf_content, process_email_attachments, extract_pdf_order_details


def get_deepest_text_payload(payload):
    texts = []

    def extract_text(part):
        if 'parts' in part:
            for subpart in part['parts']:
                extract_text(subpart)
        else:
            mime_type = part.get('mimeType')
            data = part.get('body', {}).get('data')
            if mime_type in ['text/plain', 'text/html'] and data:
                try:
                    decoded = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
                    texts.append((mime_type, decoded))
                except Exception:
                    pass

    extract_text(payload)

    plain_texts = [text for mime, text in texts if mime == 'text/plain']
    html_texts = [text for mime, text in texts if mime == 'text/html']

    if plain_texts:
        full_text = ' '.join(plain_texts)
    elif html_texts:
        soup = BeautifulSoup(html_texts[0], 'html.parser')
        full_text = soup.get_text(separator=' ', strip=True)
    else:
        return ""

    full_text = re.sub(r'\s+', ' ', full_text).strip()
    return full_text



def extract_order_id(full_text):
    order_id_patterns = [
        r'(Sipariş Numarası[:#]?|Sipariş No[:#]?|Order ID[:#]?|Order Number[:#]?)[^\d]*(\d+)',
        r'(SİPARİŞ NO[:#\.]?|Order ID[:#\.]?)[^\d]*(\d+)',
        r'#(\d+)',
        r'(\d+)\s+numaralı\s+siparişini\s+aldık',
        r"Sipariş No\.?\s*(\d+-\d+-\d+)",
        r"#(\d{3}-\d{7}-\d{7})",
        r'(?:Sipariş|Order|Invoice|Fatura)[^0-9]*?(\d+)',
    ]

    for pattern in order_id_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            if match.lastindex >= 2:
                return match.group(2)
            else:
                return match.group(1)
    return None


def extract_amount(full_text):
    text = full_text.replace('\n', ' ').replace('\r', ' ')
    text = re.sub(r'\s+', ' ', text)

    general_patterns = [
        r'(?:Ara toplam|Toplam|Tutar|Amount|Total)[^0-9₺TL$USD€EUR]*?([\d.,]+)\s*(?:TL|TRY|₺|\$|USD|€|EUR)',
        r'([\d.,]+)\s*(?:TL|TRY|₺|\$|USD|€|EUR)',
        r'[₺$€]\s*([\d.,]+)',
        r"KDV Dahil Sipariş Toplamı:\s*([\d.,]+)\s*TL",
        r'(?:Toplam Tutar|Ara Toplam|Total Amount)[^0-9]*?([\d.,]+)\s*(?:TL|TRY|₺|\$|USD|€|EUR)',
    ]

    for pattern in general_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            amount_str = match.group(1).strip()
            try:
                if '.' in amount_str and ',' in amount_str:
                    amount_str = amount_str.replace('.', '').replace(',', '.')
                elif ',' in amount_str:
                    amount_str = amount_str.replace(',', '.')
                amount = float(amount_str)
                if amount < 10 and '.' in amount_str:
                    amount *= 1000
                return f"{amount:.2f}"
            except ValueError:
                continue
    return None



def extract_order_details(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    full_text = ' '.join(soup.get_text(separator=' ', strip=True).split())

    order_id_ = extract_order_id(full_text)
    total_amount_ = extract_amount(full_text)

    print(f"Extracted Order ID: {order_id_}")
    print(f"Extracted Total Amount: {total_amount_}")

    return {
        'order_id': order_id_ or "Sipariş Numarası bulunamadı",
        'total_amount': total_amount_ or "Tutar bulunamadı"
    }


def extract_trendyol_order_details(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    full_text = ' '.join(soup.get_text(separator=' ', strip=True).split())

    order_id_patterns = [
        r"(?:Sipariş Numaranız:|Sipariş Numarası:|Sipariş No:|Order ID:) *(\d+)",
        r"#(\d+)\s+numaralı\s+siparişi",
    ]
    order_id_ = None
    for pattern in order_id_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            order_id_ = match.group(1)
            break

    amount_patterns = [
        r"(?:Sepet Tutarı|Toplam Tutar|Toplam|Ödenecek Tutar)[^\d]*?([\d.,]+)\s*(?:TL|TRY|₺|\$|USD)",
        r'([\d.,]+)\s*(?:TL|TRY|₺|\$|USD)',
        r'[₺$]\s*([\d.,]+)'
    ]
    total_amount_ = None
    for pattern in amount_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(',', '.')
            try:
                total_amount_ = f"{float(amount_str):.2f}"
                break
            except ValueError:
                continue

    if not order_id_:
        order_elements = soup.find_all(class_=re.compile(r'order.*number|siparis.*no', re.I))
        for element in order_elements:
            potential_id = extract_order_id(element.get_text())
            if potential_id:
                order_id_ = potential_id
                break

    if not total_amount_:
        amount_elements = soup.find_all(class_=re.compile(r'total.*amount|toplam.*tutar', re.I))
        for element in amount_elements:
            potential_amount = extract_amount(element.get_text())
            if potential_amount:
                total_amount_ = potential_amount
                break

    return {
        'order_id': order_id_ or "Trendyol Sipariş Numarası Bulunamadı",
        'total_amount': total_amount_ or "Trendyol Tutar Bulunamadı"
    }


def list_emails_with_details(service, keywords, max_results=50, query=None):
    keyword_query = " OR ".join(keywords)
    temu_filter = "-from:temu@orders.temu.com"
    merged_query = f"{keyword_query} {query} {temu_filter}" if query else f"{keyword_query} {temu_filter}"

    try:
        results = service.users().messages().list(
            userId='me',
            q=merged_query,
            maxResults=max_results
        ).execute()
    except HttpError as e:
        print(f"Gmail API error: {e}")
        return []

    messages = results.get('messages', [])
    email_details = []
    for message in messages:
        try:
            msg_data = service.users().messages().get(userId='me', id=message['id']).execute()
            payload = msg_data.get('payload', {})
            headers = payload.get('headers', [])

            subject_ = "(No Subject)"
            sender_ = "(Unknown Sender)"
            formatted_date = "(Unknown Date)"

            for header in headers:
                if header['name'] == 'Subject':
                    subject_ = header['value']
                elif header['name'] == 'From':
                    sender_match = re.match(r"^(.*?)(<.*?>)?$", header['value'])
                    sender_ = sender_match.group(1).strip() if sender_match else header['value']
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
                'subject': subject_,
                'sender': sender_,
                'date': formatted_date
            })
        except HttpError as e:
            print(f"Gmail API error when fetching message {message['id']}: {e}")
            continue

    return email_details



def get_date_range_for_month(year, month):
    start_date = f"{year}-{month:02d}-01"

    next_month = month + 1
    next_year = year
    if next_month == 13:
        next_month = 1
        next_year += 1

    end_date = f"{next_year}-{next_month:02d}-01"

    return start_date, end_date


def list_emails_with_month(service, keywords, year, month, max_results=50, query=None):
    """Belirli bir ay ve yıl için e-postaları listele."""
    start_date = f"{year}-{month:02d}-01"
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    end_date = f"{next_year}-{next_month:02d}-01"

    query = f"after:{start_date} before:{end_date}"

    emails = list_emails_with_details(
        service,
        keywords,
        max_results=max_results,
        query=query
    )
    month_name = calendar.month_name[month]
    return emails, month_name


def parse_email_date(date_str):
    try:
        return datetime.strptime(date_str, '%a, %d %b %Y %H:%M')
    except ValueError:
        try:
            return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return None


def is_duplicate_order(existing_orders, new_order):
    new_order_id = new_order.get('order_id')
    if not new_order_id or new_order_id in [order['order_id'] for order in existing_orders]:
        return True
    return False


def process_all_orders(service, max_results=50):
    general_keywords = ['e-ticket', 'sipariş özeti', 'sipariş tutarı', 'fatura', 'E-FATURA HESABI | BOYNER']

    content_keywords = [
        'sipariş', 'fatura', 'order', 'invoice',
        'toplam tutar', 'total amount',
        'ödeme', 'payment',
        'sipariş özeti', 'order summary'
    ]

    trendyol_query = "from:info@trendyolmail.com subject:'Siparişini aldık ✅'"
    try:
        trendyol_results = service.users().messages().list(
            userId='me',
            q=trendyol_query,
            maxResults=max_results
        ).execute()
    except HttpError as e:
        print(f"Gmail API error: {e}")
        trendyol_results = {}

    try:
        other_query = f"({' OR '.join([f'subject:{keyword}' for keyword in general_keywords])}) -from:info@trendyolmail.com"
        other_results = service.users().messages().list(
            userId='me',
            q=other_query,
            maxResults=max_results
        ).execute()
    except HttpError as e:
        print(f"Gmail API error: {e}")
        other_results = {}

    all_emails = []

    def check_content_keywords(text):
        text = text.lower()
        return any(keyword.lower() in text for keyword in content_keywords)

    for msg in trendyol_results.get('messages', []):
        msg_id = msg['id']
        try:
            msg_data = service.users().messages().get(userId='me', id=msg_id).execute()
            payload = msg_data.get('payload', {})
            headers = payload.get('headers', [])

            body_content = get_deepest_text_payload(payload)
            extracted_data = extract_trendyol_order_details(body_content)

            if not check_content_keywords(body_content):
                attachment_ids = process_email_attachments(msg_data)
                for att_id in attachment_ids:
                    attachment = service.users().messages().attachments().get(
                        userId='me',
                        messageId=msg_id,
                        id=att_id
                    ).execute()

                    pdf_data = attachment.get('data', '')
                    if pdf_data:
                        pdf_text = extract_pdf_content(pdf_data)
                        pdf_extracted_data = extract_pdf_order_details(pdf_text)
                        if pdf_extracted_data:
                            extracted_data = pdf_extracted_data
                            break

            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'Unknown')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown')

            new_order = {
                "subject": subject,
                "sender": sender,
                "date": date,
                "order_id": extracted_data['order_id'],
                "amount": extracted_data['total_amount'],
                "source": "Trendyol",
                "processed_from": "Email"
            }

            if not is_duplicate_order(all_emails, new_order):
                all_emails.append(new_order)

        except HttpError as e:
            print(f"Gmail API error when fetching message {msg_id}: {e}")
            continue

    for msg in other_results.get('messages', []):
        msg_id = msg['id']
        try:
            msg_data = service.users().messages().get(userId='me', id=msg_id).execute()
            payload = msg_data.get('payload', {})
            headers = payload.get('headers', [])

            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'Unknown')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown')

            body_content = get_deepest_text_payload(payload)
            extracted_data = extract_order_details(body_content)

            if not check_content_keywords(body_content):
                attachment_ids = process_email_attachments(msg_data)
                for att_id in attachment_ids:
                    attachment = service.users().messages().attachments().get(
                        userId='me',
                        messageId=msg_id,
                        id=att_id
                    ).execute()

                    pdf_data = attachment.get('data', '')
                    if pdf_data:
                        pdf_text = extract_pdf_content(pdf_data)
                        pdf_extracted_data = extract_pdf_order_details(pdf_text)
                        if pdf_extracted_data:
                            extracted_data = pdf_extracted_data
                            break

            new_order = {
                "subject": subject,
                "sender": sender,
                "date": date,
                "order_id": extracted_data['order_id'],
                "amount": extracted_data['total_amount'],
                "source": "Other",
                "processed_from": "Email" if check_content_keywords(body_content) else "PDF"
            }

            if not is_duplicate_order(all_emails, new_order):
                all_emails.append(new_order)

        except HttpError as e:
            print(f"Gmail API error when fetching message {msg_id}: {e}")
            continue

    return all_emails

def process_emails_with_attachments(service, keywords, year, month):
    """Belirtilen ay ve yıl için e-postaları işleyerek eklerini indir ve işle."""
    emails, month_name = list_emails_with_month(service, keywords, year, month)

    for email in emails:
        try:
            print(f"E-posta işleniyor: {email['subject']} ({email['id']})")
            msg_data = service.users().messages().get(userId='me', id=email['id']).execute()
            process_email_attachments(msg_data)
        except Exception as e:
            print(f"E-posta işlenirken hata: {e}")
            continue



def main():
    creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/gmail.readonly'])
    service = build('gmail', 'v1', credentials=creds)

    orders = process_all_orders(service, max_results=100)

    for order in orders:
        print(f"Sipariş ID: {order['order_id']}, Tutar: {order['amount']}, Kaynak: {order['source']}")
        print(f"Subject: {order['subject']}, Gönderen: {order['sender']}, Tarih: {order['date']}")
        print("-" * 50)


if __name__ == "__main__":
    main()