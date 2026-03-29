/**
 * AI Stylist Platform - Main JavaScript
 */

// Глобальные утилиты
const Utils = {
    // Форматирование цены
    formatPrice: (price) => {
        return new Intl.NumberFormat('kk-KZ').format(price) + ' ₸';
    },
    
    // Показ уведомления
    showToast: (message, type = 'info') => {
        const toast = document.createElement('div');
        toast.className = `fixed top-4 right-4 px-6 py-3 rounded-lg shadow-lg z-50 animate-fade-in ${
            type === 'success' ? 'bg-green-500 text-white' :
            type === 'error' ? 'bg-red-500 text-white' :
            'bg-gray-800 text-white'
        }`;
        toast.textContent = message;
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 3000);
    },
    
    // Загрузка изображения как base64
    imageToBase64: (file) => {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    }
};

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    console.log('🎯 AI Stylist Platform loaded');
    
    // Добавляем класс анимации для всех карточек
    document.querySelectorAll('.product-card, .outfit-card').forEach((card, index) => {
        card.style.animationDelay = `${index * 0.1}s`;
        card.classList.add('animate-fade-in');
    });
    
    // Плавный скролл для якорных ссылок
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({ behavior: 'smooth' });
            }
        });
    });
});

// Сервис воркер для PWA (опционально)
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        // navigator.serviceWorker.register('/sw.js')
        //     .then(reg => console.log('SW registered:', reg))
        //     .catch(err => console.error('SW error:', err));
    });
}