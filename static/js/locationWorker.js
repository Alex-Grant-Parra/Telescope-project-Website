// locationWorker.js
// Dedicated worker to provide IP-based geolocation fallback and simple helpers.
// Note: Web Workers cannot reliably access navigator.geolocation in browsers,
// so this worker performs an IP lookup as a fallback when the main thread
// cannot obtain high-accuracy geolocation.

self.addEventListener('message', async (ev) => {
    const { cmd } = ev.data || {};
    if (!cmd) return;

    // Perform an IP-based lookup and post result
    async function doIpLocate() {
        try {
            const resp = await fetch('https://ipwho.is/');
            if (!resp.ok) {
                self.postMessage({ type: 'error', message: 'IP geolocation fetch failed: ' + resp.status });
                return;
            }
            const data = await resp.json();
            if (data && (data.latitude !== undefined) && (data.longitude !== undefined)) {
                self.postMessage({ type: 'location', source: 'ip', latitude: Number(data.latitude), longitude: Number(data.longitude), raw: data });
            } else {
                self.postMessage({ type: 'error', message: 'IP geolocation returned no coordinates' });
            }
        } catch (err) {
            self.postMessage({ type: 'error', message: String(err) });
        }
    }

    // Higher-level locate flow: ask main thread to request browser geolocation,
    // fallback to IP lookup if main doesn't respond or reports failure.
    if (cmd === 'locate') {
        // Notify main thread to attempt browser geolocation
        self.postMessage({ type: 'needBrowserGeo' });

        // Wait for a browser result to be posted back to the worker (cmd 'browserGeoResult')
        // Use a Promise with timeout to fallback to IP lookup.
        const result = await new Promise((resolve) => {
            let settled = false;
            const onMessage = (ev2) => {
                const d = ev2.data || {};
                if (d && d.cmd === 'browserGeoResult') {
                    if (!settled) {
                        settled = true;
                        self.removeEventListener('message', onMessage);
                        resolve(d);
                    }
                }
            };
            self.addEventListener('message', onMessage);

            // timeout fallback
            setTimeout(() => {
                if (!settled) {
                    settled = true;
                    self.removeEventListener('message', onMessage);
                    resolve({ success: false, error: 'timeout' });
                }
            }, 7000);
        });

        if (result && result.success) {
            self.postMessage({ type: 'location', source: 'browser', latitude: Number(result.latitude), longitude: Number(result.longitude), accuracy: result.accuracy || null });
            return;
        }

        // Browser geolocation unavailable or failed — perform IP fallback
        await doIpLocate();
        return;
    }

    if (cmd === 'ipLocate') {
        await doIpLocate();
        return;
    }

    // Support receiving browserGeoResult directly (alternate flow)
    if (cmd === 'browserGeoResult') {
        // echo back as location for consumers
        if (ev.data && ev.data.success) {
            const lat = Number(ev.data.latitude);
            const lon = Number(ev.data.longitude);
            self.postMessage({ type: 'location', source: 'browser', latitude: lat, longitude: lon, accuracy: ev.data.accuracy || null });
        } else {
            self.postMessage({ type: 'error', message: ev.data && ev.data.error ? ev.data.error : 'browser geolocation failed' });
        }
        return;
    }

    // Future commands could include reverse geocoding or other helpers.
});

// Worker ready
self.postMessage({ type: 'ready' });
