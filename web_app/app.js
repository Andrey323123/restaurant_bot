console.log('Starting Telegram WebApp with Admin Panel...');

// --- Telegram WebApp Init ---
const tg = window.Telegram?.WebApp;

if (tg) {
    tg.ready();
    tg.expand();
    tg.MainButton.hide();
    tg.BackButton.hide();
} else {
    console.warn('Telegram WebApp not detected — debug mode');
}

// --- Логирование в файл ---
let logs = [];

function logToFile(msg, obj = '') {
    const line = `[${new Date().toISOString()}] ${msg} ${typeof obj === 'object' ? JSON.stringify(obj) : obj}`;
    logs.push(line);
    console.log(line);
}

// Функция для сохранения TXT (теперь только по запросу)
function saveLogs() {
    if (!logs.length) return;
    const blob = new Blob([logs.join('\n')], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'webapp_logs.txt';
    a.click();
    URL.revokeObjectURL(url);
}

// === АДМИНКА: проверяем по ID из бекенда ===
let user = tg?.initDataUnsafe?.user || null;
let adminConfig = { admin_id: null };
let isAdmin = false;

function updateAdminFlag() {
    isAdmin = Boolean(adminConfig?.admin_id && user?.id && String(user.id) === String(adminConfig.admin_id));
    logToFile('user:', user);
    logToFile('isAdmin:', isAdmin);
}

async function fetchAdminConfig() {
    try {
        const res = await fetch(`${API_BASE}/admin/config`);
        if (res.ok) {
            const data = await res.json();
            adminConfig = data || { admin_id: null };
        }
    } catch (e) {
        console.warn('Failed to load admin config', e);
    } finally {
        updateAdminFlag();
    }
}
// Убрано автоматическое saveLogs()

// --- Константы ---
const API_BASE = (location.protocol === 'https:' || location.hostname === 'localhost')
    ? (location.origin + '/api')
    : '/api';
const RESTAURANT_ADDRESS = 'ул. Советская, 1, Гомель, 246000';

let cart = JSON.parse(localStorage.getItem('cart')) || [];
let orderType = localStorage.getItem('orderType') || 'delivery';
let currentDiscount = 0; // Глобальная переменная для хранения текущей скидки

// --- Утилиты ---
const $ = (id) => document.getElementById(id);

function escapeHtml(str) {
    if (typeof str !== 'string') return str || '';
    return str.replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '<', '>': '>', '"': '&quot;', "'": '&#39;' }[m]));
}

function showToast(msg, duration = 2000) {
    const toast = $('toast');
    if (!toast) return;
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), duration);
}

function addClickHandler(el, handler) {
    if (!el) return;
    const wrapped = (e) => {
        e.preventDefault();
        e.stopPropagation();
        handler(e);
    };
    el.addEventListener('click', wrapped);
    el.addEventListener('touchend', wrapped);
}

// --- Модальные окна ---
function openModal(html) {
    const modal = $('modal');
    const content = $('modal-content');
    if (!modal || !content) return;

    content.innerHTML = `
        <button id="modal-close-x" class="absolute top-3 right-3 text-gray-500 text-xl font-bold">&times;</button>
        ${html}
    `;
    modal.classList.remove('hidden');
    modal.classList.add('show');

    setTimeout(() => {
        const closeBtn = $('modal-close-x');
        if (closeBtn) addClickHandler(closeBtn, closeModal);
    }, 0);

    modal.onclick = (e) => { if (e.target === modal) closeModal(); };
    content.onclick = (e) => e.stopPropagation();
}

function closeModal() {
    const modal = $('modal');
    if (modal) {
        modal.classList.remove('show');
        modal.classList.add('hidden');
    }
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
});

// --- Навигация ---
function updateNavigation(activeTab) {
    const menuBtn = $('menu-btn');
    const deliveryBtn = $('delivery-btn');
    const setActive = (el, active) => {
        if (!el) return;
        el.classList.toggle('text-orange-600', active);
        el.classList.toggle('font-bold', active);
        el.classList.toggle('text-gray-600', !active);
    };
    setActive(menuBtn, activeTab === 'menu');
    setActive(deliveryBtn, activeTab === 'delivery');
}

