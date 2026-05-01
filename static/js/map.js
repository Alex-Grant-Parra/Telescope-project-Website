(function () {
    const mapElement = document.getElementById("world-map");
    if (!mapElement || typeof L === "undefined") {
        return;
    }

    const config = window.MAP_CONFIG || {};
    const statusEl = document.getElementById("map-status");
    const weatherOpacityInput = document.getElementById("weather-opacity");
    const bortleOpacityInput = document.getElementById("bortle-opacity");
    const layerInputs = Array.from(document.querySelectorAll("[data-layer]"));

    const openMeteoTileUrl = (config.openMeteoTileUrl || "").trim();
    const openMeteoAttribution = (config.openMeteoAttribution || "").trim() ||
        "Weather data &copy; Open-Meteo.com";
    const openMeteoBaseUrl = openMeteoTileUrl ||
        "https://map-tiles.open-meteo.com/data_spatial/dwd_icon/latest.json?time_step=current_time_1H";
    const bortleUrl = (config.bortleTileUrl || "").trim();
    const satelliteUrl = (config.satelliteTileUrl || "").trim() ||
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
    const satelliteAttribution = (config.satelliteAttribution || "").trim() ||
        "Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics";
    const bortleAttribution = (config.bortleAttribution || "").trim() || "Sky brightness overlay";

    const map = L.map(mapElement, {
        zoomControl: false,
        minZoom: 2,
        maxZoom: 8,
        worldCopyJump: true,
        maxBounds: L.latLngBounds(L.latLng(-85, -180), L.latLng(85, 180)),
        maxBoundsViscosity: 0.8
    });

    map.setView([20, 0], 2);
    L.control.zoom({ position: "bottomright" }).addTo(map);

    L.tileLayer(satelliteUrl, {
        attribution: satelliteAttribution,
        maxZoom: 8
    }).addTo(map);

    map.createPane("weatherPane");
    map.createPane("bortlePane");
    const weatherPane = map.getPane("weatherPane");
    const bortlePane = map.getPane("bortlePane");
    if (weatherPane) {
        weatherPane.style.zIndex = 450;
    }
    if (bortlePane) {
        bortlePane.style.zIndex = 460;
        bortlePane.style.mixBlendMode = "screen";
    }

    let weatherOpacity = weatherOpacityInput ? parseFloat(weatherOpacityInput.value) : 0.7;
    let bortleOpacity = bortleOpacityInput ? parseFloat(bortleOpacityInput.value) : 0.6;

    const overlayLayers = {};

    function setStatus(messages) {
        if (!statusEl) {
            return;
        }
        const text = messages.filter(Boolean).join(" ");
        statusEl.textContent = text;
        statusEl.classList.toggle("is-visible", Boolean(text));
    }

    function setLayerActive(name, isActive) {
        const layer = overlayLayers[name];
        if (!layer) {
            return;
        }
        if (isActive) {
            map.addLayer(layer);
        } else {
            map.removeLayer(layer);
        }
    }

    const omLib = window.OMWeatherMapLayer;
    const openMeteoReady = Boolean(omLib && omLib.addLeafletProtocolSupport && omLib.omProtocol);

    function buildOpenMeteoUrl(variable) {
        if (!openMeteoBaseUrl) {
            return "";
        }
        const joiner = openMeteoBaseUrl.includes("?") ? "&" : "?";
        return `om://${openMeteoBaseUrl}${joiner}variable=${encodeURIComponent(variable)}`;
    }

    // Configure tile overlays once, then wire inputs to toggles.
    if (openMeteoReady && openMeteoBaseUrl) {
        const leafletAdapter = omLib.addLeafletProtocolSupport(L);
        leafletAdapter.addProtocol("om", omLib.omProtocol);

        const weatherLayerOptions = {
            opacity: weatherOpacity,
            pane: "weatherPane",
            attribution: openMeteoAttribution,
            maxZoom: 12
        };

        overlayLayers.rain = leafletAdapter.createTileLayer(
            buildOpenMeteoUrl("rain"),
            weatherLayerOptions
        );
        overlayLayers.wind = leafletAdapter.createTileLayer(
            buildOpenMeteoUrl("wind_speed_10m"),
            weatherLayerOptions
        );
        overlayLayers.temperature = leafletAdapter.createTileLayer(
            buildOpenMeteoUrl("temperature_2m"),
            weatherLayerOptions
        );
    }

    if (bortleUrl) {
        overlayLayers.bortle = L.tileLayer(bortleUrl, {
            opacity: bortleOpacity,
            pane: "bortlePane",
            attribution: bortleAttribution,
            className: "bortle-layer"
        });
    }

    const weatherLayerNames = ["rain", "wind", "temperature"];
    const messages = [];

    if (!openMeteoReady) {
        messages.push("Open-Meteo map library failed to load; weather layers are unavailable.");
    }
    if (!bortleUrl) {
        messages.push("Add BORTLE_TILE_URL to enable the Bortle overlay.");
    }
    setStatus(messages);

    layerInputs.forEach((input) => {
        const name = input.getAttribute("data-layer");
        const isWeatherLayer = weatherLayerNames.includes(name);
        const isAvailable = isWeatherLayer ? openMeteoReady : Boolean(bortleUrl);

        if (!isAvailable) {
            input.checked = false;
            input.disabled = true;
            const wrapper = input.closest(".layer-toggle");
            if (wrapper) {
                wrapper.classList.add("is-disabled");
            }
            return;
        }

        if (input.checked) {
            setLayerActive(name, true);
        }

        input.addEventListener("change", (event) => {
            setLayerActive(name, event.target.checked);
        });
    });

    if (weatherOpacityInput) {
        weatherOpacityInput.addEventListener("input", (event) => {
            weatherOpacity = parseFloat(event.target.value);
            weatherLayerNames.forEach((name) => {
                if (overlayLayers[name]) {
                    overlayLayers[name].setOpacity(weatherOpacity);
                }
            });
        });
    }

    if (bortleOpacityInput) {
        bortleOpacityInput.addEventListener("input", (event) => {
            bortleOpacity = parseFloat(event.target.value);
            if (overlayLayers.bortle) {
                overlayLayers.bortle.setOpacity(bortleOpacity);
            }
        });
    }

    map.whenReady(() => {
        const wrap = document.querySelector(".map-wrap");
        if (wrap) {
            wrap.classList.add("is-ready");
        }
    });
})();
