// GeNarrative UI - Main JavaScript

// Swiper availability check
function checkSwiperAvailability() {
    if (typeof Swiper === 'undefined') {
        console.error('Swiper.js が読み込まれていません');
        utils.showError('スライダーライブラリの読み込みに失敗しました', document.body);
        return false;
    }
    console.log('Swiper.js が正常に読み込まれました (Local Version)');
    return true;
}

// Global Swiper configurations
const swiperDefaults = {
    loop: false,
    grabCursor: true,
    keyboard: {
        enabled: true,
    },
    mousewheel: false,
    speed: 400,
};

// Utility functions
const utils = {
    // デバウンス関数
    debounce: function(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    // 画像の遅延読み込み
    lazyLoadImages: function() {
        const images = document.querySelectorAll('img[data-src]');
        
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.classList.remove('lazy');
                    imageObserver.unobserve(img);
                }
            });
        });

        images.forEach(img => imageObserver.observe(img));
    },

    // ローディングスピナーの制御
    showLoading: function(container) {
        const spinner = document.createElement('div');
        spinner.className = 'loading-spinner';
        spinner.innerHTML = '<div class="spinner"></div>';
        container.appendChild(spinner);
        return spinner;
    },

    hideLoading: function(spinner) {
        if (spinner && spinner.parentNode) {
            spinner.parentNode.removeChild(spinner);
        }
    },

    // エラーメッセージの表示
    showError: function(message, container) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.textContent = message;
        container.appendChild(errorDiv);
        
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.parentNode.removeChild(errorDiv);
            }
        }, 5000);
    }
};

// Swiper初期化ヘルパー
const swiperManager = {
    instances: new Map(),

    create: function(selector, options = {}) {
        if (!checkSwiperAvailability()) {
            return null;
        }
        
        const element = document.querySelector(selector);
        if (!element) {
            console.warn(`Swiper element not found: ${selector}`);
            return null;
        }

        const config = { ...swiperDefaults, ...options };
        const swiper = new Swiper(selector, config);
        
        this.instances.set(selector, swiper);
        console.log(`Swiper initialized: ${selector}`);
        return swiper;
    },

    destroy: function(selector) {
        const swiper = this.instances.get(selector);
        if (swiper) {
            swiper.destroy(true, true);
            this.instances.delete(selector);
        }
    },

    update: function(selector) {
        const swiper = this.instances.get(selector);
        if (swiper) {
            swiper.update();
        }
    },

    destroyAll: function() {
        this.instances.forEach((swiper, selector) => {
            swiper.destroy(true, true);
        });
        this.instances.clear();
    }
};

// ページ固有の初期化
const pageHandlers = {
    // ホームページ
    index: function() {
        console.log('ホームページが読み込まれました');
        utils.lazyLoadImages();
    },

    // Swiperデモページ
    swiperDemo: function() {
        console.log('Swiperデモページが読み込まれました');
        
        // 基本的なSwiper
        swiperManager.create('.basic-swiper', {
            loop: true,
            pagination: {
                el: '.swiper-pagination',
                clickable: true,
            },
            navigation: {
                nextEl: '.swiper-button-next',
                prevEl: '.swiper-button-prev',
            },
            autoplay: {
                delay: 3000,
                disableOnInteraction: false,
            },
        });

        // カード型Swiper
        swiperManager.create('.card-swiper', {
            slidesPerView: 1,
            spaceBetween: 20,
            pagination: {
                el: '.card-swiper .swiper-pagination',
                clickable: true,
            },
            breakpoints: {
                640: {
                    slidesPerView: 2,
                },
                1024: {
                    slidesPerView: 3,
                },
            },
        });

        // 縦スクロールSwiper
        swiperManager.create('.vertical-swiper', {
            direction: 'vertical',
            slidesPerView: 1,
            spaceBetween: 0,
            mousewheel: true,
            pagination: {
                el: '.vertical-swiper .swiper-pagination',
                clickable: true,
            },
        });
    },

    // ギャラリーページ
    gallery: function() {
        console.log('ギャラリーページが読み込まれました');
        
        // サムネイルSwiper
        const galleryThumbs = swiperManager.create('.gallery-thumbs', {
            spaceBetween: 10,
            slidesPerView: 4,
            freeMode: true,
            watchSlidesProgress: true,
            breakpoints: {
                640: {
                    slidesPerView: 6,
                },
                1024: {
                    slidesPerView: 8,
                },
            },
        });

        // メインギャラリーSwiper
        if (galleryThumbs) {
            swiperManager.create('.gallery-swiper', {
                spaceBetween: 10,
                navigation: {
                    nextEl: '.swiper-button-next',
                    prevEl: '.swiper-button-prev',
                },
                pagination: {
                    el: '.swiper-pagination',
                    type: 'fraction',
                },
                thumbs: {
                    swiper: galleryThumbs,
                },
                keyboard: {
                    enabled: true,
                },
                zoom: {
                    maxRatio: 3,
                },
            });
        }

        utils.lazyLoadImages();
    }
};

