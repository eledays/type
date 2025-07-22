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
    let user_id = Math.round(Math.random() * 100000000000 + 100000000000);
    localStorage.setItem('user_id', user_id);
    fetch('/set_user_id', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ user_id: user_id }),
    })
    .then(data => {
        window.location.href = '/';
    });
}