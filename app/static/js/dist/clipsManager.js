export default class ClipsManager {
    constructor() {
        this.clips = [];
        this.currentIndex = 0;
        this.isLoading = false;
    }
    async loadClips(count) {
        if (this.isLoading)
            return;
        this.isLoading = true;
        try {
            const params = new URLSearchParams({
                count: count.toString()
            });
            const response = await fetch(`/api/clips/batch?${params.toString()}`);
            const data = await response.json();
            this.clips.push(...data.clips);
            console.info(`Loaded ${data.clips.length} clips. Total clips: ${this.clips.length}`);
        }
        catch (error) {
            console.error('Error loading clips:', error);
        }
        finally {
            this.isLoading = false;
            this.cleanupClips();
        }
    }
    async cleanupClips(oldClipsCount = 1) {
        this.clips.splice(0, oldClipsCount);
        this.currentIndex = Math.max(0, this.currentIndex - oldClipsCount);
        console.info(`Cleaned up ${oldClipsCount} old clips. Total clips: ${this.clips.length}`);
    }
    renderClips(container) {
        container.innerHTML = '';
        this.clips.forEach((clip, index) => {
            const clipElement = document.createElement('div');
            clipElement.className = 'clip';
            clipElement.textContent = clip.content;
            container.appendChild(clipElement);
        });
    }
}
//# sourceMappingURL=clipsManager.js.map