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

            with pdfplumber.open(temp_pdf.name) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_content.append(page_text)

            if not text_content:
                images = convert_from_path(temp_pdf.name)
                for image in images:
                    ocr_text = pytesseract.image_to_string(image)
                    if ocr_text.strip():
                        text_content.append(ocr_text)

        os.unlink(temp_pdf.name)
        return "\n".join(text_content)

    except Exception as e:
        print(f"PDF işleme hatası: {e}")
        return ""


def extract_pdf_order_details(text_content):

    patterns = {
        'invoice_number': r'Fatura No:\s*([A-Z0-9]+)',
        'order_number': r'Sipariş No:\s*(\d+)',
        'invoice_date': r'Fatura Tarihi:\s*(\d{4}-\d{2}-\d{2})',
        'total_amount': r'Ödenecek Tutar\s*([\d.,]+)TL'
    }

    details = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text_content, re.IGNORECASE)
        if match:
            value = match.group(1)
            if key == 'total_amount':  # Tutarı dönüştür
                value = value.replace('.', '').replace(',', '.')  # Nokta kaldır, virgülü nokta yap
                try:
                    value = float(value)  # Floata çevir
                except ValueError:
                    value = "Hatalı Tutar Formatı"
            details[key] = value

    return {
        'invoice_number': details.get('invoice_number', "Fatura Numarası Bulunamadı"),
        'order_number': details.get('order_number', "Sipariş Numarası Bulunamadı"),
        'invoice_date': details.get('invoice_date', "Fatura Tarihi Bulunamadı"),
        'total_amount': details.get('total_amount', "Toplam Tutar Bulunamadı")
    }


def process_email_attachments(message):
    try:
        attachment_ids = []
        parts = message.get('payload', {}).get('parts', [])

        def find_attachments(parts):
            for part in parts:
                if part.get('mimeType') == 'application/pdf':
                    attachment_id = part.get('body', {}).get('attachmentId')
                    if attachment_id:
                        attachment_ids.append(attachment_id)
                elif 'parts' in part:
                    find_attachments(part['parts'])

        find_attachments(parts)
        return attachment_ids

    except Exception as e:
        print(f"Ekler işlenirken hata: {e}")
        return []
