import ClipsManager from './clipsManager.js';
import SwipeHandler from './events/swipeHandler.js';
import WindowResizeHandler from './events/windowResizeHandler.js';
import { showLoading, hideLoading } from './effect/loading.js';
import { CONFIG } from './config.js';

export default class App {
    private clipsManager: ClipsManager;
    private swipeHandler: SwipeHandler;
    private windowResizeHandler: WindowResizeHandler;

    constructor() {
        this.clipsManager = new ClipsManager();
        this.swipeHandler = new SwipeHandler(
            () => this.clipsManager?.goToNextClip(),
            () => this.clipsManager?.goToPreviousClip()
        );
        this.windowResizeHandler = new WindowResizeHandler();
    }

    async init() {
        await this.clipsManager.loadClips(CONFIG.clipsOnPage);
        this.clipsManager.renderClips(document.getElementById('clips-container')!);
        hideLoading();
    }
}

window.addEventListener('DOMContentLoaded', async () => {
    window.app = new App();
    await window.app.init();
});