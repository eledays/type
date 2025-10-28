function showLoading() {
    const loadingElement = document.querySelector('.loading') as HTMLElement;
    if (loadingElement) {
        loadingElement.style.display = 'block';
        return;
    }

    const newLoadingElement = document.createElement('div');
    newLoadingElement.className = 'loading';
    document.body.appendChild(newLoadingElement);
}

function hideLoading() {
    const loadingElement = document.querySelector('.loading') as HTMLElement;
    if (loadingElement) {
        loadingElement.style.display = 'none';
    }
}

export { showLoading, hideLoading };