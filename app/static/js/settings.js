let strikeItem = document.getElementById('strike');
let notificationItem = document.getElementById('notifications');
let notificationInput = document.getElementById('notification-time');

// notificationInput.value = '{{ settings.notification_time.strftime("%H:%M") }}';

function handleClick(id) {
    let item = document.querySelector(`.setting-item#${id}`);
    let child = document.querySelector(`.time-control#${id}`);
    let valueElement = item.querySelector('.setting-value');
    let value = !(valueElement.classList.contains('on'));

    console.log(child);
    

    fetch(window.routeConfig.updateSettings, {
        method: 'PATCH',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': window.routeConfig.csrfToken,
        },
        body: JSON.stringify({[id]: value})
    })
    .then((data) => {
        if (data.status === 200 && value) {
            valueElement.innerText = 'В' + valueElement.innerText.slice(2);
            valueElement.classList.replace('off', 'on');
            if (child) child.style.marginTop = '-4px';
        }
        else if (data.status === 200 && !value) {
            valueElement.innerText = 'Вы' + valueElement.innerText.slice(1);
            valueElement.classList.replace('on', 'off');
            if (child) child.style.marginTop = '-52px';
        }
    });
}

function handleTimeInput(id) {
    let item = document.querySelector(`[data-setting-time="${id}"]`);
    fetch(window.routeConfig.updateSettings, {
        method: 'PATCH',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': window.routeConfig.csrfToken,
        },
        body: JSON.stringify({[id + '_time']: item.value})
    });
}

addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-setting-toggle]').forEach((item) => {
        item.addEventListener('click', () => handleClick(item.dataset.settingToggle));
    });
    document.querySelectorAll('[data-setting-time]').forEach((input) => {
        input.addEventListener('change', () => handleTimeInput(input.dataset.settingTime));
    });
    const reportForm = document.getElementById('general-report-form');
    reportForm?.addEventListener('submit', async (event) => {
        event.preventDefault();
        const message = document.getElementById('general-report-message');
        const feedback = document.getElementById('general-report-feedback');
        const submit = reportForm.querySelector('[type="submit"]');
        submit.disabled = true;
        feedback.textContent = 'Отправляем…';
        try {
            const response = await fetch(window.routeConfig.createReport, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.routeConfig.csrfToken,
                },
                body: JSON.stringify({message: message.value, practice_item_id: null}),
            });
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.message);
            reportForm.reset();
            feedback.textContent = 'Спасибо, сообщение отправлено';
        } catch (error) {
            feedback.textContent = error.message || 'Не удалось отправить сообщение';
        } finally {
            submit.disabled = false;
        }
    });
});
