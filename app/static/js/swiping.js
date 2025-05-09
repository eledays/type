let touchStartY = 0;
let touchEndY = 0;

addEventListener('touchstart', (event) => {
    touchStartY = event.touches[0].clientY;
}, {passive: false});

addEventListener('touchend', (event) => {
    touchEndY = event.changedTouches[0].clientY;
    handleSwipe();
});

function handleSwipe() {
    if (touchStartY - touchEndY > 50) {
        parent.postMessage('swipeNext', '*');
    }
    else if (touchStartY - touchEndY < 50) {
        parent.postMessage('swipePrev', '*');
    }
}

let isScrolling = false;
document.addEventListener('wheel', (event) => {
    if (isScrolling) return;
    if (event.deltaY > 0) {
        parent.postMessage('swipeNext', '*');
    }
    else {
        parent.postMessage('swipePrev', '*');
    }

    isScrolling = true;
    setTimeout(() => {
        isScrolling = false; 
    }, 300);
});