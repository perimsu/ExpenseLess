import calendar
import base64
import re
import io

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError
from PyPDF2 import PdfReader
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# ---- Yardımcı Fonksiyonlar ----

def get_deepest_text_payload(payload):
    """
    E-posta gövdesinin en derin metin kısmını alır.
    """
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
        return ' '.join(plain_texts)
    elif html_texts:
        soup = BeautifulSoup(html_texts[0], 'html.parser')
        return ' '.join(soup.get_text(separator=' ', strip=True).split())
    return ""

def extract_order_id(full_text):
    """
    Gelen metin içinden sipariş numarasını (order_id) yakalamak için
    çeşitli regex kalıpları kullanılır.
    """
    order_id_patterns = [
        r'(Sipariş Numarası[:#]?|Sipariş No[:#]?|Order ID[:#]?|Order Number[:#]?)[^\d]*(\d+)',
        r'(SİPARİŞ NO[:#\.]?|Order ID[:#\.]?)[^\d]*(\d+)',
        r'#(\d+)',  # # ile başlayan sipariş numaraları
        r'(\d+)\s+numaralı\s+siparişini\s+aldık',
    ]

    for pattern in order_id_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            # Eğer 2 grup varsa (etiket + numara)
            if match.lastindex >= 2:
                return match.group(2)
            else:
                return match.group(1)
    return None

def extract_amount(full_text):
    """
    Metin içinden tutar bilgisini çıkarır.
    """
    text = full_text.replace('\n', ' ').replace('\r', ' ')
    text = re.sub(r'\s+', ' ', text)

    general_patterns = [
        r'(?:Toplam|Tutar|Amount|Total)[^0-9₺TL$USD€EUR]*?([\d.,]+)\s*(?:TL|TRY|₺|\$|USD|€|EUR)',
        r'([\d.,]+)\s*(?:TL|TRY|₺|\$|USD|€|EUR)',
        r'[₺$€]\s*([\d.,]+)',
    ]

    for pattern in general_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            amount_str = match.group(1).strip()
            try:
                if ',' in amount_str and '.' in amount_str:
                    # "1.234,56" -> "1234.56"
                    amount_str = amount_str.replace('.', '').replace(',', '.')
                elif ',' in amount_str:
                    # "123,45" -> "123.45"
                    amount_str = amount_str.replace(',', '.')
                amount = float(amount_str)
                return f"{amount:.2f}"
            except ValueError:
                continue

    return None

def extract_order_details(html_content):
    """
    Genel sipariş detaylarını HTML içeriğinden çıkarır.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    full_text = ' '.join(soup.get_text(separator=' ', strip=True).split())

    order_id_ = extract_order_id(full_text)
    total_amount_ = extract_amount(full_text)

    return {
        'order_id': order_id_ or "Sipariş Numarası bulunamadı",
        'total_amount': total_amount_ or "Tutar bulunamadı"
    }

def extract_trendyol_order_details(html_content):
    """
    Trendyol sipariş detaylarını HTML içeriğinden çıkarır.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    full_text = ' '.join(soup.get_text(separator=' ', strip=True).split())

    # Order ID kalıpları (Trendyol'a özel)
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
    """
    Belirli keyword'lere ve isteğe bağlı ek query'e göre e-postaları arar.
    Bulunan e-postaların temel bilgilerini (id, subject, sender, date) döndürür.
    """
    keyword_query = " OR ".join(keywords)
    merged_query = f"{keyword_query} {query}" if query else keyword_query

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
    """
    Belirli bir yıl ve ay için başlangıç ve bitiş tarihlerini döndürür.
    """
    start_date = f"{year}-{month:02d}-01"

    next_month = month + 1
    next_year = year
    if next_month == 13:
        next_month = 1
        next_year += 1

    end_date = f"{next_year}-{next_month:02d}-01"

    return start_date, end_date

def list_emails_with_month(service, keywords, year, month, max_results=50, query=None):
    """
    Belirli bir yıl ve ay için e-postaları listeler.
    """
    start_date, end_date = get_date_range_for_month(year, month)
    query = f"after:{start_date} before:{end_date}"

    emails = list_emails_with_details(
        service,
        keywords,
        max_results=max_results,
        query=query
    )
    month_name = calendar.month_name[month]
    return emails, month_name

# ---- PDF İŞLEMLERİ ----