// --- Загрузка блюд ---
async function loadDishes(category = '') {
    try {
        const url = `${API_BASE}/dishes${category ? '?category=' + encodeURIComponent(category) : ''}`;
        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const dishes = await res.json();
        renderDishes(Array.isArray(dishes) ? dishes : []);
    } catch (e) {
        console.error('loadDishes error', e);
        showToast('Не удалось загрузить меню');
        renderDishes([]);
    }
}

function renderDishes(dishes) {
    const grid = $('dishes-grid');
    const empty = $('empty');
    if (!grid) return;

    grid.innerHTML = '';
    if (dishes.length === 0) {
        empty?.classList.remove('hidden');
        return;
    }
    empty?.classList.add('hidden');

    dishes.forEach(dish => {
        const card = document.createElement('div');
        card.className = 'dish-card cursor-pointer';
        card.innerHTML = `
            <div class="dish-image">
                <img src="${dish.image_url || '/web_app/assets/placeholder.png'}" alt="${escapeHtml(dish.name)}" class="w-full h-full object-cover">
            </div>
            <div class="p-3">
                <h3 class="font-semibold text-sm">${escapeHtml(dish.name)}</h3>
                <p class="text-xs text-gray-500 mt-1">${escapeHtml(dish.description || '')}</p>
                <div class="mt-2 text-orange-500 font-bold">${dish.price ? dish.price + ' BYN' : '—'}</div>
            </div>
        `;
        addClickHandler(card, () => openDishDetails(dish));
        grid.appendChild(card);
    });
}

function openDishDetails(dish) {
    openModal(`
        <h2 class="text-xl font-bold mb-3">${escapeHtml(dish.name)}</h2>
        <img src="${dish.image_url || '/web_app/assets/placeholder.png'}" class="w-full h-48 object-cover rounded mb-3">
        <p class="text-gray-700 mb-3">${escapeHtml(dish.description || 'Описание отсутствует')}</p>
        <div class="text-orange-600 font-bold text-lg mb-4">${dish.price ? dish.price + ' BYN' : '—'}</div>
        <button id="add-to-cart-btn" class="w-full bg-orange-500 text-white py-2 rounded-lg font-medium">Добавить в корзину</button>
    `);
    setTimeout(() => {
        const btn = $('add-to-cart-btn');
        if (btn) addClickHandler(btn, () => {
            addToCart(dish);
            closeModal();
        });
    }, 0);
}

// --- Корзина ---
function addToCart(dish) {
    const idx = cart.findIndex(i => i.id === dish.id);
    if (idx >= 0) {
        cart[idx].qty = (cart[idx].qty || 1) + 1;
    } else {
        cart.push({ ...dish, qty: 1 });
    }
    localStorage.setItem('cart', JSON.stringify(cart));
    updateCartCount();
    showToast(`${dish.name} добавлен`);
}

function updateCartCount() {
    const count = cart.reduce((sum, item) => sum + (item.qty || 1), 0);
    const badge = $('cart-count');
    if (badge) {
        badge.textContent = count;
        badge.classList.toggle('hidden', count === 0);
    }
}

