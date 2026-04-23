document.addEventListener('DOMContentLoaded', function () {
    // Like forms (unified handler)
    document.querySelectorAll('.like-form').forEach(form => {
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            const postId = form.dataset.id;
            const contentType = form.dataset.type;
            const csrfToken = form.querySelector('input[name="csrf_token"]').value;
            try {
                const response = await fetch(`/like/${contentType}/${postId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    }
                });
                const data = await response.json();
                const likeIcon = document.getElementById(`like-icon-${postId}`);
                if (likeIcon) {
                    likeIcon.src = data.liked ? '/static/like_filled.svg' : '/static/like.svg';
                }

                const rating = document.getElementById(`rating-${postId}`);
                if (rating) {
                    rating.textContent = data.rating;
                }

                console.log(data);
            } catch (error) {
                console.error('Error:', error);
            }
        });
    });

    // Popovers
    const popoverTriggerList = document.querySelectorAll('[data-bs-toggle="popover"]');

    // Sidebar
    const sidebar = document.getElementById('sidebar');
    const toggleBtn = document.getElementById('toggleSidebarBtn');

    if (sidebar && toggleBtn) {
        const savedState = localStorage.getItem('sidebarCollapsed');

        if (savedState === 'false') {
            sidebar.classList.remove('collapsed');
            sidebar.style.width = '260px';
            sidebar.style.padding = '20px';
            toggleBtn.style.left = '260px';
            toggleBtn.textContent = '☰';
        } else {
            sidebar.classList.add('collapsed');
            sidebar.style.width = '0';
            sidebar.style.padding = '0';
            toggleBtn.style.left = '0';
            toggleBtn.textContent = '☰';
        }

        toggleBtn.addEventListener('click', function () {
            if (sidebar.classList.contains('collapsed')) {
                sidebar.classList.remove('collapsed');
                sidebar.style.width = '260px';
                sidebar.style.padding = '20px';
                toggleBtn.style.left = '260px';
                toggleBtn.textContent = '☰';
                localStorage.setItem('sidebarCollapsed', 'false');
            } else {
                sidebar.classList.add('collapsed');
                sidebar.style.width = '0';
                sidebar.style.padding = '0';
                toggleBtn.style.left = '0';
                toggleBtn.textContent = '☰';
                localStorage.setItem('sidebarCollapsed', 'true');
            }
        });
    }

    // Dropdown - отмечаем уведомления как прочитанные
    const notificationDropdown = document.getElementById('notificationDropdown');

    if (notificationDropdown) {
        notificationDropdown.addEventListener('shown.bs.dropdown', async function () {
            try {
                const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;

                const response = await fetch('/mark_notice', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        ...(csrfToken && { 'X-CSRFToken': csrfToken })
                    }
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const data = await response.json();

                if (data.success) {
                    console.log('Уведомления отмечены как прочитанные');

                    // Ищем badge в родительском элементе
                    const badge = notificationDropdown.parentElement.querySelector('.badge');
                    if (badge) {
                        console.log("Бейдж найден");
                        badge.remove();
                        console.log("Бейдж удален");
                    } else {
                        console.log("Бейдж не найден");
                    }
                } else {
                    console.error('Ошибка:', data.message);
                }
            } catch (error) {
                console.error('Ошибка при отправке запроса:', error);
            }
        });
    }

    // Ripple effect функция
    function addRippleEffect(selector) {
        const elements = document.querySelectorAll(selector);

        elements.forEach(element => {
            element.addEventListener('click', function (e) {
                // Удаляем старый круг, если есть
                const oldRipple = element.querySelector('.ripple');
                if (oldRipple) oldRipple.remove();

                const circle = document.createElement('span');
                const diameter = Math.max(element.clientWidth, element.clientHeight);
                const radius = diameter / 2;

                // Расчет координат клика относительно элемента
                const rect = element.getBoundingClientRect();
                circle.style.width = circle.style.height = `${diameter}px`;
                circle.style.left = `${e.clientX - rect.left - radius}px`;
                circle.style.top = `${e.clientY - rect.top - radius}px`;
                circle.classList.add('ripple');

                element.appendChild(circle);

                // Удаляем элемент после анимации
                setTimeout(() => {
                    if (circle.parentNode) {
                        circle.remove();
                    }
                }, 600);
            });
        });
    }

    // Применяем эффект к разным типам элементов
    addRippleEffect('.btn-glass-outline');
    addRippleEffect('.btn-glass-primary');
    addRippleEffect('.btn-glass');
    addRippleEffect('.post');
    addRippleEffect('.discuss-custom');
    addRippleEffect('.link-custom');

    // Эффект нажатия для кнопок
    function addPressEffect(selector) {
        const elements = document.querySelectorAll(selector);

        elements.forEach(element => {
            element.addEventListener('mousedown', function () {
                this.style.transform = 'scale(0.99)';
            });

            element.addEventListener('mouseup', function () {
                this.style.transform = '';
            });

            element.addEventListener('mouseleave', function () {
                this.style.transform = '';
            });
        });
    }

    // Применяем эффект нажатия
    addPressEffect('.btn-glass');
    addPressEffect('.btn-glass-primary');
    addPressEffect('.btn-glass-outline');

    console.log('Ripple effect initialized');

    const passwordToggleBtn = document.getElementById('togglePassword');
    const img = document.getElementById('hide');
    const passwordInput = document.getElementById('password');

    if (passwordToggleBtn && img && passwordInput) {
        passwordToggleBtn.addEventListener('click', function () {
            const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordInput.setAttribute('type', type);
            img.src = type === 'password' ? '/static/view.svg' : '/static/hide.svg';
        });
    }

    // Валидация формы перед отправкой

    const form = document.querySelector('form[action="/send_email"]');
    if (form) {
        const verifyType = form.dataset.type;
        const modal = new bootstrap.Modal(document.getElementById('staticBackdrop'));

        if (modal) {
            console.log("Модальное окно найдено");
        };

        form.addEventListener('submit', function (e) {
            e.preventDefault();
            if (verifyType === 'register') {
                const username = document.getElementById('username').value.trim();
                const version = document.querySelector('input[name="version"]:checked');
                const email = document.getElementById('email').value.trim();
                const password = document.getElementById('password').value.trim();

                // Проверяем все поля
                if (!username || !email || !password || !version) {
                    e.preventDefault(); // Останавливаем отправку формы
                    alert('Пожалуйста, заполните все поля!');
                    return false;
                }

                // Проверяем минимальную длину username
                if (username.length < 4) {
                    e.preventDefault();
                    alert('Имя пользователя должно содержать минимум 4 символа!');
                    return false;
                }

                // Проверяем email
                const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                if (!emailRegex.test(email)) {
                    e.preventDefault();
                    alert('Введите корректный email!');
                    return false;
                }
            } else if (verifyType === 'login') {
                const email = document.getElementById('email').value.trim();
                const password = document.getElementById('password').value.trim();
            }
            
            const formData = new FormData(form);

            fetch(`/send_email/${verifyType}`, {
                method: 'POST',
                body: formData
            })

                .then(response => {
                    if (response.ok) {
                        modal.show();
                    } else {
                        alert('Произошла ошибка!');
                    }
                })
                .catch(error => {
                    alert('Произошла ошибка!');
                });
        });
    }
});