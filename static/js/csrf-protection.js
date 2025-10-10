// Global CSRF Protection Script
// This script provides CSRF protection for any page, including those that don't extend base.html

(function() {
    'use strict';
    
    // Function to set up CSRF protection
    function setupCSRFProtection() {
        try {
            // Get CSRF token from meta tag (should be set by template)
            let csrfToken = '';
            const metaTag = document.querySelector('meta[name="csrf-token"]');
            if (metaTag) {
                csrfToken = metaTag.content;
            }
            
            // If no token found, we can't proceed
            if (!csrfToken) {
                console.warn('CSRF token not found. CSRF protection will not work.');
                return;
            }
            
            // Make CSRF token globally available
            window.CSRF_TOKEN = csrfToken;
            
            // Function to inject CSRF token into forms
            function injectTokenIntoForm(form) {
                if (!form) return;
                
                // Only inject into forms that are POSTing
                const method = (form.getAttribute('method') || '').toLowerCase();
                if (method !== 'post') return;
                
                // Check if input already exists
                if (form.querySelector('input[name="csrf_token"]')) return;
                
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'csrf_token';
                input.value = csrfToken;
                form.prepend(input);
            }
            
            // Inject into existing forms
            document.querySelectorAll('form').forEach(injectTokenIntoForm);
            
            // Observe for dynamically added forms
            const observer = new MutationObserver(function(mutations) {
                for (const mutation of mutations) {
                    for (const node of mutation.addedNodes) {
                        if (node.tagName === 'FORM') {
                            injectTokenIntoForm(node);
                        }
                        if (node.querySelectorAll) {
                            node.querySelectorAll('form').forEach(injectTokenIntoForm);
                        }
                    }
                }
            });
            
            observer.observe(document.documentElement || document.body, {
                childList: true,
                subtree: true
            });
            
            // Wrap fetch to include CSRF header for same-origin requests
            if (!window._originalFetch) {
                window._originalFetch = window.fetch;
                
                window.fetch = function(resource, init) {
                    try {
                        init = init || {};
                        init.headers = init.headers || {};
                        
                        // Determine request method
                        const method = ((init.method || 'GET') + '').toUpperCase();
                        const safeMethods = ['GET', 'HEAD', 'OPTIONS'];
                        
                        // Determine if this is a same-origin request
                        const url = (typeof resource === 'string') ? resource : (resource && resource.url) || '';
                        const isSameOrigin = url === '' || 
                                           url.startsWith(window.location.origin) || 
                                           url.startsWith('/') || 
                                           url.startsWith('./') || 
                                           url.startsWith('../');
                        
                        // Add CSRF token for same-origin non-safe methods
                        if (isSameOrigin && !safeMethods.includes(method)) {
                            // Only add if not already present
                            if (!init.headers['X-CSRFToken'] && !init.headers['x-csrftoken']) {
                                init.headers['X-CSRFToken'] = csrfToken;
                            }
                        }
                    } catch (e) {
                        console.warn('Error adding CSRF header:', e);
                    }
                    
                    return window._originalFetch.apply(this, arguments);
                };
            }
            
            console.log('CSRF protection initialized');
            
        } catch (e) {
            console.error('Failed to set up CSRF protection:', e);
        }
    }
    
    // Run setup when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupCSRFProtection);
    } else {
        setupCSRFProtection();
    }
    
    // Also expose the setup function globally for manual initialization
    window.setupCSRFProtection = setupCSRFProtection;
    
})();
