if (window.Telegram) {
    const tg = window.Telegram.WebApp;
    const user = tg.initDataUnsafe.user;

    console.log(user.id); // Telegram ID
    console.log(user.first_name); // Имя
}

if (tg.initData) {
    fetch('/verify-hash', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ initData: tg.initData }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.valid) {
            console.log('Hash is valid');
        } else {
            console.log('Hash is invalid');
        }
    })
    .catch(err => {
        console.error('Error verifying hash on server:', err);
    });
}

