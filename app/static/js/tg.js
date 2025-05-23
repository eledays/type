let p = document.createElement('p')
p.innerText = 'loading' + window.Telegram;
p.style.zIndex = 10000;
p.style.position = 'absolute';
document.body.appendChild(p);

if (window.Telegram) {
    const tg = window.Telegram.WebApp;
    const user = tg.initDataUnsafe.user;

    console.log(user.id); // Telegram ID
    console.log(user.first_name); // Имя

    if (tg.initData) {
        p.innerText = 'tg loading';
        fetch('/verify_hash', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ initData: tg.initData }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.valid) {
                p.innerText = 'success';
            } else {
                p.innerText = 'fail';
            }
        })
        .catch(err => {
            p.innerText = ('Error verifying hash on server:', err);
        });
    }
}

