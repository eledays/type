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
