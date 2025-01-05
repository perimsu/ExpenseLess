import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64

VIBRANT_COLORS = [
    '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40',
    '#C9CBCF', '#8BC34A', '#FF5722', '#795548', '#00BCD4', '#E91E63'
]

def generate_pie_chart(data):
    try:
        if data.empty or 'sender' not in data.columns or 'total_amount' not in data.columns:
            return None

        grouped_data = data.groupby('sender')['total_amount'].sum()

        plt.clf()
        fig, ax = plt.subplots(figsize=(3.5, 3.5))
        ax.pie(
            grouped_data.values,
            labels=grouped_data.index,
            autopct='%1.1f%%',
            startangle=90,
            colors=VIBRANT_COLORS[:len(grouped_data)],
            wedgeprops=dict(width=1, edgecolor='none')
        )
        plt.title('Göndericiye Göre Harcama Dağılımı', pad=10)

        fig.patch.set_facecolor('none')
        fig.patch.set_alpha(0)
        ax.axis('off')

        buffer = io.BytesIO()
        plt.savefig(
            buffer,
            format='png',
            bbox_inches='tight',
            dpi=80,
            transparent=True
        )
        buffer.seek(0)
        image_png = buffer.getvalue()
        buffer.close()
        plt.close()

        return base64.b64encode(image_png).decode('utf-8')

    except Exception as e:
        print(f"Error generating pie chart: {e}")
        return None


def generate_line_chart(daily_expenses, month_name):
    try:
        plt.clf()
        fig, ax = plt.subplots(figsize=(8, 4))

        ax.plot(
            daily_expenses.index,
            daily_expenses.values,
            marker='o',
            linestyle='-',
            color='#36A2EB'
        )
        ax.set_title(f'Harcama Trendleri - {month_name}', pad=20)
        ax.set_xlabel('Gün')
        ax.set_ylabel('Harcama Tutarı (TL)')
        ax.grid(True)

        fig.patch.set_facecolor('none')
        fig.patch.set_alpha(0)
        for spine in ax.spines.values():
            spine.set_visible(False)

        buffer = io.BytesIO()
        plt.savefig(
            buffer,
            format='png',
            bbox_inches='tight',
            dpi=80,
            transparent=True
        )
        buffer.seek(0)
        image_png = buffer.getvalue()
        buffer.close()
        plt.close()

        return base64.b64encode(image_png).decode('utf-8')

    except Exception as e:
        print(f"Error generating line chart: {e}")
        return None


