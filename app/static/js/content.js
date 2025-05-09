var word = null;

var wordElement = document.querySelector('.word');
var answersElement = document.querySelector('.answers');
var loadingElement = document.querySelector('.loading');

var menuElement = document.querySelector('.menu');
var touchArea = document.querySelector('.touch-area');

let longPressTimer = null;
let longPressTime = 500;

addEventListener('DOMContentLoaded', () => {
    fetch('/get_word')
    .then(response => response.json())
    .then(data => {
        word = data;
        loadingElement.style.opacity = 0;
        setTimeout(() => {
            loadingElement.style.display = 'none';
        }, 300);
        wordElement.innerHTML = word.html_word;

        answersElement.innerHTML = '';
        for (let i = 0; i < word.answers.length; i++) {
            let answer = document.createElement('button');
            answer.className = 'answer';
            answer.innerHTML = word.answers[i];
            answersElement.appendChild(answer);

            answer.addEventListener('click', (event) => handleAnswerClick(event, i));
        }
    });
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

function handleAnswerClick(event, i) {
    fetch('/check_word', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({id: word.id, answer: word.answers[i]})
    })
    .then(response => response.json())
    .then(data => {
        if (data.correct) {
            document.body.className = 'correct';
            wordElement.classList.add('shrink');
            setTimeout(() => {
                wordElement.innerHTML = data.full_word;
            }, 200);
            setTimeout(() => {
                document.body.classList.remove('correct');
                parent.postMessage('swipe', '*');
            }, 700);
        } else {
            alert('Incorrect!');
        }
    });
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