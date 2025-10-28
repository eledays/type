interface BatchResponse {
    clips: ClipData[];
}

interface ClipData {
    id: number;
    content: string;
}

export default class ClipsManager {
    private clips: ClipData[] = [];
    private currentIndex: number = 0;
    private isLoading: boolean = false;

    async loadClips(count: number): Promise<void> {
        if (this.isLoading) return;
        this.isLoading = true;

        try {
            const params = new URLSearchParams({
                count: count.toString()
            });

            const response = await fetch(`/api/clips/batch?${params.toString()}`);
            const data: BatchResponse = await response.json();

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

    async cleanupClips(oldClipsCount: number = 1): Promise<void> {
        this.clips.splice(0, this.currentIndex - oldClipsCount);
        this.currentIndex = Math.max(this.currentIndex - oldClipsCount, 0);
        console.info(`Cleaned up clips. Remaining clips: ${this.clips.length}`);
    }

    renderClips(container: HTMLElement): void {
        let previousClip = null;
        let currentClip = null;
        let nextClip = null;

        container.innerHTML = '';

        if (this.currentIndex > 0) {
            previousClip = document.createElement('div');
            previousClip.innerHTML = this.clips[this.currentIndex - 1].content;
            previousClip.id = 'previous-clip';
            previousClip.className = 'word-container';
            container.appendChild(previousClip);
        }

        if (this.currentIndex < this.clips.length) {
            currentClip = document.createElement('div');
            currentClip.innerHTML = this.clips[this.currentIndex].content;
            currentClip.id = 'current-clip';
            currentClip.className = 'word-container';
            container.appendChild(currentClip);
        }

        if (this.currentIndex + 1 < this.clips.length) {
            nextClip = document.createElement('div');
            nextClip.innerHTML = this.clips[this.currentIndex + 1].content;
            nextClip.id = 'next-clip';
            nextClip.className = 'word-container';
            container.appendChild(nextClip);
        }
    }
}