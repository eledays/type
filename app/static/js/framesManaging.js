window.addEventListener('message', (event) => {
    if (event.data === 'swipeNext') {
        swipeNextFrame();
    }
    else if (event.data === 'swipePrev') {
        swipePrevFrame();
    }
});

var currentFrame = document.querySelector('iframe.current');
var nextFrame = document.querySelector('iframe.next');

const parts = 50;
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

function swipeNextFrame() {
    let prev = document.querySelector('.prev')
    if (prev !== null) prev.remove();

    nextFrame.classList.remove('next');
    currentFrame.classList.replace('current', 'prev');

    setTimeout(() => {
        nextFrame.className = 'current';
        currentFrame = nextFrame;
        nextFrame = document.createElement('iframe');
        nextFrame.src = "/get_frame";
        nextFrame.className = 'next';
        document.body.appendChild(nextFrame);
        resizeHandler();
    }, 300);

    let word_id = currentFrame.contentWindow.word.id;
    fetch('/action/swipe_next', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({word_id: word_id})
    });
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

const strikeLevel = {
    5: 4,
    4: 3,
    3: 2,
    2: 1,
}

function strike(n) {
    let p = document.querySelector('.strike-block p');
    p.innerText = n;

    console.log(n, strikeLevel[-1]);
    

    if (n === 0 && fire.children.length > 0) {
        fire.style.opacity = 0;
        document.documentElement.style.setProperty('--strike-background-color', `var(--secondary-color)`);
        setTimeout(() => {
            while (fire.firstChild) {
                fire.removeChild(fire.firstChild);
            }
            fire.style.opacity = 1;
        }, 700);
        return;
    }

    for (let level in strikeLevel) {
        if (n >= level) {
            document.documentElement.style.setProperty('--particle-color', `var(--fire-${strikeLevel[level]})`);
            document.documentElement.style.setProperty('--strike-background-color', `transparent`);
            
            if (fire.children.length === 0) {
                for (let i = 0; i < parts; i++) {
                    const p = document.createElement('div');
                    p.className = 'particle';
                    p.style.left = `calc((100% - 60px) * ${i / parts})`;
                    p.style.animationDelay = `${Math.random()}s`;
                    fire.appendChild(p);
                }
            }
        }
    }
}