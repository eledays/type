export default class WindowResizeHandler {
    constructor() {
        this.setupListeners();
    }

    private setupListeners() {
        this.setupWindowResizeListner();
        this.handleResize();
    }

    private setupWindowResizeListner() {
        window.addEventListener('resize', () => {
            this.handleResize();
        });
    }

    private handleResize() {
        if (window.innerHeight > innerWidth) {
            document.body.className = 'fullscreen';
        } else {
            document.body.className = 'partscreen';
        }
    }
}