function openCart() {
    if (cart.length === 0) {
        openModal('<p class="text-center py-6 text-gray-600">Ваша корзина пуста</p>');
        return;
    }

    let subtotal = 0;
    let itemsHtml = '<div class="space-y-3 max-h-60 overflow-y-auto pr-1">';
    cart.forEach((item, idx) => {
        const price = (item.price || 0) * (item.qty || 1);
        subtotal += price;
        itemsHtml += `
            <div class="flex justify-between items-start bg-gray-50 p-3 rounded">
                <div>
                    <div class="font-medium">${escapeHtml(item.name)}</div>
                    <div class="text-sm text-gray-500">${item.qty} × ${item.price} BYN</div>
                </div>
                <button class="text-red-500 text-sm remove-item" data-index="${idx}">Удалить</button>
            </div>
        `;
    });
    itemsHtml += `</div>`;

    const total = subtotal * (1 - currentDiscount / 100);
    openModal(`
        <h2 class="text-xl font-bold mb-4">🛒 Корзина</h2>
        ${itemsHtml}
        <div class="mt-3">
            <input id="promo-code" class="w-full p-2 border rounded mb-2" placeholder="Введите промокод">
            <button id="apply-promo" class="w-full bg-blue-500 text-white py-2 rounded mb-3">Применить</button>
            ${currentDiscount > 0 ? `<p class="text-green-600 text-sm">Скидка: ${currentDiscount}% (экономия ${(subtotal * currentDiscount / 100).toFixed(2)} BYN)</p>` : ''}
        </div>
        <div class="mt-4 pt-3 border-t border-gray-200 flex justify-between items-center">
            <div class="font-bold text-lg">Итого: <span id="cart-total">${total.toFixed(2)} BYN</span></div>
            <div class="flex gap-2">
                <button id="clear-cart" class="px-3 py-1 bg-gray-200 rounded text-sm">Очистить</button>
                <button id="pay-btn" class="px-4 py-2 bg-green-600 text-white rounded font-medium">Оплатить</button>
            </div>
        </div>
    `);

    setTimeout(() => {
        document.querySelectorAll('.remove-item').forEach(btn => {
            addClickHandler(btn, (e) => {
                const idx = parseInt(e.target.dataset.index);
                if (!isNaN(idx)) {
                    cart.splice(idx, 1);
                    localStorage.setItem('cart', JSON.stringify(cart));
                    updateCartCount();
                    openCart();
                }
            });
        });

        const clearBtn = $('clear-cart');
        if (clearBtn) addClickHandler(clearBtn, () => {
            cart = [];
            currentDiscount = 0;
            localStorage.setItem('cart', '[]');
            updateCartCount();
            closeModal();
        });

        const payBtn = $('pay-btn');
        if (payBtn) addClickHandler(payBtn, () => {
            createPayment(total);
        });

        const applyPromo = $('apply-promo');
        if (applyPromo) {
            addClickHandler(applyPromo, async () => {
                console.log('Apply promo clicked'); // Отладка
                const promoCode = $('promo-code')?.value.trim();
                if (promoCode) {
                    try {
                        const res = await fetch(`${API_BASE}/validate_promo`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ code: promoCode })
                        });
                        const data = await res.json();
                        console.log('Server response:', data); // Отладка
                        if (res.ok && data.valid) {
                            currentDiscount = parseFloat(data.discount) || 0;
                            const newTotal = subtotal * (1 - currentDiscount / 100);
                            const totalElement = $('cart-total');
                            if (totalElement) totalElement.textContent = `${newTotal.toFixed(2)} BYN`;
                            showToast(`Промокод применён! Скидка ${currentDiscount}%`);
                        } else {
                            currentDiscount = 0;
                            const totalElement = $('cart-total');
                            if (totalElement) totalElement.textContent = `${subtotal.toFixed(2)} BYN`;
                            showToast(data.error || 'Неверный или истёкший промокод');
                        }
                    } catch (e) {
                        console.error('Fetch error:', e);
                        currentDiscount = 0;
                        const totalElement = $('cart-total');
                        if (totalElement) totalElement.textContent = `${subtotal.toFixed(2)} BYN`;
                        showToast('Ошибка при проверке промокода');
                    }
                } else {
                    showToast('Введите промокод');
                }
            });
        }
    }, 0);
}

