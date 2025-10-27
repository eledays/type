import ClipsManager from './clipsManager.js';

export default class App {
    private clipsManager: ClipsManager | null;

    constructor() {
        this.clipsManager = null;
    }

    async init() {
        this.clipsManager = new ClipsManager();
        await this.clipsManager.loadClips(3);
    }
}

window.addEventListener('DOMContentLoaded', async () => {
    window.app = new App();
    await window.app.init();
});