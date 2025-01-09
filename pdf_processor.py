import pdfplumber
import re
import base64
import tempfile
import os
from pdf2image import convert_from_path
import pytesseract

def clean_currency(value):
    try:
        value = value.strip()
        if ',' in value and '.' in value:
            value = value.replace('.', '').replace(',', '.')
        elif ',' in value:
            value = value.replace(',', '.')
        return float(value)
    except ValueError as e:
        print(f"clean_currency Hatası: {e}")
        return "Hatalı Tutar Formatı"


def extract_pdf_order_details(text_content):

    details = {}

    order_patterns = [
        r'Sipariş No:\s*(\d+)',
        r'Sipariş No\s*:\s*(\d+)',
        r'Sipariş No\s*(\d+)',
    ]

    amount_patterns = [
        r'Ödenecek Tutar\s*:?\s*([\d,.]+)\s*TL',
        r'Ödenecek Tutar\s*:?\s*([\d,.]+)',
        r'GENEL TOPLAM\s*:?\s*([\d,.]+)\s*TL',
        r'Toplam\s*:?\s*([\d,.]+)\s*TL',
        r'(?:^|\n)\s*Toplam\s*(?::|)\s*([\d,.]+)',
        r'Ödenecek Tutar\s*:?\s*([\d.,]+)\s*TL',
        r'Mal Hizmet Toplam Tutarı\s*:?\s*([\d.,]+)\s*TL',
        r'Toplam İskonto\s*:?\s*([\d.,]+)\s*TL',
        r'Hesaplanan KDV Matrahı\s*:?\s*([\d.,]+)\s*TL',
        r'(?:Toplam|Ara Toplam)\s*:?\s*([\d.,]+)\s*TL'
    ]

    order_id = None
    for pattern in order_patterns:
        match = re.search(pattern, text_content)
        if match:
            order_id = match.group(1)
            break

    amount = None
    for pattern in amount_patterns:
        match = re.search(pattern, text_content)
        if match:
            amount_str = match.group(1).strip()
            try:
                if '.' in amount_str and ',' in amount_str:
                    amount_str = amount_str.replace('.', '').replace(',', '.')
                elif ',' in amount_str:
                    amount_str = amount_str.replace(',', '.')

                amount = float(amount_str)
                break
            except ValueError:
                continue

    if not amount:
        try:
            lines = text_content.split('\n')
            for i, line in enumerate(lines):
                if 'Ödenecek Tutar' in line:
                    amount_match = re.search(r'([\d,.]+)TL', line)
                    if amount_match:
                        amount_str = amount_match.group(1)
                        if '.' in amount_str and ',' in amount_str:
                            amount_str = amount_str.replace('.', '').replace(',', '.')
                        elif ',' in amount_str:
                            amount_str = amount_str.replace(',', '.')
                        amount = float(amount_str)
                        break

                    # If not found on same line, check next line
                    elif i + 1 < len(lines):
                        next_line = lines[i + 1]
                        amount_match = re.search(r'([\d,.]+)', next_line)
                        if amount_match:
                            amount_str = amount_match.group(1)
                            if '.' in amount_str and ',' in amount_str:
                                amount_str = amount_str.replace('.', '').replace(',', '.')
                            elif ',' in amount_str:
                                amount_str = amount_str.replace(',', '.')
                            amount = float(amount_str)
                            break
        except Exception as e:
            print(f"Error in secondary amount extraction: {e}")


    formatted_amount = f"{amount:.2f}" if amount is not None else None

    return {
        'order_id': order_id or "Sipariş Numarası Bulunamadı",
        'total_amount': formatted_amount or "Tutar Bulunamadı"
    }


def extract_pdf_content(pdf_data):

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
            pdf_bytes = base64.b64decode(pdf_data)
            temp_pdf.write(pdf_bytes)
            temp_pdf.flush()

            text_content = []

            with pdfplumber.open(temp_pdf.name) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text(x_tolerance=2, y_tolerance=3)
                    if page_text:
                        text_content.append(page_text)

                    if len(page_text.strip()) < 100:
                        tables = page.extract_tables()
                        for table in tables:
                            for row in table:
                                row_text = ' '.join(str(cell) for cell in row if cell)
                                if row_text.strip():
                                    text_content.append(row_text)

            extracted_text = "\n".join(text_content)

            if not any(keyword in extracted_text for keyword in ['Ödenecek Tutar', 'Sipariş No', 'TL']):
                images = convert_from_path(temp_pdf.name)
                ocr_text = []
                for image in images:
                    text = pytesseract.image_to_string(image, lang='tur')
                    ocr_text.append(text)
                extracted_text = "\n".join(ocr_text)

            return extracted_text

    except Exception as e:
        print(f"PDF processing error: {e}")
        return ""
    finally:
        if 'temp_pdf' in locals() and os.path.exists(temp_pdf.name):
            os.unlink(temp_pdf.name)


def process_email_attachments(message):
    try:
        attachment_ids = []

        def find_attachments(parts):
            for part in parts:
                filename = part.get('filename', '')
                mime_type = part.get('mimeType', '')

                if filename and mime_type == 'application/pdf':
                    attachment_id = part.get('body', {}).get('attachmentId')
                    if attachment_id:
                        attachment_ids.append(attachment_id)

                if 'parts' in part:
                    find_attachments(part['parts'])

        payload = message.get('payload', {})
        if 'parts' in payload:
            find_attachments(payload['parts'])

        return attachment_ids

    except Exception as e:
        print(f"Attachment processing error: {e}")
        return []


if __name__ == "__main__":
    with open('BE02024005049284.pdf', 'rb') as f:
        pdf_data = base64.b64encode(f.read()).decode()
    text_content = extract_pdf_content(pdf_data)
    order_details = extract_pdf_order_details(text_content)
    print(order_details)