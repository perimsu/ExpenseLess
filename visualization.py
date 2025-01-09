import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
import numpy as np

VIBRANT_COLORS = [
    '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40',
    '#C9CBCF', '#8BC34A', '#FF5722', '#795548', '#00BCD4', '#E91E63'
]

def generate_pie_chart(data):
    try:
        if data.empty or 'sender' not in data.columns or 'total_amount' not in data.columns:
            return None

        grouped_data = data.groupby('sender')['total_amount'].sum().sort_values(ascending=False)

        total = grouped_data.sum()
        percentages = (grouped_data / total * 100).round(1)

        small_segments = percentages[percentages < 2]
        if not small_segments.empty:
            grouped_data = grouped_data[percentages >= 2]
            percentages = percentages[percentages >= 2]
            other_amount = small_segments.sum()
            grouped_data['Diğer'] = other_amount
            percentages['Diğer'] = small_segments.sum()

        plt.clf()
        fig, ax = plt.subplots(figsize=(8, 8))

        wedges, texts = ax.pie(
            grouped_data.values,
            labels=[''] * len(grouped_data),
            colors=VIBRANT_COLORS[:len(grouped_data)],
            wedgeprops=dict(width=0.9, edgecolor='white', linewidth=2),
            startangle=90
        )

        for i, p in enumerate(wedges):
            ang = (p.theta2 - p.theta1) / 2. + p.theta1
            y = np.sin(np.deg2rad(ang))
            x = np.cos(np.deg2rad(ang))

            color = 'white' if percentages.iloc[i] > 10 else 'black'

            ax.text(x * 0.6, y * 0.6, f'{percentages.iloc[i]}%',
                    ha='center', va='center', fontsize=10,
                    fontweight='bold', color=color)

            label_x = x * 1.2
            label_y = y * 1.2
            ha = 'left' if x > 0 else 'right'

            ax.text(label_x, label_y, f'{grouped_data.index[i]}',
                    ha=ha, va='center', fontsize=10)

        plt.title('Göndericiye Göre Harcama Dağılımı', pad=20, size=14, weight='bold')

        fig.patch.set_facecolor('none')
        fig.patch.set_alpha(0)
        ax.axis('equal')

        plt.tight_layout(pad=2.0)
        buffer = io.BytesIO()
        plt.savefig(
            buffer,
            format='png',
            bbox_inches='tight',
            dpi=100,
            transparent=True,
            pad_inches=0.3
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


