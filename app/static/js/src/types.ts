import App from './app.js';

declare global {
    interface Window {
        app: App;
    }
}

export {};