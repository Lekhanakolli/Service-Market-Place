// ServeHub – Main JS

function toggleMenu() {
    const links = document.querySelector('.nav-links');
    if (links) {
        links.style.display = links.style.display === 'flex' ? 'none' : 'flex';
        links.style.flexDirection = 'column';
        links.style.position = 'absolute';
        links.style.top = '66px';
        links.style.left = '0';
        links.style.right = '0';
        links.style.background = '#16161a';
        links.style.padding = '16px 24px';
        links.style.borderBottom = '1px solid #2e2e3a';
        links.style.zIndex = '99';
    }
}

// Auto-dismiss flash messages after 4 seconds
document.addEventListener('DOMContentLoaded', () => {
    const flashes = document.querySelectorAll('.flash');
    flashes.forEach(f => {
        setTimeout(() => {
            f.style.opacity = '0';
            f.style.transition = 'opacity 0.4s';
            setTimeout(() => f.remove(), 400);
        }, 4000);
    });
});
