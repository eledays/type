import ClipsManager from './clipsManager.js';
import { showLoading, hideLoading } from './effect/loading.js';

export default class App {
    private clipsManager: ClipsManager | null;

    constructor() {
        this.clipsManager = null;
    }

    async init() {
        this.clipsManager = new ClipsManager();
        await this.clipsManager.loadClips(3);
        this.clipsManager.renderClips(document.getElementById('clips-container')!);
        hideLoading();
    }
}

window.addEventListener('DOMContentLoaded', async () => {
    window.app = new App();
    await window.app.init();
});