// --- Оплата через CryptoBot ---
async function createPayment(amount) {
    if (amount <= 0) {
        showToast('Корзина пуста');
        return;
    }

    const order_id = Date.now().toString();
    const delivery_addr = localStorage.getItem('delivery_addr') || RESTAURANT_ADDRESS;

    // Формируем данные заказа в формате, ожидаемом API
    const paymentData = {
        amount: amount.toFixed(2),
        order_id: order_id,
        description: 'Заказ в La Tavola'
    };

    const orderData = {
        dishes: cart.map(item => ({
            id: item.id,
            name: item.name,
            qty: item.qty || 1,
            price: item.price || 0
        })),
        address: orderType === 'delivery' ? delivery_addr : RESTAURANT_ADDRESS,
        total: amount.toFixed(2),
        order_id: order_id,
        orderType: orderType,
        user: {
            id: user?.id,
            first_name: user?.first_name,
            username: user?.username
        },
        timestamp: new Date().toISOString()
    };

    try {
        const res = await fetch(`${API_BASE}/create_payment`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ payment: paymentData, orderData: orderData })
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (data.status === 'success' && data.payment_url) {
            // Отправка данных заказа в Telegram
            if (tg?.sendData) {
                tg.sendData(JSON.stringify(orderData));
                logToFile('Order sent to Telegram:', orderData);
            }

            if (tg?.openLink) {
                tg.openLink(data.payment_url);
            } else {
                window.location.href = data.payment_url; // Для теста вне Telegram
            }

            // Очищаем корзину после успешного редиректа
            cart = [];
            currentDiscount = 0;
            localStorage.setItem('cart', JSON.stringify(cart));
            updateCartCount();

            showToast('Переход к оплате через CryptoBot...', 1500);
            closeModal();
        } else {
            showToast(data.error || 'Ошибка: не получена ссылка на оплату');
        }
    } catch (e) {
        console.error('Payment error:', e);
        showToast('Ошибка при создании платежа');
    }
}

// --- Доставка и карта ---
function openDelivery() {
    updateNavigation('delivery');
    const savedAddr = localStorage.getItem('delivery_addr') || RESTAURANT_ADDRESS;

    let htmlContent = `
        <h2 class="text-xl font-bold mb-3">📍 ${orderType === 'delivery' ? 'Доставка' : 'Самовывоз'}</h2>
    `;

    if (orderType === 'delivery') {
        htmlContent += `
            <div id="map-container"></div>
            <p class="text-sm text-gray-600 mb-2">Адрес ресторана: <strong>${escapeHtml(RESTAURANT_ADDRESS)}</strong></p>
            <input id="delivery-addr" type="text" class="w-full p-3 border rounded mb-3" placeholder="Ваш адрес (для доставки)" value="${escapeHtml(savedAddr)}">
            <button id="geo-btn" class="w-full bg-blue-500 text-white py-2 rounded mb-3">📍 Определить мою локацию</button>
            <button id="save-delivery" class="w-full bg-green-600 text-white py-3 rounded font-medium">Сохранить адрес</button>
        `;
    } else {
        htmlContent += `
            <p class="text-sm text-gray-600 mb-2">Адрес ресторана: <strong>${escapeHtml(RESTAURANT_ADDRESS)}</strong></p>
            <p class="text-gray-700 mb-3">Среднее время готовки: ~30 минут</p>
            <p class="text-gray-500 mb-3">Пожалуйста, приезжайте после получения уведомления о готовности.</p>
            <button id="confirm-pickup" class="w-full bg-green-600 text-white py-3 rounded font-medium">Подтвердить самовывоз</button>
        `;
    }

    openModal(htmlContent);

    setTimeout(() => {
        if (orderType === 'delivery' && window.ymaps) {
            ymaps.ready(() => {
                const map = new ymaps.Map($('map-container'), {
                    center: [52.4414, 30.9829], // Гомель
                    zoom: 15
                });
                map.geoObjects.add(new ymaps.Placemark([52.4414, 30.9829], {
                    balloonContent: 'La Tavola, Гомель'
                }));

                const geoBtn = $('geo-btn');
                if (geoBtn) {
                    addClickHandler(geoBtn, async () => {
                        let location = null;
                        if (tg && tg.requestLocation) {
                            location = await new Promise((resolve) => {
                                tg.requestLocation({ onSuccess: resolve });
                            });
                        } else if (navigator.geolocation) {
                            location = await new Promise((resolve, reject) => {
                                navigator.geolocation.getCurrentPosition(resolve, reject);
                            });
                        }
                        if (location) {
                            const { latitude: lat, longitude: lng } = location.coords || location;
                            localStorage.setItem('delivery_geo', JSON.stringify({ lat, lng }));

                            // Геокодирование для получения адреса
                            ymaps.geocode([lat, lng], { results: 1 }).then(res => {
                                const addr = res.geoObjects.get(0).getAddressLine();
                                const addrInput = $('delivery-addr');
                                if (addrInput) {
                                    addrInput.value = addr;
                                    localStorage.setItem('delivery_addr', addr);
                                    showToast('Локация и адрес сохранены!');
                                }
                            }).catch(e => {
                                console.error('Geocode error', e);
                                showToast('Локация сохранена, но адрес не определён');
                            });

                            // Обновление карты
                            map.setCenter([lat, lng]);
                            map.geoObjects.add(new ymaps.Placemark([lat, lng], {
                                balloonContent: 'Ваша локация'
                            }));
                        } else {
                            showToast('Геолокация недоступна');
                        }
                    });
                }

                const saveBtn = $('save-delivery');
                if (saveBtn) addClickHandler(saveBtn, () => {
                    const addr = $('delivery-addr')?.value.trim() || '';
                    if (!addr) return showToast('Введите адрес');
                    localStorage.setItem('delivery_addr', addr);
                    tg?.sendData?.(JSON.stringify({ action: 'set_delivery_address', address: addr }));
                    showToast('Адрес сохранён');
                    closeModal();
                });
            });
        } else if (orderType === 'restaurant') {
            const confirmBtn = $('confirm-pickup');
            if (confirmBtn) addClickHandler(confirmBtn, () => {
                showToast('Самовывоз подтверждён. Ожидайте уведомления о готовности (~30 минут).');
                closeModal();
            });
        }
    }, 0);
}

