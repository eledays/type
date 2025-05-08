const theme = localStorage.getItem('theme') || 'light';

const themeLink = document.createElement('link');
themeLink.rel = 'stylesheet';
themeLink.href = `/static/css/themes/${theme}.css`; 

document.head.appendChild(themeLink);