if (window.Telegram) {
    const tg = window.Telegram.WebApp;
    const user = tg.initDataUnsafe.user;

    console.log(user.id); // Telegram ID
    console.log(user.first_name); // Имя
}

let p = document.createElement('p')
p.innerText = 'loading';
document.body.appendChild(p);

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
            p.innerText = 'success';
        } else {
            p.innerText = 'fail';
        }
    })
    .catch(err => {
        console.error('Error verifying hash on server:', err);
    });
}

