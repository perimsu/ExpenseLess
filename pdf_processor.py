import pdfplumber
import re
import base64
import tempfile
import os
from pdf2image import convert_from_path
import pytesseract


def extract_pdf_content(pdf_data):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
            pdf_bytes = base64.b64decode(pdf_data)
            temp_pdf.write(pdf_bytes)
            temp_pdf.flush()

            text_content = []

            # PDF metni çıkarma
            with pdfplumber.open(temp_pdf.name) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text(x_tolerance=2, y_tolerance=2)
                    if page_text:
                        text_content.append(page_text)

            # Eğer metin çıkarılamadıysa OCR fallback
            if not any(text_content):
                images = convert_from_path(temp_pdf.name)
                for image in images:
                    ocr_text = pytesseract.image_to_string(image, lang="tur")  # Türkçe OCR
                    if ocr_text.strip():
                        text_content.append(ocr_text)

        # Tüm sayfa metinlerini birleştir
        return "\n".join(text_content)

    except Exception as e:
        print(f"PDF işleme hatası: {e}")
        return ""

    finally:
        if os.path.exists(temp_pdf.name):
            os.unlink(temp_pdf.name)


def extract_pdf_order_details(text_content):
    patterns = {
        'invoice_number': r'Fatura\s*No:\s*([A-Za-z0-9]+)',
        'order_number': r'Sipariş\s*No:\s*(\d+)',
        'invoice_date': r'Fatura\s*Tarihi:\s*(\d{4}-\d{2}-\d{2})',
        'total_amount': r'Ödenecek\s*Tutar\s*([\d.,]+)\s*TL|Toplam Tutar[:\s]*([\d.,]+)\s*TL'
    }

    details = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text_content, re.IGNORECASE)
        if match:
            value = match.group(1) if key != 'total_amount' else match.group(1) or match.group(2)
            if key == 'total_amount':
                # Tutarı formatla
                value = re.sub(r'[^\d,.-]', '', value)
                value = value.replace('.', '').replace(',', '.')
                try:
                    value = float(value)
                except ValueError:
                    value = "Hatalı Tutar Formatı"
            details[key] = value

    return {
        'invoice_number': details.get('invoice_number', "Fatura Numarası Bulunamadı"),
        'order_number': details.get('order_number', "Sipariş Numarası Bulunamadı"),
        'invoice_date': details.get('invoice_date', "Fatura Tarihi Bulunamadı"),
        'total_amount': details.get('total_amount', 0.0)  # Varsayılan olarak 0 döndür
    }

def process_email_attachments(message):
    try:
        attachment_ids = []
        email_parts = message.get('payload', {}).get('parts', [])

        def find_attachments(sub_parts):
            for part in sub_parts:
                if part.get('filename') and part.get('mimeType') == 'application/pdf':
                    attachment_id = part.get('body', {}).get('attachmentId')
                    if attachment_id:
                        attachment_ids.append(attachment_id)
                if 'parts' in part:
                    find_attachments(part['parts'])

        find_attachments(email_parts)
        return attachment_ids

    except Exception as e:
        print(f"Ekler işlenirken hata: {e}")
        return []

