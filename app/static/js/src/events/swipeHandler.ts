export default class SwipeHandler {
    private touchStartY = 0;
    private touchEndY = 0;
    private isScrolling = false;

    constructor(
        private onSwipeNext: () => void,
        private onSwipePrevious: () => void
    ) {
        this.setupListeners();
        console.log('SwipeHandler initialized');
    }

    private setupListeners() {
        this.setupTouchListeners();
        this.setupWheelListener();
    }

    private setupTouchListeners() {
        document.addEventListener('touchstart', (event) => {
            this.touchStartY = event.touches[0].clientY;
        }, { passive: false });

        document.addEventListener('touchend', (event) => {
            this.touchEndY = event.changedTouches[0].clientY;
            this.handleSwipe();
        });
    }

    private handleSwipe() {
        if (this.touchStartY - this.touchEndY > 50) this.swipeNext();
        else if (this.touchStartY - this.touchEndY < -50) this.swipePrevious();
    }

    private setupWheelListener() {
        document.addEventListener('wheel', (event) => {
            if (this.isScrolling) return;

            if (event.deltaY > 0) this.swipeNext();
            else this.swipePrevious();

            this.isScrolling = true;
            setTimeout(() => {
                this.isScrolling = false;
            }, 300);
        });
    }

    private swipeNext() {
        this.onSwipeNext();
    }

    private swipePrevious() {
        this.onSwipePrevious();
    }
}