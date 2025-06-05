window.addEventListener('message', (event) => {
    if (event.data === 'swipeNext') {
        let word_id = currentFrame.contentWindow.word_id
        fetch(`/can_swipe?word_id=${word_id}`, {
            method: 'GET'
        })
        .then((data) => data.json())
        .then((data) => {
            if (data.status === 'yes') {
                swipeNextFrame();
            }
            else {
                Telegram.WebApp.showPopup({
                    title: "Вы уверены?",
                    message: "Если перелистнуть, серия обнулится. Перелистываем?",
                    buttons: [
                    { id: "no", type: "default", text: "Нет" },
                    { id: "yes", type: "destructive", text: "Да" }
                    ]
                });
            }
        });
    }
    else if (event.data === 'swipeNextNoFetch') {
        swipeNextFrame(doFetch=false);
    }
    else if (event.data === 'swipePrev') {
        swipePrevFrame();
    }
});

Telegram.WebApp.onEvent('popupClosed', function(button) {
    if (button.button_id === "yes") {
        swipeNextFrame();
    }
});  

var currentFrame = document.querySelector('iframe.current');
var nextFrame = document.querySelector('iframe.next');

const parts = 10;
const fire = document.getElementById('fire');


function resizeHandler() {
    var iframes = document.querySelectorAll('iframe');
    for (iframe of iframes) {
        if (window.innerHeight > innerWidth) {
            document.body.className = 'fullscreen';
        } else {
            document.body.className = 'partscreen';
        }
    }
}
resizeHandler();
window.addEventListener('resize', resizeHandler);

addEventListener('keydown', (event) => {
    if (event.key === 's' || event.key === 'ArrowDown' || event.key === ' ') {
        swipeNextFrame();
    }
    if (event.key === 'w' || event.key === 'ArrowUp') {
        swipePrevFrame();
    }
});

let isScrolling = false;
document.addEventListener('wheel', (event) => {
    if (isScrolling) return;
    if (event.deltaY > 0) swipeNextFrame()
    else swipePrevFrame()

    isScrolling = true;
    setTimeout(() => {
        isScrolling = false; 
    }, 300);
});

function swipeNextFrame(doFetch=true) {
    let prev = document.querySelector('.prev')
    if (prev !== null) prev.remove();

    nextFrame.classList.remove('next');
    currentFrame.classList.replace('current', 'prev');

    setTimeout(() => {
        nextFrame.className = 'current';
        currentFrame = nextFrame;
        nextFrame = document.createElement('iframe');
        nextFrame.src = currentFrame.src;
        nextFrame.className = 'next';
        document.body.appendChild(nextFrame);
        resizeHandler();
    }, 300);

    if (doFetch) {
        // Уязвимость: Обработка потери свайпа частично на стороне клиента
        let word_id = currentFrame.contentWindow.word_id;
        
        fetch('/action/swipe_next', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({word_id: word_id})
        })
        .then((data) => data.json())
        .then((data) => {
            strike({n: data.strike})
        });
    }
}

function swipePrevFrame() {
    let prev = document.querySelector('.prev');
    if (!prev) return;

    nextFrame.remove();
    nextFrame = currentFrame;
    nextFrame.classList.replace('current', 'next');

    prev.classList.remove('prev');
    prev.className = 'current';
    currentFrame = prev;
}

function strike(strikeData) {
    // Вовращает - был ли переход на новый уровень страйка

    let p = document.querySelector('.strike-block p');

    if (!p) {
        return;
    }

    let n = strikeData.n;
    let strikeLevel = strikeData.levels;
    let nextLevel = false;
    p.innerText = n;

    if (n === 0 && fire.children.length > 0) {
        // Перезагрузка следующего фрейма при смене огонька, чтобы применился фон
        nextFrame.contentWindow.location.reload();
        fire.style.opacity = 0;
        setTimeout(() => {
            while (fire.firstChild) {
                fire.removeChild(fire.firstChild);
            }
            fire.style.opacity = 1;
        }, 700);
        return false;
    }

    for (let i = 0; i < strikeLevel.length; i++) {
        if (n < strikeLevel[i]) {
            // Перезагрузка следующего фрейма при смене огонька, чтобы применился фон
            if (i > 0 && n - 1 < strikeLevel[i - 1]) {
                nextFrame.contentWindow.location.reload();
                nextLevel = true;
            }

            document.documentElement.style.setProperty('--particle-color', `var(--fire-${i})`);
            document.documentElement.style.setProperty('--strike-background-color', `transparent`);
            
            if (fire.children.length === 0) {
                for (let i = 0; i < parts; i++) {
                    const p = document.createElement('div');
                    p.className = 'particle';
                    p.style.left = `calc(${(fire.getBoundingClientRect().width) / 2}px * (${i / parts}))`;
                    p.style.animationDelay = `${Math.random()}s`;
                    fire.appendChild(p);
                }
            }

            return nextLevel;
        }
    }
}