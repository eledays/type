if (window.Telegram && window.Telegram.WebApp.initData) {
    const tg = window.Telegram.WebApp;
    const user = tg.initDataUnsafe.user;

    window.addEventListener('DOMContentLoaded', () => {
        tg.ready();
        tg.expand();
        tg.requestFullscreen();
        tg.lockOrientation();
    });

    if (tg.initData) {
        fetch('/verify_hash', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ initData: tg.initData, user: user }),
        })
        .then(response => response.json())
        .then(data => {
            window.location.href = '/';
        })
        .catch(err => {
            // p.innerText = ('Error verifying hash on server:', err);
        });
    }
}
else {
    window.location.href = '/demo';
}