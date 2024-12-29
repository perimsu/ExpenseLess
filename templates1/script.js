// API endpoints
const API_ENDPOINTS = {
    DASHBOARD: '/api/dashboard',
    USER_INFO: '/api/user',
    UPDATE_PROFILE: '/api/user/update',
    UPDATE_PHOTO: '/api/user/photo',
    CATEGORIES: '/api/categories',
    TRANSACTIONS: '/api/transactions',
    LOGOUT: '/api/logout',
    SPENDING_STATS: '/api/spending/stats'
};

// API servisi
const apiService = {
    async fetchDashboardData() {
        try {
            const response = await fetch(API_ENDPOINTS.DASHBOARD);
            if (!response.ok) throw new Error('Network response was not ok');
            return await response.json();
        } catch (error) {
            console.error('Error fetching dashboard data:', error);
            return null;
        }
    },

    async fetchUserData() {
        try {
            const response = await fetch(API_ENDPOINTS.USER_INFO);
            if (!response.ok) throw new Error('Network response was not ok');
            return await response.json();
        } catch (error) {
            console.error('Error fetching user data:', error);
            return null;
        }
    }
};

// UI Güncellemeleri için 
const uiHelpers = {
    updateCharts(data) {
        if (!data) return;
        
        spendingChart.data.datasets[0].data = data.monthlySpending;
        spendingChart.update();

        categoryChart.data.datasets[0].data = data.categorySpending;
        categoryChart.data.labels = data.categoryLabels;
        categoryChart.update();
    },

    updateTransactionsList(data) {
        if (!data) return;
        
        const transactionList = document.querySelector('.transaction-list');
        transactionList.innerHTML = data.recentTransactions.map(transaction => `
            <div class="transaction-item">
                <div>
                    <div>${transaction.description}</div>
                    <small>${new Date(transaction.date).toLocaleDateString('en-US')}</small>
                </div>
                <div class="transaction-amount">₺${transaction.amount.toLocaleString()}</div>
            </div>
        `).join('');
    },

    updateSummaryCards(data) {
        if (!data) return;

        document.querySelector('.total-spending .amount').textContent = `₺${data.totalSpending?.toLocaleString() || '0'}`;
        
        document.querySelector('.average-spending .amount').textContent = `₺${data.averageSpending?.toLocaleString() || '0'}`;
        
        document.querySelector('.total-orders .amount').textContent = data.totalTransactions?.toString() || '0';

        if (data.categoryStats) {
            document.querySelector('.category-stats').innerHTML = `
                <span class="stat-item">
                    <i class="fas fa-arrow-trend-up"></i>
                    Most: <strong>${data.categoryStats.mostSpent || 'N/A'}</strong>
                </span>
                <span class="stat-item">
                    <i class="fas fa-arrow-trend-down"></i>
                    Least: <strong>${data.categoryStats.leastSpent || 'N/A'}</strong>
                </span>
            `;
        }
    },

    updateUserInfo(userData) {
        if (!userData) return;
        
        const welcomeText = document.querySelector('.welcome-text');
        welcomeText.textContent = userData.fullName ? `Welcome, ${userData.fullName}` : 'Welcome';
    }
};

const spendingChart = new Chart(document.getElementById('spendingChart').getContext('2d'), {
    type: 'line',
    data: {
        labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
        datasets: [{
            label: 'Monthly Expenditure (₺)',
            data: [],
            borderColor: '#3498DB',
            tension: 0.4,
            fill: true,
            backgroundColor: 'rgba(52, 152, 219, 0.1)'
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'top',
                labels: {
                    boxWidth: 12,
                    padding: 15
                }
            }
        },
        scales: {
            y: {
                beginAtZero: true,
                ticks: {
                    callback: function(value) {
                        return '₺' + value.toLocaleString();
                    },
                    maxTicksLimit: 6
                }
            },
            x: {
                grid: {
                    display: false
                },
                ticks: {
                    padding: 5
                }
            }
        }
    }
});

const categoryChart = new Chart(document.getElementById('categoryChart').getContext('2d'), {
    type: 'doughnut',
    data: {
        labels: [],
        datasets: [{
            data: [],
            backgroundColor: [
                '#3498DB',
                '#2ECC71',
                '#E74C3C',
                '#F1C40F',
                '#95A5A6'
            ]
        }]
    },
    options: {
        responsive: true,
        plugins: {
            legend: {
                position: 'bottom',
            }
        }
    }
});

document.addEventListener('DOMContentLoaded', async () => {
    const [dashboardData, userData] = await Promise.all([
        apiService.fetchDashboardData(),
        apiService.fetchUserData()
    ]);

    uiHelpers.updateCharts(dashboardData);
    uiHelpers.updateTransactionsList(dashboardData);
    uiHelpers.updateSummaryCards(dashboardData);
    uiHelpers.updateUserInfo(userData);
});


document.querySelector('.time-range').addEventListener('change', async function(e) {
    const timeRange = e.target.value;
    try {
        const response = await fetch(`/api/dashboard?timeRange=${timeRange}`);
        if (!response.ok) throw new Error('Failed to fetch data');
        const data = await response.json();
        uiHelpers.updateCharts(data);
        uiHelpers.updateSummaryCards(data);
    } catch (error) {
        console.error('Error updating time range:', error);
    }
});
