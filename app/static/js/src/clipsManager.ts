import { CONFIG } from './config.js';

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

    private renderTimeout: number | null = null;

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
            console.log('Clips data:', this.clips, this.currentIndex);
        }
        catch (error) {
            console.error('Error loading clips:', error);
        }
        finally {
            this.isLoading = false;
            this.cleanupClips();
        }
    }

    private getTransitionDuration(): number {
        const rootStyle = getComputedStyle(document.documentElement);
        const duration = rootStyle.getPropertyValue('--clip-transition-duration');
        return parseInt(duration); // Возвращает 300 (в миллисекундах)
    }

    async cleanupClips(oldClipsCount: number = CONFIG.oldClipsCount): Promise<void> {
        const clipsToRemove = Math.max(this.currentIndex - oldClipsCount, 0);
        
        if (clipsToRemove > 0) {
            this.clips.splice(0, clipsToRemove);
            this.currentIndex -= clipsToRemove;
        }
        
        console.info(`Cleaned up ${clipsToRemove} clips. Current index: ${this.currentIndex}, Remaining clips: ${this.clips.length}`);
    }

    renderClips(container: HTMLElement): void {
        let previousClip = null;
        let currentClip = null;
        let nextClip = null;

        container.innerHTML = '';

        console.log('Rendering clips at index:', this.currentIndex);

        if (this.currentIndex > 0) {
            previousClip = document.createElement('div');
            previousClip.innerHTML = this.clips[this.currentIndex - 1].content;
            previousClip.id = 'previous-clip';
            previousClip.className = 'clip-container';
            container.appendChild(previousClip);
        }

        if (this.currentIndex < this.clips.length) {
            currentClip = document.createElement('div');
            currentClip.innerHTML = this.clips[this.currentIndex].content;
            currentClip.id = 'current-clip';
            currentClip.className = 'clip-container';
            container.appendChild(currentClip);
        }

        if (this.currentIndex + 1 < this.clips.length) {
            nextClip = document.createElement('div');
            nextClip.innerHTML = this.clips[this.currentIndex + 1].content;
            nextClip.id = 'next-clip';
            nextClip.className = 'clip-container';
            container.appendChild(nextClip);
        }
    }

    async updateCLips(): Promise<void> {
        let log = `${this.clips.length}`;
        this.cleanupClips();
        log += ` -> ${this.clips.length}`;
        if (this.clips.length - this.currentIndex < CONFIG.loadingTriggerOffset) {
            await this.loadClips(CONFIG.clipsOnPage - this.clips.length);
        }
        this.renderClips(document.getElementById('clips-container')!);
        log += ` -> ${this.clips.length}`;
        console.log(log);
        console.log(this.clips.length - this.currentIndex);
    }   

    goToNextClip(): void {
        const currentClip = document.getElementById('current-clip');
        const nextClip = document.getElementById('next-clip');
        const previousClip = document.getElementById('previous-clip');

        if (this.currentIndex + 1 < this.clips.length) {
            this.currentIndex++;
            console.log(this.currentIndex)
            
            if (previousClip) {
                previousClip.remove();
            }
            if (currentClip) {
                currentClip.id = 'previous-clip';
            }
            if (nextClip) {
                nextClip.id = 'current-clip';
            }
        } else {
            console.warn('No next clip available.');
        }

        if (this.renderTimeout) clearTimeout(this.renderTimeout);
        this.renderTimeout = setTimeout(() => {
            this.updateCLips();
        }, this.getTransitionDuration());
    }

    goToPreviousClip(): void {
        const currentClip = document.getElementById('current-clip');
        const nextClip = document.getElementById('next-clip');
        const previousClip = document.getElementById('previous-clip');

        if (!previousClip) {
            console.warn('No previous clip available.');
            return;
        };
        if (this.currentIndex <= 0) {
            console.warn('Already at the first clip.');
            return;
        };
        
        this.currentIndex--;
        if (nextClip) {
            nextClip.remove();
        }
        if (currentClip) {
            currentClip.id = 'next-clip';
        }
        if (previousClip) {
            previousClip.id = 'current-clip';
        }   

        if (this.renderTimeout) clearTimeout(this.renderTimeout);
        this.renderTimeout = setTimeout(() => {
            this.updateCLips();
        }, this.getTransitionDuration());   
    }
}