def extract_text_from_pdf(attachment_data):
    """
    PDF içerik baytlarını PyPDF2 ile okuyup metnini döndürür.
    """
    try:
        pdf_bytes = base64.urlsafe_b64decode(attachment_data)
        pdf_stream = io.BytesIO(pdf_bytes)
        reader = PdfReader(pdf_stream)

        all_text = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            all_text.append(page_text)

        return "\n".join(all_text)
    except Exception as e:
        print(f"PDF extraction error: {e}")
        return ""

def extract_info_from_pdf_attachment(service, user_id, message_id, part):
    """
    PDF ekini indirir, parse eder ve sipariş/tutar bilgilerini yakalamaya çalışır.
    """
    try:
        att_id = part['body']['attachmentId']
        attachment = service.users().messages().attachments().get(
            userId=user_id,
            messageId=message_id,
            id=att_id
        ).execute()

        pdf_content = attachment.get('data')
        if pdf_content:
            pdf_text = extract_text_from_pdf(pdf_content)
            parsed_data = extract_order_details(pdf_text)
            return parsed_data

    except HttpError as e:
        print(f"Gmail API error when fetching attachment: {e}")
    except Exception as e:
        print(f"Error processing PDF attachment: {e}")

    return {'order_id': '', 'total_amount': ''}

def process_email_with_pdf(service, user_id, message_id):
    """
    1) E-postanın gövdesinde sipariş/tutar var mı (extract_order_details) bakar.
    2) Yoksa eklerde PDF arar, bulursa parse eder.
    3) Sonuç olarak order_id, total_amount döndürür.
    """
    try:
        msg_data = service.users().messages().get(
            userId=user_id,
            id=message_id
        ).execute()

        payload = msg_data.get('payload', {})
        # Gövdeyi parse et
        body_content = get_deepest_text_payload(payload)
        info_from_body = extract_order_details(body_content)

        # Gövdede bilgi varsa direkt dön
        if (info_from_body['order_id'] != "Sipariş Numarası bulunamadı") and \
           (info_from_body['total_amount'] != "Tutar bulunamadı"):
            return info_from_body

        # Gövdede yoksa PDF eklerini arayalım
        if 'parts' in payload:
            for part in payload['parts']:
                filename = part.get('filename', '').lower()
                mime_type = part.get('mimeType', '').lower()

                if filename.endswith('.pdf') or ('pdf' in mime_type):
                    pdf_info = extract_info_from_pdf_attachment(service, user_id, message_id, part)
                    if pdf_info['order_id'] != "Sipariş Numarası bulunamadı" or \
                       pdf_info['total_amount'] != "Tutar bulunamadı":
                        return pdf_info

                # Alt parts içinde de PDF olabilir
                if 'parts' in part:
                    for subpart in part['parts']:
                        filename_sub = subpart.get('filename', '').lower()
                        mime_sub = subpart.get('mimeType', '').lower()
                        if filename_sub.endswith('.pdf') or ('pdf' in mime_sub):
                            pdf_info = extract_info_from_pdf_attachment(
                                service, user_id, message_id, subpart
                            )
                            if pdf_info['order_id'] != "Sipariş Numarası bulunamadı" or \
                               pdf_info['total_amount'] != "Tutar bulunamadı":
                                return pdf_info

        # Hiçbir yerde veri yoksa
        return {
            'order_id': "Sipariş Numarası bulunamadı",
            'total_amount': "Tutar bulunamadı"
        }
    except HttpError as e:
        print(f"Gmail API error when processing email {message_id}: {e}")
    except Exception as e:
        print(f"Error processing email {message_id}: {e}")

    return {
        'order_id': "Sipariş Numarası bulunamadı",
        'total_amount': "Tutar bulunamadı"
    }

# ---- Tekrarlama Kontrol Fonksiyonları ----

def parse_email_date(date_str):
    """
    E-posta tarih dizesini datetime nesnesine dönüştürür.
    """
    try:
        # Örnek tarih formatı: 'Sun, 08 Dec 2024 12:50'
        return datetime.strptime(date_str, '%a, %d %b %Y %H:%M')
    except ValueError:
        try:
            # İlk format başarısız olursa alternatif formatı dene
            return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return None

def is_duplicate_order(existing_orders, new_order):
    """
    Siparişin zaten listede olup olmadığını order_id'ye göre kontrol eder.
    """
    new_order_id = new_order.get('order_id')
    if not new_order_id or new_order_id in [order['order_id'] for order in existing_orders]:
        return True
    return False