// DOM読み込み完了時の初期化
document.addEventListener('DOMContentLoaded', function() {
    console.log('GeNarrative UI が読み込まれました');

    // Swiper.js の可用性をチェック
    if (!checkSwiperAvailability()) {
        return;
    }

    // ドロップダウンメニューの初期化
    dropdownManager.init();

    // 現在のページを判定
    const path = window.location.pathname;
    let currentPage = 'index';
    
    if (path.includes('swiper-demo')) {
        currentPage = 'swiperDemo';
    } else if (path.includes('gallery')) {
        currentPage = 'gallery';
    }

    // ページ固有の初期化を実行
    if (pageHandlers[currentPage]) {
        pageHandlers[currentPage]();
    }

    // レスポンシブ対応：ウィンドウリサイズ時の処理
    window.addEventListener('resize', utils.debounce(() => {
        console.log('ウィンドウがリサイズされました');
        
        // すべてのSwiperインスタンスを更新
        swiperManager.instances.forEach((swiper, selector) => {
            swiper.update();
        });
    }, 250));

    // ページ離脱時のクリーンアップ
    window.addEventListener('beforeunload', () => {
        swiperManager.destroyAll();
    });
});

// 追加のユーティリティ：画像エラーハンドリング
document.addEventListener('error', function(e) {
    if (e.target.tagName === 'IMG') {
        console.warn('画像の読み込みに失敗しました:', e.target.src);
        e.target.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZGRkIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCwgc2Fucy1zZXJpZiIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzk5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPuOCpOODoeODvOOCuOOBjOS4jeW+l+OBm+OCk+OBoOOBi+OCiTwvdGV4dD48L3N2Zz4=';
        e.target.alt = '画像が見つかりません';
    }
}, true);

// Swiperのエラーハンドリング
window.addEventListener('error', function(e) {
    if (e.message && e.message.includes('Swiper')) {
        console.error('Swiperエラー:', e.message);
        utils.showError('スライダーの初期化に失敗しました', document.body);
    }
});

// グローバルオブジェクトとして公開
// Dropdown menu handler
const dropdownManager = {
    init: function() {
        const dropdowns = document.querySelectorAll('.dropdown');
        
        dropdowns.forEach(dropdown => {
            const toggle = dropdown.querySelector('.dropdown-toggle');
            const menu = dropdown.querySelector('.dropdown-menu');
            let hoverTimeout;
            
            if (!toggle || !menu) return;
            
            // マウスがドロップダウン要素に入った時
            dropdown.addEventListener('mouseenter', () => {
                clearTimeout(hoverTimeout);
                menu.style.display = 'block';
                
                // アニメーション用の少し遅延をつけて表示
                requestAnimationFrame(() => {
                    menu.style.opacity = '1';
                    menu.style.transform = 'translateY(0)';
                });
            });
            
            // マウスがドロップダウン要素から出た時
            dropdown.addEventListener('mouseleave', () => {
                // 少し遅延をつけてメニューを隠す（マウスが戻ってくる可能性を考慮）
                hoverTimeout = setTimeout(() => {
                    menu.style.opacity = '0';
                    menu.style.transform = 'translateY(-10px)';
                    
                    // アニメーションが完了してからdisplay:noneにする
                    setTimeout(() => {
                        menu.style.display = 'none';
                    }, 300);
                }, 150); // 150ms の猶予時間
            });
            
            // メニュー項目のクリックでメニューを閉じる
            menu.addEventListener('click', (e) => {
                if (e.target.tagName === 'A') {
                    menu.style.opacity = '0';
                    menu.style.transform = 'translateY(-10px)';
                    setTimeout(() => {
                        menu.style.display = 'none';
                    }, 300);
                }
            });
        });
    }
};

window.GeNarrative = {
    utils,
    swiperManager,
    pageHandlers,
    dropdownManager
};
