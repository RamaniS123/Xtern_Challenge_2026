const CACHE_NAME = 'pmadapt-cache-v1';
const ASSETS = [
    '/',
    '/index.html',
    '/dashboard.html',
    '/styles.css',
    '/app.js',
    '/dashboard.js',
    '/bootstrap.bundle.min.js',
    '/logo.svg',
    // We can also let the caching strategy cache other dynamic assets like fonts dynamically
];

// Install Event
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            console.log('[Service Worker] Caching Application Shell');
            return cache.addAll(ASSETS.map(url => new Request(url, { cache: 'reload' })));
        })
    );
    // Force active
    self.skipWaiting();
});

// Activate Event
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cache => {
                    if (cache !== CACHE_NAME) {
                        console.log('[Service Worker] Clearing Old Cache');
                        return caches.delete(cache);
                    }
                })
            );
        })
    );
    // Claim clients
    self.clients.claim();
});

// Fetch Event (Network First, fallback to Cache)
self.addEventListener('fetch', event => {
    // Only intercept local frontend static files, bypass API requests
    if (event.request.url.includes(':8000') || event.request.method !== 'GET') {
        return;
    }

    event.respondWith(
        fetch(event.request)
            .then(res => {
                // Return valid response and cache it
                const resClone = res.clone();
                caches.open(CACHE_NAME).then(cache => {
                    cache.put(event.request, resClone);
                });
                return res;
            })
            .catch(() => {
                // If network fails, try cache
                return caches.match(event.request).then(res => {
                    return res || caches.match('/index.html');
                });
            })
    );
});