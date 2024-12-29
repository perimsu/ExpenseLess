const API_ENDPOINTS = {
  // flask api bağlarken linkleri güncelle
    USER_INFO: '/api/user',
    UPDATE_PROFILE: '/api/user/update',
    UPDATE_PHOTO: '/api/user/photo',
    CATEGORIES: '/api/categories',
    TRANSACTIONS: '/api/transactions',
    LOGOUT: '/api/logout',
    SPENDING_STATS: '/api/spending/stats'
};

const profileImage = document.querySelector('.profile-image img');
const fullNameInput = document.querySelector('.info-group input[type="text"]');
const emailInput = document.querySelector('.info-group input[type="email"]');
const phoneInput = document.querySelector('.info-group input[type="tel"]');
const editButtons = document.querySelectorAll('.edit-btn');
const changePhotoBtn = document.querySelector('.change-photo-btn');
const headerAvatar = document.querySelector('.user-info img');
const welcomeText = document.querySelector('.user-info span');
const categoryList = document.querySelector('.category-list');
const addCategoryInput = document.querySelector('.add-category input');
const addCategoryBtn = document.querySelector('.add-category .add-btn');
const profileDropdownToggle = document.getElementById('profileDropdownToggle');
const userDropdownMenu = document.getElementById('userDropdownMenu');

const mostSpentCategory = document.querySelector('.stats-grid .stat-card:nth-child(1) .stat-value');
const mostSpentCategoryTotal = document.querySelector('.stats-grid .stat-card:nth-child(1) .stat-detail');
const highestSpendingDate = document.querySelector('.stats-grid .stat-card:nth-child(2) .stat-value');
const highestSpendingTotal = document.querySelector('.stats-grid .stat-card:nth-child(2) .stat-detail');
const monthlyAverage = document.querySelector('.stats-grid .stat-card:nth-child(3) .stat-value');
const transactionsList = document.querySelector('.transactions-list');

// API servisi
const apiService = {
    async fetchUserData() {
        try {
            const response = await fetch(API_ENDPOINTS.USER_INFO);
            if (!response.ok) throw new Error('Network response was not ok');
            return await response.json();
        } catch (error) {
            console.error('Error fetching user data:', error);
            return null;
        }
    },

    async updateUserField(fieldName, value) {
        try {
            const response = await fetch(API_ENDPOINTS.UPDATE_PROFILE, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ field: fieldName, value: value })
            });
            if (!response.ok) throw new Error('Update failed');
            return await response.json();
        } catch (error) {
            console.error('Error updating user field:', error);
            return null;
        }
    },

    async updateProfilePhoto(file) {
        try {
            const formData = new FormData();
            formData.append('photo', file);
            const response = await fetch(API_ENDPOINTS.UPDATE_PHOTO, {
                method: 'POST',
                body: formData
            });
            if (!response.ok) throw new Error('Photo upload failed');
            return await response.json();
        } catch (error) {
            console.error('Error uploading photo:', error);
            return null;
        }
    },

    async fetchCategories() {
        try {
            const response = await fetch(API_ENDPOINTS.CATEGORIES);
            if (!response.ok) throw new Error('Network response was not ok');
            return await response.json();
        } catch (error) {
            console.error('Error fetching categories:', error);
            return null;
        }
    },

    async addCategory(name) {
        try {
            const response = await fetch(API_ENDPOINTS.CATEGORIES, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name })
            });
            if (!response.ok) throw new Error('Failed to add category');
            return await response.json();
        } catch (error) {
            console.error('Error adding category:', error);
            return null;
        }
    },

    async deleteCategory(id) {
        try {
            const response = await fetch(`${API_ENDPOINTS.CATEGORIES}/${id}`, {
                method: 'DELETE'
            });
            if (!response.ok) throw new Error('Failed to delete category');
            return true;
        } catch (error) {
            console.error('Error deleting category:', error);
            return false;
        }
    },

    async fetchSpendingStats() {
        try {
            const response = await fetch(API_ENDPOINTS.SPENDING_STATS);
            if (!response.ok) throw new Error('Network response was not ok');
            return await response.json();
        } catch (error) {
            console.error('Error fetching spending stats:', error);
            return null;
        }
    },

    async fetchTransactions() {
        try {
            const response = await fetch(API_ENDPOINTS.TRANSACTIONS);
            if (!response.ok) throw new Error('Network response was not ok');
            return await response.json();
        } catch (error) {
            console.error('Error fetching transactions:', error);
            return null;
        }
    }
};

