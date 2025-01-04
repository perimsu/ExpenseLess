from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import pandas as pd
import matplotlib.pyplot as plt
import random
from typing import List, Dict, Any
import logging

from web_scraping import list_emails_with_month, get_deepest_text_payload, extract_order_details


class GmailAnalyzer:
    """A class to analyze spending patterns from Gmail emails."""

    def __init__(self, credentials_path: str):
        """
        Initialize the Gmail analyzer with credentials.

        Args:
            credentials_path: Path to the Gmail API credentials file
        """
        self.credentials = Credentials.from_authorized_user_file(
            credentials_path,
            ["https://www.googleapis.com/auth/gmail.readonly"]
        )
        self.service = build('gmail', 'v1', credentials=self.credentials)
        self.logger = self.setup_logger()

    @staticmethod
    def setup_logger():
        """Configure logging for the analyzer."""
        logger = logging.getLogger('GmailAnalyzer')
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    def fetch_email_data(self, keywords: List[str], year: int, month: int) -> pd.DataFrame:
        """
        Fetch and analyze emails matching given criteria.

        Args:
            keywords: List of keywords to filter emails
            year: Year to analyze
            month: Month to analyze

        Returns:
            DataFrame containing sender and amount information
        """
        try:
            emails, _ = list_emails_with_month(self.service, keywords, year, month)
            email_data = []

            for email in emails:
                try:
                    msg_data = self.service.users().messages().get(
                        userId='me',
                        id=email['id']
                    ).execute()

                    payload = msg_data.get('payload', {})
                    sender = email.get('sender', '(Unknown Sender)')
                    body_content = get_deepest_text_payload(payload)
                    extracted_details = extract_order_details(body_content)
                    total_amount = extracted_details['total_amount']

                    if total_amount != "Tutar bulunamadı":
                        email_data.append({
                            'sender': sender,
                            'total_amount': float(total_amount)
                        })
                except (ValueError, KeyError) as e:
                    self.logger.warning(f"Error processing email {email.get('id')}: {str(e)}")
                    continue

            return pd.DataFrame(email_data)

        except Exception as e:
            self.logger.error(f"Failed to fetch email data: {str(e)}")
            raise

    def visualize_by_sender(self, data: pd.DataFrame,
                            save_path: str = None,
                            min_percentage: float = 1.0) -> None:
        """
        Create a pie chart of spending distribution by sender.

        Args:
            data: DataFrame containing sender and amount information
            save_path: Optional path to save the plot
            min_percentage: Minimum percentage to show in pie chart (smaller values grouped as 'Others')
        """
        if data.empty:
            self.logger.warning("No data available for visualization")
            return

        sender_totals = data.groupby('sender')['total_amount'].sum()
        total_spending = sender_totals.sum()

        # Group small values
        mask = (sender_totals / total_spending * 100) >= min_percentage
        main_senders = sender_totals[mask]
        others = pd.Series({
            'Others': sender_totals[~mask].sum()
        }) if any(~mask) else pd.Series()

        final_data = pd.concat([main_senders, others])

        colors = [f'#{random.randint(0, 0xFFFFFF):06x}' for _ in range(len(final_data))]

        plt.figure(figsize=(10, 8))
        patches, texts, autotexts = plt.pie(
            final_data,
            labels=final_data.index,
            autopct='%1.1f%%',
            startangle=140,
            colors=colors
        )

        plt.setp(autotexts, size=8, weight="bold")
        plt.setp(texts, size=10)

        plt.title('Spending Distribution by Sender', pad=20, size=14)
        plt.axis('equal')

        if save_path:
            plt.savefig(save_path, bbox_inches='tight', dpi=300)
            self.logger.info(f"Plot saved to {save_path}")
        else:
            plt.show()

        plt.close()


def main():
    CONFIG = {
        'credentials_path': 'token.json',
        'keywords': ['e-fatura', 'sipariş', 'order'],
        'year': 2024,
        'month': 12,
        'min_percentage': 2.0,
        'save_plot': 'spending_analysis.png'
    }

    try:
        analyzer = GmailAnalyzer(CONFIG['credentials_path'])

        email_data = analyzer.fetch_email_data(
            CONFIG['keywords'],
            CONFIG['year'],
            CONFIG['month']
        )

        analyzer.visualize_by_sender(
            email_data,
            save_path=CONFIG.get('save_plot'),
            min_percentage=CONFIG['min_percentage']
        )

    except Exception as e:
        logging.error(f"Analysis failed: {str(e)}")
        raise


if __name__ == "__main__":
    main()