// --- История заказов ---
async function fetchUserOrders() {
    try {
        const userId = user?.id || 0;
        const res = await fetch(`${API_BASE}/user/${userId}/orders`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const orders = await res.json();
        return Array.isArray(orders) ? orders : [];
    } catch (e) {
        console.error('fetchOrders error', e);
        return [];
    }
}

// --- Обновление статуса заказа ---
async function updateOrderStatus(orderId, newStatus) {
    try {
        const res = await fetch(`${API_BASE}/order/${orderId}/status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Telegram-Id': user?.id },
            body: JSON.stringify({ status: newStatus })
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (data.status === 'success') {
            showToast(`Статус заказа #${orderId} обновлён на ${newStatus}`);
            openProfile(); // Перезагружаем профиль для отображения нового статуса
        } else {
            showToast(data.error || 'Ошибка обновления статуса');
        }
    } catch (e) {
        console.error('Update status error:', e);
        showToast('Ошибка при обновлении статуса');
    }
}

// --- Профиль (+ админка для админа) ---
async function openProfile() {
    const savedAddr = localStorage.getItem('delivery_addr') || '';
    const name = user ? (user.first_name || user.username || 'Пользователь') : 'Гость';

    const orders = await fetchUserOrders();
    let ordersHtml = orders.length
        ? '<div class="space-y-2 mt-2">' +
            orders.map(order => {
                let statusClass = '';
                switch (order.status) {
                    case 'delivered':
                        statusClass = 'text-green-600';
                        break;
                    case 'on_delivery':
                        statusClass = 'text-yellow-600';
                        break;
                    case 'cooking':
                        statusClass = 'text-blue-600';
                        break;
                    case 'accepted':
                        statusClass = 'text-purple-600';
                        break;
                    case 'pending':
                    case 'failed':
                        statusClass = 'text-gray-600';
                        break;
                }
                return `
                    <div class="p-2 bg-gray-50 rounded text-sm">
                        <div><strong>Заказ #${order.id}</strong></div>
                        <div>Сумма: ${order.total} BYN</div>
                        <div><span class="${statusClass} font-medium">Статус: ${escapeHtml(order.status || '—')}</span></div>
                        <div>${new Date(order.created_at).toLocaleDateString()}</div>
                        ${isAdmin ? `
                            <select id="status-select-${order.id}" class="mt-2 w-full p-1 border rounded">
                                <option value="pending" ${order.status === 'pending' ? 'selected' : ''}>Ожидает</option>
                                <option value="accepted" ${order.status === 'accepted' ? 'selected' : ''}>Принят</option>
                                <option value="cooking" ${order.status === 'cooking' ? 'selected' : ''}>Готовится</option>
                                <option value="on_delivery" ${order.status === 'on_delivery' ? 'selected' : ''}>В доставке</option>
                                <option value="delivered" ${order.status === 'delivered' ? 'selected' : ''}>Доставлен</option>
                                <option value="failed" ${order.status === 'failed' ? 'selected' : ''}>Ошибка</option>
                            </select>
                            <button id="update-status-${order.id}" class="mt-1 w-full bg-blue-500 text-white py-1 rounded">Обновить статус</button>
                        ` : ''}
                    </div>
                `;
            }).join('') + '</div>'
        : '<p class="text-gray-500 mt-2">История заказов пуста</p>';

    // Админка — только для админа
    let adminSection = '';
    if (isAdmin) {
        adminSection = `
            <div class="mt-6 pt-4 border-t border-gray-200">
                <h3 class="font-bold text-lg text-blue-700">🛠️ Админ-панель</h3>
                <button id="open-admin-panel-btn" class="w-full mt-2 bg-blue-600 text-white py-2 rounded font-medium">
                    Открыть админ-панель
                </button>
            </div>
        `;
    }

    openModal(`
        <h2 class="text-xl font-bold mb-3">👤 Профиль</h2>
        <p class="text-gray-700">Имя: <strong>${escapeHtml(name)}</strong></p>
        <p class="mt-3 mb-1">Адрес доставки:</p>
        <input id="profile-addr" class="w-full p-3 border rounded mb-3" value="${escapeHtml(savedAddr)}" placeholder="Адрес не задан">
        <h3 class="font-semibold mt-4 mb-2">История заказов</h3>
        ${ordersHtml}
        ${adminSection}
        <div class="mt-4">
            <button id="save-profile" class="w-full bg-orange-500 text-white py-3 rounded font-medium">Сохранить</button>
        </div>
    `);

    setTimeout(() => {
        const saveBtn = $('save-profile');
        if (saveBtn) addClickHandler(saveBtn, () => {
            const addr = $('profile-addr')?.value.trim() || '';
            localStorage.setItem('delivery_addr', addr);
            showToast('Адрес обновлён');
            closeModal();
        });

        // Кнопка админки — только если админ
        if (isAdmin) {
            const openAdminBtn = $('open-admin-panel-btn');
            if (openAdminBtn) {
                addClickHandler(openAdminBtn, () => {
                    const uidParam = user?.id ? `?uid=${user.id}` : '';
                    const adminUrl = location.origin + '/web_app/admin.html' + uidParam;
                    if (tg?.openLink) {
                        tg.openLink(adminUrl);
                    } else {
                        window.open(adminUrl, '_blank');
                    }
                });
            }

            // Обработчики обновления статуса для каждого заказа
            orders.forEach(order => {
                const select = $(`status-select-${order.id}`);
                const updateBtn = $(`update-status-${order.id}`);
                if (select && updateBtn) {
                    addClickHandler(updateBtn, () => {
                        const newStatus = select.value;
                        updateOrderStatus(order.id, newStatus);
                    });
                }
            });
        }
    }, 0);
}

// --- Выбор типа заказа ---
function openOrderTypeSelector() {
    openModal(`
        <h2 class="text-xl font-bold mb-4 text-center">Выберите способ получения</h2>
        <div class="space-y-3">
            <button id="btn-delivery" class="w-full py-4 bg-green-100 text-green-800 rounded-lg font-medium flex items-center justify-center gap-2">
                🚚 Доставка
            </button>
            <button id="btn-restaurant" class="w-full py-4 bg-orange-100 text-orange-800 rounded-lg font-medium flex items-center justify-center gap-2">
                🍽 Самовывоз
            </button>
        </div>
    `);

    setTimeout(() => {
        addClickHandler($('btn-delivery'), () => {
            orderType = 'delivery';
            localStorage.setItem('orderType', orderType);
            $('orderType').textContent = '🚚 Доставка';
            showToast('Выбрана доставка');
            closeModal();
            openDelivery();
        });
        addClickHandler($('btn-restaurant'), () => {
            orderType = 'restaurant';
            localStorage.setItem('orderType', orderType);
            $('orderType').textContent = '🍽 Самовывоз';
            showToast('Выбран самовывоз');
            closeModal();
            openDelivery();
        });
    }, 0);
}

// --- DOM Ready ---
document.addEventListener('DOMContentLoaded', async () => {
    console.log('DOM ready — initializing UI');
    await fetchAdminConfig();

    if (user) {
        const nameEl = $('userName');
        if (nameEl) nameEl.textContent = user.first_name || user.username || 'Пользователь';
    }

    const orderTypeEl = $('orderType');
    if (orderTypeEl) {
        orderTypeEl.textContent = orderType === 'restaurant' ? '🍽 Самовывоз' : '🚚 Доставка';
    }

    // Обработчики кнопок
    addClickHandler($('cart-btn'), openCart);
    addClickHandler($('profile-btn'), openProfile);
    addClickHandler($('order-type-trigger'), openOrderTypeSelector);
    addClickHandler($('delivery-btn'), openDelivery);
    addClickHandler($('menu-btn'), () => updateNavigation('menu'));

    // Категории
    document.querySelectorAll('.category-btn').forEach(btn => {
        addClickHandler(btn, (e) => {
            document.querySelectorAll('.category-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            const cat = e.target.dataset.cat || '';
            loadDishes(cat);
        });
    });

    // Горизонтальный скролл категорий
    const catContainer = $('category-container');
    if (catContainer) {
        let isDown = false, startX, scrollLeft;
        catContainer.addEventListener('mousedown', (e) => {
            isDown = true;
            startX = e.pageX - catContainer.offsetLeft;
            scrollLeft = catContainer.scrollLeft;
        });
        ['mouseleave', 'mouseup'].forEach(evt =>
            catContainer.addEventListener(evt, () => isDown = false)
        );
        catContainer.addEventListener('mousemove', (e) => {
            if (!isDown) return;
            e.preventDefault();
            const x = e.pageX - catContainer.offsetLeft;
            const walk = (x - startX) * 2;
            catContainer.scrollLeft = scrollLeft - walk;
        });
    }

    // Загрузка данных
    updateNavigation('menu');
    loadDishes();
    updateCartCount();

    // Промо
    fetch(`${API_BASE}/promotions`)
        .then(r => r.json())
        .then(promos => {
            const list = $('promotion-list');
            if (list && Array.isArray(promos)) {
                list.innerHTML = promos.map(p => `
                    <div class="rounded-lg overflow-hidden bg-white flex items-center gap-3 p-3 min-w-[220px]">
                        <img src="${p.image_url || '/web_app/assets/promo_placeholder.png'}" class="w-14 h-14 object-cover rounded">
                        <div class="text-sm font-medium">${escapeHtml(p.text || '')}</div>
                    </div>
                `).join('');
            }
        })
        .catch(e => console.warn('Promotions load failed', e));
});

// Экспорт для отладки
window.openCart = openCart;
window.openProfile = openProfile;