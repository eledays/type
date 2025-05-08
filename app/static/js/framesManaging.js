window.addEventListener('message', (event) => {
    if (event.data === 'swipe') {
        swipeNextFrame();
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
});

let isScrolling = false;
document.addEventListener('wheel', (event) => {
    if (isScrolling) return;
    if (event.deltaY > 0) {
        swipeNextFrame();
    }

    isScrolling = true;
    setTimeout(() => {
        isScrolling = false; 
    }, 300);
});

function swipeNextFrame() {
    nextFrame.classList.remove('next');
    currentFrame.classList.add('prev');

    setTimeout(() => {
        nextFrame.className = 'current';
        currentFrame.remove();
        currentFrame = nextFrame;
        nextFrame = document.createElement('iframe');
        nextFrame.src = "/get_frame";
        nextFrame.className = 'next';
        document.body.appendChild(nextFrame);
        resizeHandler();
    }, 300);
}