# ---- Ana İşlem Fonksiyonu ----

def process_all_orders(service, max_results=50):
    """
    Hem Trendyol hem de diğer sipariş e-postalarını işler,
    PDF eklerini dahil ederek, tekrarları kontrol eder.
    """
    # Tüm siparişler için genel anahtar kelimeler
    general_keywords = ['e-ticket', 'sipariş özeti', 'sipariş tutarı']

    # Trendyol e-postalarını özel olarak işlemek için sorgu
    trendyol_query = "from:info@trendyolmail.com subject:'Siparişini aldık ✅'"
    trendyol_results = service.users().messages().list(
        userId='me',
        q=trendyol_query,
        maxResults=max_results
    ).execute()

    # Diğer e-postaları daha geniş kriterlerle işlemek için sorgu
    other_query = f"({' OR '.join([f'subject:{keyword}' for keyword in general_keywords])}) -from:info@trendyolmail.com"
    other_results = service.users().messages().list(
        userId='me',
        q=other_query,
        maxResults=max_results
    ).execute()

    all_emails = []

    # Trendyol e-postalarını işle
    for msg in trendyol_results.get('messages', []):
        msg_id = msg['id']
        msg_data = service.users().messages().get(userId='me', id=msg_id).execute()
        payload = msg_data.get('payload', {})
        headers = payload.get('headers', [])

        # E-posta gövdesinden veri çek
        body_content = get_deepest_text_payload(payload)
        extracted_data = extract_trendyol_order_details(body_content)

        # Eğer gövdede veri bulunamazsa, PDF eklerini işle
        if (extracted_data['order_id'] == "Trendyol Sipariş Numarası Bulunamadı" and
            extracted_data['total_amount'] == "Trendyol Tutar Bulunamadı"):
            pdf_data = process_email_with_pdf(service, 'me', msg_id)
            if pdf_data['order_id'] != "Sipariş Numarası bulunamadı":
                extracted_data = pdf_data

        # E-posta başlık bilgilerini al
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'Unknown')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
        date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown')

        new_order = {
            "subject": subject,
            "sender": sender,
            "date": date,
            "order_id": extracted_data['order_id'],
            "amount": extracted_data['total_amount'],
            "source": "Trendyol"
        }

        # Duplicate kontrolü yap ve ekle
        if not is_duplicate_order(all_emails, new_order):
            all_emails.append(new_order)

    # Diğer e-postaları işle
    for msg in other_results.get('messages', []):
        msg_id = msg['id']
        msg_data = service.users().messages().get(userId='me', id=msg_id).execute()
        payload = msg_data.get('payload', {})
        headers = payload.get('headers', [])

        # Gövdeyi parse et
        body_content = get_deepest_text_payload(payload)
        extracted_data = extract_order_details(body_content)

        # Eğer gövdede veri bulunamazsa, PDF eklerini işle
        if (extracted_data['order_id'] == "Sipariş Numarası bulunamadı" and
            extracted_data['total_amount'] == "Tutar bulunamadı"):
            pdf_data = process_email_with_pdf(service, 'me', msg_id)
            if pdf_data['order_id'] != "Sipariş Numarası bulunamadı":
                extracted_data = pdf_data

        # E-posta başlık bilgilerini al
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'Unknown')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
        date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown')

        new_order = {
            "subject": subject,
            "sender": sender,
            "date": date,
            "order_id": extracted_data['order_id'],
            "amount": extracted_data['total_amount'],
            "source": "Other"
        }

        # Duplicate kontrolü yap ve ekle
        if not is_duplicate_order(all_emails, new_order):
            all_emails.append(new_order)

    return all_emails

# ---- Örnek Kullanım ----

# Google API istemcisini oluşturun (OAuth 2.0 kimlik bilgileri gereklidir)
def main():
    # Kimlik bilgilerinizi burada ayarlayın
    creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/gmail.readonly'])
    service = build('gmail', 'v1', credentials=creds)

    # Siparişleri işle
    orders = process_all_orders(service, max_results=100)

    # Sonuçları yazdır
    for order in orders:
        print(f"Sipariş ID: {order['order_id']}, Tutar: {order['amount']}, Kaynak: {order['source']}")
        print(f"Subject: {order['subject']}, Gönderen: {order['sender']}, Tarih: {order['date']}")
        print("-" * 50)

if __name__ == "__main__":
    main()
