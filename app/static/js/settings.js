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
    

    fetch('/set_settings', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
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
    let item = document.querySelector(`.time-control#${id} #time-input`);
    fetch('/set_settings', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({[id + '_time']: item.value})
    });
}

function backToReferrer() {
    const referrer = new URLSearchParams(window.location.search).get('referrer');
    
    if (referrer) {
        window.location.href = referrer;
    } else {
        window.location.href = '/';
    }
}

addEventListener('DOMContentLoaded', () => {
    Telegram.WebApp.BackButton.show();
    Telegram.WebApp.BackButton.onClick(backToReferrer);
});