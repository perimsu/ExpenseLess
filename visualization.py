import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
from flask import Flask, render_template

app = Flask(__name__)

VIBRANT_COLORS = [
    '#FF6384',  # Kırmızı
    '#36A2EB',  # Mavi
    '#FFCE56',  # Sarı
    '#4BC0C0',  # Camgöbeği
    '#9966FF',  # Mor
    '#FF9F40',  # Turuncu
    '#C9CBCF',  # Gri
    '#8BC34A',  # Yeşil
    '#FF5722',  # Koyu Turuncu
    '#795548',  # Kahverengi
    '#00BCD4',  # Açık Camgöbeği
    '#E91E63',  # Pembe
    '#9C27B0',  # Lila
    '#3F51B5',  # Lacivert
    '#03A9F4',  # Açık Mavi
    '#CDDC39',  # Açık Yeşil
    '#FF9800',  # Turuncu
    '#673AB7',  # Mor
    '#2196F3',  # Mavi
    '#009688',  # Teal
]

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    emails = [
        {'date': '2024-01-01', 'total_amount': 100},
        {'date': '2024-02-01', 'total_amount': 150},
        {'date': '2024-03-01', 'total_amount': 120},
        {'date': '2024-04-01', 'total_amount': 200},
    ]

    plot_url = generate_plot(emails)

    return render_template('dashboard.html', plot_url=plot_url)

def generate_plot(emails):
    df = pd.DataFrame(emails)

    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['total_amount'] = pd.to_numeric(df['total_amount'], errors='coerce')

    df_grouped = df.groupby(df['date'].dt.to_period("M")).sum()

    fig, ax = plt.subplots(figsize=(8, 8))
    df_grouped['total_amount'].plot(
        kind='pie',
        ax=ax,
        colors=VIBRANT_COLORS[:len(df_grouped)],
        autopct='%1.1f%%',
        startangle=90
    )
    ax.set_ylabel("")
    ax.set_title("Aylık Toplam Harcamalar (Pie Chart)")

    img = io.BytesIO()
    plt.tight_layout()
    plt.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode('utf8')
    plt.close(fig)

    return plot_url

if __name__ == '__main__':
    app.run(debug=True)
