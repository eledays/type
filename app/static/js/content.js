let word = {};

let wordElement = document.querySelector('.word');
let answersElement = document.querySelector('.answers');
let loadingElement = document.querySelector('.loading');

let menuElement = document.querySelector('.menu');
let touchArea = document.querySelector('.touch-area');

let canvas = document.querySelector('canvas');
canvas.width = window.innerWidth;
canvas.height = window.innerHeight;
let ctx = canvas.getContext('2d');

let longPressTimer = null;
let longPressTime = 500;

loadingElement.style.display = 'none';

addEventListener('DOMContentLoaded', () => {
    for (let i = 0; i < answersElement.querySelectorAll('button').length; i++) {
        let answer = answersElement.querySelectorAll('button')[i];
        answer.addEventListener('click', (event) => handleAnswerClick(event, i));
    }
});

touchArea.addEventListener('touchstart', (event) => {
    try {event.preventDefault()} catch {}

    if (longPressTimer !== null) clearInterval(longPressTimer);
    
    longPressTimer = setTimeout(() => {
        openMenu();
    }, longPressTime);
}, {passive: false});

touchArea.addEventListener('touchend', (event) => {
    clearTimeout(longPressTimer);
});

function handleAnswerClick(event) {
    console.log(event);
    
    fetch('/check_word', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({id: word_id, answer: event.srcElement.innerText.trim()})
    })
    .then(response => response.json())
    .then(data => {
        word.full_word = data.full_word;
        if (data.correct) correctAnswer(data);
        else incorrectAnswer(data);
    });

    answersElement.querySelectorAll('.answer').forEach((e) => {
        e.disabled = true;
    });
}

function correctAnswer(data) {
    window.parent.strike(data.strike);
    // document.body.className = 'correct';
    let r = 0;
    let alpha_delta = 0;
    let rect = wordElement.getBoundingClientRect();

    function anim() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        ctx.strokeStyle = `rgba(0, 255, 0, ${0.6 - alpha_delta})`;
        ctx.fillStyle = `rgba(0, 255, 0, ${0.4 - alpha_delta})`;

        ctx.beginPath();
        ctx.arc(rect.x + rect.width / 2, rect.y + rect.height / 2, r, 0, 2 * Math.PI);
        ctx.lineWidth = 15;
        ctx.stroke();
        ctx.fill();
        r += 15;
        alpha_delta += .008;
        
        if (alpha_delta < 1) {
            requestAnimationFrame(anim);
        }
    }
    anim();
    wordElement.classList.add('shrink');
    setTimeout(() => {
        wordElement.innerHTML = word.full_word;
    }, 200);
    setTimeout(() => {
        document.body.classList.remove('correct');
        parent.postMessage('swipeNext', '*');
    }, 700);
}

function incorrectAnswer(data) {
    window.parent.strike(data.strike);
    document.body.className = 'incorrect';
    wordElement.classList.add('shrink');
    setTimeout(() => {
        wordElement.innerHTML = word.full_word;
    }, 200);
    setTimeout(() => {
        document.body.classList.remove('incorrect');
        parent.postMessage('swipeNext', '*');
    }, 1500);
}

let menuOpened = false;
function openMenu() {
    menuOpened = true;

    let overlay = document.createElement('div');
    overlay.className = 'menu-overlay';
    document.body.appendChild(overlay);

    menuElement.style.display = 'block';
    menuElement.style.opacity = 1;

    wordElement.style.top = '10vh';

    overlay.addEventListener('click', closeMenu);
    overlay.addEventListener('touchstart', closeMenu);
}

function closeMenu() {
    menuOpened = false;
    
    let overlay = document.querySelector('.menu-overlay');
    overlay.remove();
    menuElement.style.display = 'none';

    wordElement.style.top = '50%';
    setTimeout(() => clearTimeout(longPressTimer), 10);
}

function sendReport() {
    let button = document.querySelector('.menu button#mistake');
    button.querySelector('p').innerText = 'Отправка...';

    fetch('/mistake_report', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({id: word.id})
    })
    .then(() => {
        button.querySelector('p').innerText = 'Запрос отправлен';
        button.querySelector('span').innerHTML = 'check';
        button.querySelector('p').style.color = 'green';
        button.querySelector('span').style.color = 'green';
    });
}

function switchMenu() {
    if (menuOpened) closeMenu();
    else openMenu();
}