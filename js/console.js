// Redirect to the main console implementation
console.warn('Deprecated: Using consolidated console.js from static/js/');
if (typeof window !== 'undefined') {
    window.location.href = '/static/js/console.js';
}