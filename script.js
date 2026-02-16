// Основные функции для приложения
document.addEventListener('DOMContentLoaded', function() {
    console.log('Приложение загружено');

    // Инициализация всех форм
    initForms();

    // Инициализация кнопок
    initButtons();
});

function initForms() {
    // Инициализация форм с валидацией
    const forms = document.querySelectorAll('form[data-validate]');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!validateForm(this)) {
                e.preventDefault();
            }
        });
    });
}

function validateForm(form) {
    let isValid = true;
    const requiredFields = form.querySelectorAll('[required]');

    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            showError(field, 'Это поле обязательно для заполнения');
            isValid = false;
        } else {
            clearError(field);
        }
    });

    return isValid;
}

function showError(element, message) {
    clearError(element);
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    errorDiv.style.color = '#dc3545';
    errorDiv.style.fontSize = '12px';
    errorDiv.style.marginTop = '5px';
    element.parentNode.appendChild(errorDiv);
    element.style.borderColor = '#dc3545';
}

function clearError(element) {
    const errorDiv = element.parentNode.querySelector('.error-message');
    if (errorDiv) {
        errorDiv.remove();
    }
    element.style.borderColor = '';
}

function initButtons() {
    // Инициализация кнопок с подтверждением
    const confirmButtons = document.querySelectorAll('[data-confirm]');
    confirmButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            const message = this.dataset.confirm || 'Вы уверены?';
            if (!confirm(message)) {
                e.preventDefault();
            }
        });
    });
}

// Уведомления
function showNotification(message, type = 'info') {
    const container = document.getElementById('notification-container');
    if (!container) return;

    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
        <span>${message}</span>
    `;

    container.appendChild(notification);

    // Автоматическое скрытие
    setTimeout(() => {
        notification.classList.add('fade-out');
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Форматирование чисел
function formatNumber(num, decimals = 2) {
    return parseFloat(num).toFixed(decimals);
}

// Генерация отчета
function generateReport() {
    alert('Функция генерации отчета будет реализована в следующей версии');
}