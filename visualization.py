import matplotlib

matplotlib.use('Agg')

import matplotlib.pyplot as plt
import io
import base64
import pandas as pd

VIBRANT_COLORS = [
    '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40',
    '#C9CBCF', '#8BC34A', '#FF5722', '#795548', '#00BCD4', '#E91E63'
]


def generate_pie_chart(data):
    try:
        if data.empty:
            print("Data is empty. Cannot generate pie chart.")
            return None

        if 'sender' not in data.columns or 'total_amount' not in data.columns:
            print("Required columns missing in data.")
            return None

        grouped_data = data.groupby('sender')['total_amount'].sum()

        if grouped_data.empty:
            print("Grouped data is empty. Cannot generate pie chart.")
            return None

        plt.clf()
        fig, ax = plt.subplots(figsize=(4, 4))
        ax.pie(
            grouped_data.values,
            labels=grouped_data.index,
            autopct='%1.1f%%',
            startangle=90,
            colors=VIBRANT_COLORS[:len(grouped_data)]
        )
        plt.title('Göndericiye Göre Harcama Dağılımı', pad=20)

        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', bbox_inches='tight', dpi=80)
        buffer.seek(0)
        image_png = buffer.getvalue()
        buffer.close()
        plt.close()

        return base64.b64encode(image_png).decode('utf-8')

    except Exception as e:
        print(f"Error generating pie chart: {e}")
        return None


def generate_pie_chart_only(data):
    """Generate pie chart with error handling"""
    try:
        if not isinstance(data, pd.DataFrame):
            data = pd.DataFrame(data)
        print("[DEBUG] Converted data to DataFrame.")

        if data.empty:
            print("[DEBUG] No data available for pie chart.")
            return None

        print(f"[DEBUG] Data shape: {data.shape}")
        print(f"[DEBUG] Columns: {data.columns.tolist()}")
        print(f"[DEBUG] First few rows:\n{data.head()}")

        if 'sender' not in data.columns or 'total_amount' not in data.columns:
            print("[DEBUG] Missing required columns: 'sender' or 'total_amount'.")
            return None

        pie_chart = generate_pie_chart(data)

        if not pie_chart:
            print("[DEBUG] Pie chart generation failed.")

        return pie_chart

    except Exception as e:
        print(f"Error in generate_pie_chart_only: {str(e)}")
        return None
