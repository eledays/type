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