// UI güncelleme fonksiyonları
const uiHelpers = {
    updateUserInfo(userData) {
        if (!userData) return;
        
        fullNameInput.value = userData.fullName || '';
        emailInput.value = userData.email || '';
        phoneInput.value = userData.phone || '';
        const photoUrl = userData.photoUrl || 'image/userProfile.png';
        profileImage.src = photoUrl;
        headerAvatar.src = photoUrl;
        welcomeText.textContent = userData.fullName ? `Welcome, ${userData.fullName}` : 'Welcome';
    },

    updateSpendingStats(stats) {
        if (!stats) return;

        if (stats.mostSpentCategory) {
            mostSpentCategory.textContent = stats.mostSpentCategory.name || 'N/A';
            mostSpentCategoryTotal.textContent = `Total: ₺${stats.mostSpentCategory.total?.toLocaleString() || '0'}`;
        }

        if (stats.highestSpendingDate) {
            const date = new Date(stats.highestSpendingDate.date);
            highestSpendingDate.textContent = date.toLocaleDateString('en-US', { 
                year: 'numeric', 
                month: 'long', 
                day: 'numeric' 
            });
            highestSpendingTotal.textContent = `Total: ₺${stats.highestSpendingDate.total?.toLocaleString() || '0'}`;
        }

        monthlyAverage.textContent = `₺${stats.monthlyAverage?.toLocaleString() || '0'}`;
    },

    updateTransactionsList(transactions) {
        if (!transactions) return;
        
        transactionsList.innerHTML = transactions.map(transaction => `
            <div class="transaction-item">
                <div class="transaction-info">
                    <span class="transaction-date">
                        ${new Date(transaction.date).toLocaleDateString('en-US', {
                            year: 'numeric',
                            month: 'long',
                            day: 'numeric'
                        })}
                    </span>
                    <span class="transaction-description">${transaction.description}</span>
                </div>
                <span class="transaction-amount">₺${transaction.amount.toLocaleString()}</span>
            </div>
        `).join('');
    },

    updateCategoriesList(categories) {
        if (!categories) return;
        
        categoryList.innerHTML = categories.map(category => `
            <div class="category-item" data-id="${category.id}">
                <span>${category.name}</span>
                <button class="delete-btn" onclick="handleDeleteCategory(${category.id})">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `).join('');
    }
};


async function handleDeleteCategory(categoryId) {
    const success = await apiService.deleteCategory(categoryId);
    if (success) {
        const categories = await apiService.fetchCategories();
        uiHelpers.updateCategoriesList(categories);
    }
}

async function handleAddCategory() {
    const categoryName = addCategoryInput.value.trim();
    if (!categoryName) return;

    const newCategory = await apiService.addCategory(categoryName);
    if (newCategory) {
        addCategoryInput.value = '';
        const categories = await apiService.fetchCategories();
        uiHelpers.updateCategoriesList(categories);
    }
}

async function handleLogout() {
    try {
        const response = await fetch(API_ENDPOINTS.LOGOUT, {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            window.location.href = 'index.html';
        } else {
            console.error('Logout failed');
            alert('Failed to logout. Please try again.');
        }
    } catch (error) {
        console.error('Logout error:', error);
        alert('An error occurred while logging out');
    }
}


addCategoryBtn.addEventListener('click', handleAddCategory);

changePhotoBtn.addEventListener('click', () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.onchange = async (e) => {
        const file = e.target.files[0];
        if (file) {
            const result = await apiService.updateProfilePhoto(file);
            if (result?.photoUrl) {
                profileImage.src = result.photoUrl;
                headerAvatar.src = result.photoUrl;
            }
        }
    };
    input.click();
});


if (profileDropdownToggle && userDropdownMenu) {
    profileDropdownToggle.addEventListener('click', (e) => {
        e.stopPropagation();
        userDropdownMenu.classList.toggle('active');
    });

    document.addEventListener('click', (e) => {
        if (!userDropdownMenu.contains(e.target) && !profileDropdownToggle.contains(e.target)) {
            userDropdownMenu.classList.remove('active');
        }
    });
}


document.addEventListener('DOMContentLoaded', async () => {
    try {
        const [userData, spendingStats, transactions, categories] = await Promise.all([
            apiService.fetchUserData(),
            apiService.fetchSpendingStats(),
            apiService.fetchTransactions(),
            apiService.fetchCategories()
        ]);

        uiHelpers.updateUserInfo(userData);
        uiHelpers.updateSpendingStats(spendingStats);
        uiHelpers.updateTransactionsList(transactions);
        uiHelpers.updateCategoriesList(categories);

        const logoutButton = document.getElementById('logoutButton');
        if (logoutButton) {
            logoutButton.addEventListener('click', async () => {
                try {
                    const response = await fetch(API_ENDPOINTS.LOGOUT, {
                        method: 'POST',
                        credentials: 'include',
                        headers: {
                            'Content-Type': 'application/json'
                        }
                    });
                    
                    if (response.ok) {
                        window.location.href = 'index.html';
                    } else {
                        throw new Error('Logout failed');
                    }
                } catch (error) {
                    console.error('Logout error:', error);
                    alert('Failed to logout. Please try again.');
                }
            });
        }
    } catch (error) {
        console.error('Error initializing profile:', error);
    }
}); 