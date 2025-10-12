// 3D Planetarium JavaScript
// Get star/planet data from Flask
const stars = JSON.parse(document.getElementById('stars-data').textContent);

// Image cache for planet sprites
const planetImages = {};
const fixedPlanetSize = 24; // Fixed size for all planets (increased for better visibility)

// Find the actual magnitude range in the data
let minMag = Infinity, maxMag = -Infinity;
for (const obj of stars) {
    if (obj.mag != null && !isNaN(obj.mag)) {
        minMag = Math.min(minMag, obj.mag);
        maxMag = Math.max(maxMag, obj.mag);
    }
}

// Set reasonable defaults if no valid magnitudes found
if (minMag === Infinity) minMag = -2;
if (maxMag === -Infinity) maxMag = 10;

// UI elements
const magFilter = document.getElementById('mag-filter');
const magValue = document.getElementById('mag-value');
const latInput = document.getElementById('latitude');
const lonInput = document.getElementById('longitude');
const showStars = document.getElementById('show-stars');
const showPlanets = document.getElementById('show-planets');
const showHorizonGrid = document.getElementById('show-horizon-grid');
const showEquatorialGrid = document.getElementById('show-equatorial-grid');
const showEcliptic = document.getElementById('show-ecliptic');
const timeControl = document.getElementById('time-control');
const timeNowBtn = document.getElementById('time-now');
const timeRotate = document.getElementById('time-rotate');
let currentLSTDeg = 0; // updated per draw based on time and longitude
const resetBtn = document.getElementById('reset-view');
const helpBtn = document.getElementById('help-btn');
const helpModal = document.getElementById('help-modal');
const closeHelp = document.getElementById('close-help');
const loading = document.getElementById('loading');
// Debug orientation toggle
const flipVerticalCheckbox = document.getElementById('flip-vertical');

// Context menu elements
const magContextMenu = document.getElementById('mag-context-menu');
const magCustomInput = document.getElementById('mag-custom-input');
const magApplyBtn = document.getElementById('mag-apply');
const magCancelBtn = document.getElementById('mag-cancel');

// Search elements
const searchInput = document.getElementById('search-object');
const searchBtn = document.getElementById('search-btn');
const clearSearchBtn = document.getElementById('clear-search-btn');

// Search state
let searchedObject = null;
let highlightAnimation = 0;

// Controls inversion state (affects drag deltas only)
let invertControls = false;

// Canvas setup
const canvas = document.getElementById('planetarium');
const ctx = canvas.getContext('2d');
let width = window.innerWidth, height = window.innerHeight;
canvas.width = width;
canvas.height = height;

// Set up the magnitude slider with actual data range
magFilter.min = minMag.toFixed(1);
magFilter.max = maxMag.toFixed(1);
magFilter.step = "0.1";
magFilter.value = "4.0"; // Start at magnitude 4
magValue.textContent = "4.0";

// 3D sphere parameters
// Increase the sphere radius for a more immersive effect
const R = Math.min(width, height) * 0.9 / 2;
let rotX = 0, rotY = 0; // rotation angles
let dragging = false, lastX = 0, lastY = 0;

// Zoom parameters
let zoom = 1.0; // Default zoom level
const minZoom = 0.8; // 80% - only slightly zoomed out
const maxZoom = 5.0; // 500% - zoomed way in
const zoomStep = 0.1; // Zoom increment per scroll

// Camera is inside the sphere: invert z-culling (draw z < 0)
// Convert RA/DEC to 3D Cartesian coordinates
function radecToXYZ(ra, dec) {
    // RA in degrees, DEC in degrees
    const raRad = ra * Math.PI / 180;
    const decRad = dec * Math.PI / 180;
    const x = Math.cos(decRad) * Math.cos(raRad);
    const y = Math.sin(decRad);
    const z = Math.cos(decRad) * Math.sin(raRad);
    return [x, y, z];
}

// Time and sidereal time utilities
// Convert a Date to Julian Date (UTC)
function toJulianDate(date) {
    // Algorithm from NOAA; date should be a JS Date in UTC
    const year = date.getUTCFullYear();
    let month = date.getUTCMonth() + 1; // 1-12
    const day = date.getUTCDate() + (date.getUTCHours() + (date.getUTCMinutes() + date.getUTCSeconds() / 60) / 60) / 24;
    let Y = year;
    let M = month;
    if (M <= 2) { Y -= 1; M += 12; }
    const A = Math.floor(Y / 100);
    const B = 2 - A + Math.floor(A / 4);
    const JD = Math.floor(365.25 * (Y + 4716)) + Math.floor(30.6001 * (M + 1)) + day + B - 1524.5;
    return JD;
}

// Greenwich Mean Sidereal Time in degrees (0-360)
function gmstDegrees(date) {
    // Use the IAU 1982/1994 expression based on full Julian Date
    const JD = toJulianDate(date);
    const T = (JD - 2451545.0) / 36525.0;
    let gmst = 280.46061837 + 360.98564736629 * (JD - 2451545.0) + 0.000387933 * T * T - (T * T * T) / 38710000.0;
    gmst = ((gmst % 360) + 360) % 360; // normalize
    return gmst;
}

// Local Sidereal Time in degrees given longitude in degrees (east positive)
function lstDegrees(date, longitudeDeg) {
    const gmst = gmstDegrees(date);
    let lst = gmst + longitudeDeg; // East positive
    lst = ((lst % 360) + 360) % 360; // normalize 0-360
    return lst;
}

// Compute Hour Angle (degrees, range -180..+180) for a given RA (deg) and LST (deg)
function hourAngleDegrees(raDeg, lstDeg) {
    // HA = LST - RA
    let ha = lstDeg - raDeg;
    // normalize to -180..+180 for labeling aesthetics
    ha = ((ha + 180) % 360 + 360) % 360 - 180;
    return ha;
}

// 3D rotation (including local latitude/longitude)
function rotate([x, y, z], rotX, rotY, lat, lon) {
    // Apply longitude (azimuthal) rotation
    let x1 = x * Math.cos(lon) - z * Math.sin(lon);
    let z1 = x * Math.sin(lon) + z * Math.cos(lon);
    // Apply latitude (altitude) rotation
    let y1 = y * Math.cos(lat) - z1 * Math.sin(lat);
    let z2 = y * Math.sin(lat) + z1 * Math.cos(lat);
    // User rotation (drag)
    let x2 = x1 * Math.cos(rotY) - z2 * Math.sin(rotY);
    let z3 = x1 * Math.sin(rotY) + z2 * Math.cos(rotY);
    let y2 = y1 * Math.cos(rotX) - z3 * Math.sin(rotX);
    let z4 = y1 * Math.sin(rotX) + z3 * Math.cos(rotX);
    return [x2, y2, z4];
}

// Project 3D point to 2D canvas (camera at center, looking outward)
function project([x, y, z]) {
    // Perspective projection for camera inside sphere looking outward
    // Use full screen dimensions instead of sphere radius
    const fov = 1.2; // field of view
    const scale = Math.max(width, height) * 0.8 * zoom / (fov + z); // Apply zoom factor
    // Canvas Y-axis: subtract y so positive y goes up on screen
    return [
        width / 2 + x * scale,
        height / 2 - y * scale
    ];
}

// Convert altitude/azimuth to Cartesian coordinates
function altazToXYZ(alt, az) {
    const altRad = alt * Math.PI / 180;
    const azRad = az * Math.PI / 180;
    const x = Math.cos(altRad) * Math.sin(azRad);
    const y = Math.sin(altRad);
    const z = Math.cos(altRad) * Math.cos(azRad);
    return [x, y, z];
}

// Convert ecliptic longitude/latitude (lambda, beta) to equatorial RA/Dec (degrees)
function eclipticToEquatorial(lambdaDeg, betaDeg) {
    // Mean obliquity of the ecliptic (approx, J2000)
    const eps = 23.4392911 * Math.PI / 180; // radians
    const lam = lambdaDeg * Math.PI / 180;
    const bet = betaDeg * Math.PI / 180;
    const sinDec = Math.sin(bet) * Math.cos(eps) + Math.cos(bet) * Math.sin(eps) * Math.sin(lam);
    const dec = Math.asin(sinDec);
    const y = Math.sin(lam) * Math.cos(eps) - Math.tan(bet) * Math.sin(eps);
    const x = Math.cos(lam);
    let ra = Math.atan2(y, x); // radians, range -pi..pi
    if (ra < 0) ra += 2 * Math.PI;
    return { raDeg: ra * 180 / Math.PI, decDeg: dec * 180 / Math.PI };
}

function drawEcliptic(lat, lon) {
    // Draw the ecliptic as beta=0 for lambda 0..360
    ctx.save();
    ctx.strokeStyle = "rgba(255, 215, 0, 0.6)"; // golden line
    ctx.lineWidth = 1.5;
    const cullThreshold = 0;
    ctx.beginPath();
    let started = false;
    for (let lam = 0; lam <= 360; lam += 2) {
        const { raDeg, decDeg } = eclipticToEquatorial(lam, 0);
        let [x, y, z] = radecToXYZ(raDeg, decDeg);
        [x, y, z] = rotate([x, y, z], rotX, rotY, lat, lon);
        if (z <= cullThreshold) {
            // restart segment after hidden portion
            started = false;
            continue;
        }
        const [cx, cy] = project([x, y, z]);
        if (!started) { ctx.moveTo(cx, cy); started = true; }
        else ctx.lineTo(cx, cy);
    }
    ctx.stroke();
    ctx.restore();
}

// Draw horizon coordinate grid
function drawHorizonGrid(lat, lon) {
    ctx.save();
    ctx.strokeStyle = "rgba(100, 150, 255, 0.3)"; // Light blue
    ctx.lineWidth = 1;
    ctx.font = "12px sans-serif";
    ctx.fillStyle = "rgba(100, 150, 255, 0.6)";

    // Simple back-face culling - only draw lines facing the viewer
    const cullThreshold = 0;

    // Draw altitude circles (elevation lines) - include negative altitudes
    for (let alt = -90; alt <= 90; alt += 10) {
        ctx.beginPath();
        let firstPoint = true;
        for (let az = 0; az <= 360; az += 3) {
            let [x, y, z] = altazToXYZ(alt, az);
            // Only apply user rotation, not lat/lon (horizon stays fixed)
            [x, y, z] = rotate([x, y, z], rotX, rotY, 0, 0);
            if (z <= cullThreshold) continue; // Adaptive culling based on zoom
            const [cx, cy] = project([x, y, z]);
            
            if (firstPoint) {
                ctx.moveTo(cx, cy);
                firstPoint = false;
            } else {
                ctx.lineTo(cx, cy);
            }
        }
        ctx.stroke();
        
        // Label altitude lines more frequently
        if (alt % 20 === 0 && alt !== 0) {
            let [x, y, z] = altazToXYZ(alt, 0); // North point
            [x, y, z] = rotate([x, y, z], rotX, rotY, 0, 0);
            if (z > cullThreshold) {
                const [cx, cy] = project([x, y, z]);
                ctx.fillText(`${alt}°`, cx + 5, cy - 5);
            }
        }
    }

    // Draw azimuth lines (compass directions)
    for (let az = 0; az < 360; az += 10) {
        ctx.beginPath();
        let firstPoint = true;
        for (let alt = -90; alt <= 90; alt += 2) {
            let [x, y, z] = altazToXYZ(alt, az);
            [x, y, z] = rotate([x, y, z], rotX, rotY, 0, 0);
            if (z <= cullThreshold) continue; // Adaptive culling
            const [cx, cy] = project([x, y, z]);
            
            if (firstPoint) {
                ctx.moveTo(cx, cy);
                firstPoint = false;
            } else {
                ctx.lineTo(cx, cy);
            }
        }
        ctx.stroke();
        
        // Label azimuth lines more frequently
        if (az % 30 === 0) {
            let [x, y, z] = altazToXYZ(5, az); // 5° above horizon
            [x, y, z] = rotate([x, y, z], rotX, rotY, 0, 0);
            if (z > cullThreshold) {
                const [cx, cy] = project([x, y, z]);
                ctx.fillText(`${az}°`, cx - 8, cy + 15);
            }
        }
    }

    // Draw and label cardinal directions
    const cardinals = [
        { az: 0, label: "N" },
        { az: 90, label: "E" },
        { az: 180, label: "S" },
        { az: 270, label: "W" }
    ];
    
    ctx.font = "16px sans-serif";
    ctx.fillStyle = "rgba(100, 150, 255, 0.8)";
    for (const cardinal of cardinals) {
        let [x, y, z] = altazToXYZ(5, cardinal.az); // 5° above horizon
        [x, y, z] = rotate([x, y, z], rotX, rotY, 0, 0);
        if (z > cullThreshold) {
            const [cx, cy] = project([x, y, z]);
            ctx.fillText(cardinal.label, cx - 8, cy + 5);
        }
    }
    
    ctx.restore();
}

// Draw equatorial coordinate grid
function drawEquatorialGrid(lat, lon) {
    ctx.save();
    ctx.strokeStyle = "rgba(255, 150, 100, 0.3)"; // Light orange
    ctx.lineWidth = 1;
    ctx.font = "12px sans-serif";
    ctx.fillStyle = "rgba(255, 150, 100, 0.6)";

    // Simple back-face culling - only draw lines facing the viewer
    const cullThreshold = 0;

    // Draw declination circles
    for (let dec = -90; dec <= 90; dec += 10) {
        if (dec === 0) ctx.strokeStyle = "rgba(255, 150, 100, 0.5)"; // Celestial equator more visible
        else ctx.strokeStyle = "rgba(255, 150, 100, 0.3)";
        
        ctx.beginPath();
        let firstPoint = true;
        for (let ra = 0; ra <= 360; ra += 3) {
            let [x, y, z] = radecToXYZ(ra, dec);
            [x, y, z] = rotate([x, y, z], rotX, rotY, lat, lon);
            if (z <= cullThreshold) continue; // Adaptive culling based on zoom
            const [cx, cy] = project([x, y, z]);
            
            if (firstPoint) {
                ctx.moveTo(cx, cy);
                firstPoint = false;
            } else {
                ctx.lineTo(cx, cy);
            }
        }
        ctx.stroke();
        
        // Label declination lines more frequently
        if (dec % 30 === 0) {
            let [x, y, z] = radecToXYZ(0, dec); // 0h RA
            [x, y, z] = rotate([x, y, z], rotX, rotY, lat, lon);
            if (z > cullThreshold) {
                const [cx, cy] = project([x, y, z]);
                ctx.fillText(`${dec}°`, cx + 5, cy - 5);
            }
        }
    }

    // Draw hour angle (HA) lines by converting HA -> RA (RA = LST - HA)
    // This way, the grid lines represent constant HA and move with time
    ctx.strokeStyle = "rgba(255, 150, 100, 0.3)";
    for (let ha = -180; ha < 180; ha += 10) {
        // Convert HA to corresponding RA for current time
        let ra = currentLSTDeg - ha; // degrees
        ra = ((ra % 360) + 360) % 360;
        ctx.beginPath();
        let firstPoint = true;
        for (let dec = -90; dec <= 90; dec += 2) {
            let [x, y, z] = radecToXYZ(ra, dec);
            [x, y, z] = rotate([x, y, z], rotX, rotY, lat, lon);
            if (z <= cullThreshold) continue; // Adaptive culling
            const [cx, cy] = project([x, y, z]);
            
            if (firstPoint) {
                ctx.moveTo(cx, cy);
                firstPoint = false;
            } else {
                ctx.lineTo(cx, cy);
            }
        }
        ctx.stroke();
        
        // Label HA at celestial equator for multiples of 30° (2 hours)
        const norm30 = ((ha % 30) + 30) % 30;
        if (Math.abs(norm30) < 1e-6) {
            let [x, y, z] = radecToXYZ(ra, 0);
            [x, y, z] = rotate([x, y, z], rotX, rotY, lat, lon);
            if (z > cullThreshold) {
                const [cx, cy] = project([x, y, z]);
                // Convert HA degrees to hours in range -12..+12
                let haHours = ha / 15;
                // Round to nearest integer hour for labels
                let label;
                if (Math.abs(haHours) < 0.5) label = 'HA 0h';
                else label = `HA ${(haHours > 0 ? '+' : '')}${Math.round(haHours)}h`;
                ctx.fillText(label, cx - 18, cy + 15);
            }
        }
    }
    
    ctx.restore();
}

// Draw all stars/planets
function draw() {
    ctx.clearRect(0, 0, width, height);
    // Remove celestial sphere outline to let stars fill entire screen

    // Get filter values
    const magLimit = parseFloat(magFilter.value);
    const lat = parseFloat(latInput.value) * Math.PI / 180;
    const geoLonDeg = parseFloat(lonInput.value) || 0;
    const lon = geoLonDeg * Math.PI / 180;
    // Compute LST for HA and optional time rotation
    let selectedDate = new Date();
    try { if (timeControl && timeControl.value) selectedDate = new Date(timeControl.value); } catch {}
    currentLSTDeg = lstDegrees(new Date(selectedDate.toISOString()), geoLonDeg);
    const siderealRot = -currentLSTDeg * Math.PI / 180;
    const baseLon = (timeRotate && timeRotate.checked) ? siderealRot : lon;
    const showStarsVal = showStars.checked;
    const showPlanetsVal = showPlanets.checked;

    // Draw coordinate grids (before stars so they appear behind)
    if (showHorizonGrid.checked) {
        drawHorizonGrid(lat, baseLon);
    }
    if (showEquatorialGrid.checked) {
        drawEquatorialGrid(lat, baseLon);
    }
    if (showEcliptic && showEcliptic.checked) {
        drawEcliptic(lat, baseLon);
    }

    // Draw stars/planets
    for (const obj of stars) {
        const effectiveMag = obj.mag == null ? 50 : obj.mag; // Treat null magnitudes as 50
        if (effectiveMag > magLimit) continue;
        if (obj.type === "star" && !showStarsVal) continue;
        if (obj.type === "planet" && !showPlanetsVal) continue;
        // Use cached Cartesian coordinates to avoid repeated trig calls
    let [x, y, z] = obj.xyz || radecToXYZ(obj.ra, obj.dec);
    [x, y, z] = rotate([x, y, z], rotX, rotY, lat, baseLon);
        // Only render objects in the front hemisphere (camera inside sphere looking out)
        if (z <= -0.1) continue; // Show objects in front of camera
        const [cx, cy] = project([x, y, z]);

        // Draw without ctx.save()/restore() per object (avoid expensive state push/pop)
        if (obj.type === "planet") {
            const size = fixedPlanetSize; // Use fixed size for all planets
            ctx.globalAlpha = 1;
            if (obj.icon && planetImages[obj.icon]) {
                // Draw the preloaded sprite image
                const img = planetImages[obj.icon];
                ctx.drawImage(img, cx - size/2, cy - size/2, size, size);
            } else {
                // Fallback to colored circle if image isn't loaded
                ctx.fillStyle = "#ffa500"; // Orange color for better visibility
                ctx.beginPath();
                ctx.arc(cx, cy, size/2, 0, 2*Math.PI);
                ctx.fill();
            }
        } else {
            const size = Math.max(1, 6 - effectiveMag);
            ctx.fillStyle = "#fff";
            ctx.globalAlpha = Math.max(0.5, 1 - effectiveMag/8);
            ctx.beginPath();
            ctx.arc(cx, cy, size, 0, 2*Math.PI);
            ctx.fill();
            ctx.globalAlpha = 1; // reset alpha for subsequent draws
        }
    }

    // Draw orange highlight ring for searched object
    if (searchedObject) {
        const magLimit = parseFloat(magFilter.value);
        const effectiveMag = searchedObject.mag == null ? 50 : searchedObject.mag;
        if (effectiveMag <= magLimit) {
            let [x, y, z] = searchedObject.xyz || radecToXYZ(searchedObject.ra, searchedObject.dec);
            [x, y, z] = rotate([x, y, z], rotX, rotY, lat, baseLon);
            if (z > -0.1) { // Object is visible
                const [cx, cy] = project([x, y, z]);

                // Animate the ring
                highlightAnimation += 0.1;
                const ringSize = 20 + Math.sin(highlightAnimation) * 5;
                const opacity = 0.7 + Math.sin(highlightAnimation * 2) * 0.3;

                ctx.strokeStyle = `rgba(255, 165, 0, ${opacity})`;
                ctx.lineWidth = 3;
                ctx.beginPath();
                ctx.arc(cx, cy, ringSize, 0, 2*Math.PI);
                ctx.stroke();
                ctx.lineWidth = 1; // reset
            }
        }
    }
}

// Mouse controls
canvas.addEventListener('mousedown', e => {
    dragging = true;
    lastX = e.clientX;
    lastY = e.clientY;
});
window.addEventListener('mousemove', e => {
    if (!dragging) return;
    // Optionally invert controls: affects deltas only
    const controlInvert = invertControls ? -1 : 1;
    rotY += (e.clientX - lastX) * 0.01 * controlInvert;
    rotX -= (e.clientY - lastY) * 0.01 * controlInvert;
    rotX = Math.max(-Math.PI/2, Math.min(Math.PI/2, rotX));
    lastX = e.clientX;
    lastY = e.clientY;
    draw();
});
window.addEventListener('mouseup', () => dragging = false);

// Click to show info
canvas.addEventListener('click', function(e) {
    const mx = e.clientX, my = e.clientY;
    const magLimit = parseFloat(magFilter.value);
    const lat = parseFloat(latInput.value) * Math.PI / 180;
    const geoLonDeg = parseFloat(lonInput.value) || 0;
    let selectedDate = new Date();
    try { if (timeControl && timeControl.value) selectedDate = new Date(timeControl.value); } catch {}
    const lstDeg = lstDegrees(new Date(selectedDate.toISOString()), geoLonDeg);
    const siderealRot = -lstDeg * Math.PI / 180;
    const baseLon = (timeRotate && timeRotate.checked) ? siderealRot : (geoLonDeg * Math.PI / 180);
    for (const obj of stars) {
        const effectiveMag = obj.mag == null ? 50 : obj.mag; // Treat null magnitudes as 50
        if (effectiveMag > magLimit) continue;
        if (obj.type === "star" && !showStars.checked) continue;
        if (obj.type === "planet" && !showPlanets.checked) continue;
    let [x, y, z] = obj.xyz || radecToXYZ(obj.ra, obj.dec);
    [x, y, z] = rotate([x, y, z], rotX, rotY, lat, baseLon);
        if (z <= -0.1) continue;
        const [cx, cy] = project([x, y, z]);
        
        // Allow clicking stars anywhere on screen - remove bounds checking
        
        let size = obj.type === "planet" ? fixedPlanetSize : Math.max(1, 6 - effectiveMag);
        let hitRadius = obj.type === "planet" ? fixedPlanetSize/2 : size;
        if ((mx-cx)**2 + (my-cy)**2 < hitRadius*hitRadius*1.5) {
            const displayMag = obj.mag == null ? "null" : obj.mag;
            // Show HA for the selected time
            const lstDeg = lstDegrees(new Date((timeControl && timeControl.value) ? new Date(timeControl.value).toISOString() : new Date().toISOString()), parseFloat(lonInput.value));
            const ha = hourAngleDegrees(obj.ra, lstDeg);
            document.getElementById('info').innerHTML =
                `<b>${obj.name}</b><br>RA: ${obj.ra.toFixed(2)}° | HA: ${(ha/15).toFixed(2)}h<br>DEC: ${obj.dec.toFixed(2)}°<br>Mag: ${displayMag}<br>
                 <button onclick="trackObject('${obj.name}', ${obj.ra}, ${obj.dec}, ${obj.mag})" style="margin-top: 5px; padding: 4px 8px; background: #4CAF50; color: white; border: none; border-radius: 3px; cursor: pointer;">Track</button>`;
            return;
        }
    }
    document.getElementById('info').innerHTML = "Drag to rotate. Click a star/planet for info.";
});

// Responsive resize
window.addEventListener('resize', () => {
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = width;
    canvas.height = height;
    draw();
});

// Scroll wheel zoom
canvas.addEventListener('wheel', (e) => {
    e.preventDefault(); // Prevent page scroll
    // Keep zoom behavior consistent (checkbox only inverts drag/pan)
    const scrollDirection = e.deltaY > 0 ? -1 : 1; // positive deltaY => zoom out
    const zoomChange = scrollDirection * zoomStep;

    zoom = Math.max(minZoom, Math.min(maxZoom, zoom + zoomChange));
    
    draw();
}, { passive: false });

// Preload planet icons with proper error handling
function preloadPlanetImages() {
    const loadPromises = [];
    console.log('Starting to preload planet images...');
    
    for (const obj of stars) {
        if (obj.type === "planet" && obj.icon && !planetImages[obj.icon]) {
            console.log(`Loading planet icon for ${obj.name}: ${obj.icon}`);
            const loadPromise = new Promise((resolve, reject) => {
                const img = new Image();
                img.onload = () => {
                    planetImages[obj.icon] = img;
                    console.log(`Successfully loaded icon for ${obj.name}`);
                    resolve();
                };
                img.onerror = () => {
                    console.warn(`Failed to load planet icon: ${obj.icon} for ${obj.name}`);
                    resolve(); // Continue even if image fails to load
                };
                img.src = obj.icon;
            });
            loadPromises.push(loadPromise);
        }
    }
    
    console.log(`Loading ${loadPromises.length} planet images...`);
    return Promise.all(loadPromises).then(() => {
        console.log('All planet images loaded. Cache contains:', Object.keys(planetImages));
    });
}

// UI event listeners
magFilter.addEventListener('input', () => {
    magValue.textContent = magFilter.value;
    draw();
});
latInput.addEventListener('change', draw);
lonInput.addEventListener('change', draw);
showStars.addEventListener('change', draw);
showPlanets.addEventListener('change', draw);
showHorizonGrid.addEventListener('change', draw);
showEquatorialGrid.addEventListener('change', draw);
if (showEcliptic) showEcliptic.addEventListener('change', draw);
if (timeRotate) timeRotate.addEventListener('change', draw);
if (flipVerticalCheckbox) {
    flipVerticalCheckbox.addEventListener('change', () => {
        // Capture current orientation so toggling doesn't move the map
        const prevRotX = rotX;
        const prevRotY = rotY;
        const prevZoom = zoom;

        invertControls = !!flipVerticalCheckbox.checked;
        try { localStorage.setItem('starMap.flipVertical', invertControls ? '1' : '0'); } catch {}
        console.log('Invert controls set to', invertControls);
        // Restore orientation and redraw once to ensure no visual jump
        requestAnimationFrame(() => {
            rotX = prevRotX;
            rotY = prevRotY;
            zoom = prevZoom;
            draw();
        });
    });
}
resetBtn.addEventListener('click', () => {
    rotX = 0; rotY = 0;
    zoom = 1.0; // Reset zoom level
    latInput.value = 0;
    lonInput.value = 0;
    magFilter.value = maxMag.toFixed(1); // Reset to show all objects
    magValue.textContent = maxMag.toFixed(1);
    showStars.checked = true;
    showPlanets.checked = true;
    clearSearch(); // Clear search when resetting view
    draw();
});
// Search event listeners (guarded)
if (searchBtn) searchBtn.addEventListener('click', searchObject);
else console.warn('searchBtn not found');
if (clearSearchBtn) clearSearchBtn.addEventListener('click', clearSearch);
else console.warn('clearSearchBtn not found');
searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        searchObject();
    } else if (e.key === 'Escape') {
        clearSearch();
    }
});
helpBtn.addEventListener('click', () => {
    helpModal.style.display = "flex";
});
closeHelp.addEventListener('click', () => {
    helpModal.style.display = "none";
});
helpModal.addEventListener('click', (e) => {
    if (e.target === helpModal) helpModal.style.display = "none";
});

// Expose functions to global scope so inline onclick handlers work robustly
window.trackObject = trackObject;
window.searchObject = searchObject;
window.clearSearch = clearSearch;

// Magnitude slider context menu
magFilter.addEventListener('contextmenu', (e) => {
    e.preventDefault();
    magContextMenu.style.display = 'block';
    magContextMenu.style.left = e.pageX + 'px';
    magContextMenu.style.top = e.pageY + 'px';
    magCustomInput.value = magFilter.value;
    magCustomInput.focus();
    magCustomInput.select();
});

// Context menu functionality
function hideContextMenu() {
    magContextMenu.style.display = 'none';
}

magApplyBtn.addEventListener('click', () => {
    const customValue = parseFloat(magCustomInput.value);
    if (!isNaN(customValue) && customValue >= minMag && customValue <= maxMag) {
        magFilter.value = customValue.toFixed(1);
        magValue.textContent = customValue.toFixed(1);
        draw();
    } else {
        alert(`Please enter a magnitude value between ${minMag.toFixed(1)} and ${maxMag.toFixed(1)}`);
        return;
    }
    hideContextMenu();
});

magCancelBtn.addEventListener('click', hideContextMenu);

// Handle Enter key in the input field
magCustomInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        magApplyBtn.click();
    } else if (e.key === 'Escape') {
        hideContextMenu();
    }
});

// Hide context menu when clicking elsewhere
document.addEventListener('click', (e) => {
    if (!magContextMenu.contains(e.target) && e.target !== magFilter) {
        hideContextMenu();
    }
});

// Hide loading screen after first draw
function hideLoading() {
    loading.style.display = "none";
}

// Function to track a celestial object
function trackObject(name, ra, dec, mag) {
    fetch('/track_star', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            name: name,
            ra: ra,
            dec: dec,
            mag: mag
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'tracking') {
            document.getElementById('info').innerHTML = 
                `<b>${name}</b><br>RA: ${ra.toFixed(2)}°<br>DEC: ${dec.toFixed(2)}°<br>Mag: ${mag}<br>
                 <span style="color: #4CAF50; font-weight: bold;">✓ Tracking ${name}</span>`;
            console.log(`Successfully started tracking ${name}`);
        } else {
            console.error('Tracking failed:', data);
            alert('Failed to start tracking. Please try again.');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Failed to start tracking. Please check your connection.');
    });
}

// Function to search for objects
function searchObject() {
    const searchValue = searchInput.value.trim();
    if (!searchValue) {
        alert('Please enter a search term.');
        return;
    }

    fetch('/interface/search_object', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ searchValue: searchValue })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success' && data.data) {
            const objData = data.data;
            // Find the object in our stars array or use the search result
            let foundObject = null;
            
            // First try to find it in the existing stars array
            for (const obj of stars) {
                if (obj.name && objData.Name && 
                    obj.name.toLowerCase() === objData.Name.toLowerCase()) {
                    foundObject = obj;
                    break;
                }
            }
            
            // If not found in stars array, create from search result
            if (!foundObject) {
                foundObject = {
                    name: objData.Name,
                    ra: parseFloat(objData.RA) || 0,
                    dec: parseFloat(objData.DEC) || 0,
                    mag: objData['V-Mag'] || 30,
                    type: objData.type || 'star'
                };
                // Precompute xyz for transient search result
                // Note: Do NOT invert Y here; projection already handles canvas Y direction
                const _tmp = radecToXYZ(foundObject.ra, foundObject.dec);
                foundObject.xyz = _tmp;
            }
            
            // Set as searched object and move camera to it
            searchedObject = foundObject;
            highlightAnimation = 0;
            moveToObject(foundObject);
            
            // Show info
            const lstDeg2 = lstDegrees(new Date((timeControl && timeControl.value) ? new Date(timeControl.value).toISOString() : new Date().toISOString()), parseFloat(lonInput.value));
            const ha2 = hourAngleDegrees(foundObject.ra, lstDeg2);
            document.getElementById('info').innerHTML = 
                `<b>🔍 ${foundObject.name}</b><br>RA: ${foundObject.ra.toFixed(2)}° | HA: ${(ha2/15).toFixed(2)}h<br>DEC: ${foundObject.dec.toFixed(2)}°<br>Mag: ${foundObject.mag}<br>
                 <button onclick="trackObject('${foundObject.name}', ${foundObject.ra}, ${foundObject.dec}, ${foundObject.mag})" style="margin-top: 5px; padding: 4px 8px; background: #4CAF50; color: white; border: none; border-radius: 3px; cursor: pointer;">Track</button>`;
        } else {
            alert(data.message || 'Object not found.');
        }
    })
    .catch(error => {
        console.error('Search error:', error);
        alert('Search failed. Please try again.');
    });
}

// Function to move camera to look at an object
function moveToObject(obj) {
    // Get observer settings
    const lat = parseFloat(latInput.value) * Math.PI / 180;
    const geoLonDeg = parseFloat(lonInput.value) || 0;
    const lon = geoLonDeg * Math.PI / 180;
    let selectedDate = new Date();
    try { if (timeControl && timeControl.value) selectedDate = new Date(timeControl.value); } catch {}
    const lstDeg = lstDegrees(new Date(selectedDate.toISOString()), geoLonDeg);
    const siderealRot = -lstDeg * Math.PI / 180;
    const baseLon = (timeRotate && timeRotate.checked) ? siderealRot : lon;
    
    // Convert RA/DEC to Azimuth/Elevation
    // This is a simplified conversion - for a proper implementation you'd need
    // to account for the current time and date, but for now we'll use the 
    // horizon coordinate system mapping that's already in the code
    
    // Since the sky is plotted in az/elv, we need to work with altitude/azimuth
    // The existing rotate() function handles the conversion from RA/DEC to the 
    // final 3D position. We need to find what user rotations center the object.
    
    // Let's use a different approach: find the rotation that puts the object at screen center
    function testRotation(testRotX, testRotY) {
        let [x, y, z] = obj.xyz || radecToXYZ(obj.ra, obj.dec);
    [x, y, z] = rotate([x, y, z], testRotX, testRotY, lat, baseLon);
        if (z <= -0.1) return null; // Behind camera
        const [screenX, screenY] = project([x, y, z]);
        return [screenX, screenY, z];
    }
    
    // Simple search approach - try different rotations to find one that centers the object
    const centerX = width / 2;
    const centerY = height / 2;
    let bestRotX = rotX;
    let bestRotY = rotY;
    let bestDistance = Infinity;
    
    // Search in a reasonable range around current position
    const searchRange = Math.PI; // 180 degrees
    const searchSteps = 20;
    
    for (let i = 0; i < searchSteps; i++) {
        for (let j = 0; j < searchSteps; j++) {
            const testRotY = rotY + (i - searchSteps/2) * searchRange / searchSteps;
            const testRotX = rotX + (j - searchSteps/2) * searchRange / searchSteps;
            
            // Constrain rotX
            const constrainedRotX = Math.max(-Math.PI/2, Math.min(Math.PI/2, testRotX));
            
            const result = testRotation(constrainedRotX, testRotY);
            if (result) {
                const [screenX, screenY, z] = result;
                const distance = Math.sqrt((screenX - centerX)**2 + (screenY - centerY)**2);
                
                if (distance < bestDistance && z > 0) {
                    bestDistance = distance;
                    bestRotX = constrainedRotX;
                    bestRotY = testRotY;
                }
            }
        }
    }
    
    // If we didn't find a good position, try a wider search
    if (bestDistance > 100) {
        for (let i = 0; i < searchSteps; i++) {
            for (let j = 0; j < searchSteps; j++) {
                const testRotY = (i / searchSteps) * 2 * Math.PI - Math.PI;
                const testRotX = (j / searchSteps) * Math.PI - Math.PI/2;
                
                const constrainedRotX = Math.max(-Math.PI/2, Math.min(Math.PI/2, testRotX));
                
                const result = testRotation(constrainedRotX, testRotY);
                if (result) {
                    const [screenX, screenY, z] = result;
                    const distance = Math.sqrt((screenX - centerX)**2 + (screenY - centerY)**2);
                    
                    if (distance < bestDistance && z > 0) {
                        bestDistance = distance;
                        bestRotX = constrainedRotX;
                        bestRotY = testRotY;
                    }
                }
            }
        }
    }
    
    // Normalize rotY for smooth animation
    while (bestRotY - rotY > Math.PI) bestRotY -= 2*Math.PI;
    while (bestRotY - rotY < -Math.PI) bestRotY += 2*Math.PI;
    
    console.log(`Moving to ${obj.name}:`);
    console.log(`  Found position at distance ${bestDistance.toFixed(1)} pixels from center`);
    console.log(`  Target: rotY=${(bestRotY*180/Math.PI).toFixed(1)}°, rotX=${(bestRotX*180/Math.PI).toFixed(1)}°`);
    console.log(`  Current: rotY=${(rotY*180/Math.PI).toFixed(1)}°, rotX=${(rotX*180/Math.PI).toFixed(1)}°`);
    
    // Animate to the target position
    const startRotX = rotX;
    const startRotY = rotY;
    const steps = 30;
    let step = 0;
    
    function animateMove() {
        if (step <= steps) {
            const progress = step / steps;
            const eased = 1 - Math.pow(1 - progress, 3); // Ease-out cubic
            
            rotX = startRotX + (bestRotX - startRotX) * eased;
            rotY = startRotY + (bestRotY - startRotY) * eased;
            
            draw();
            step++;
            requestAnimationFrame(animateMove);
        }
    }
    
    animateMove();
}

// Function to clear search
function clearSearch() {
    searchedObject = null;
    searchInput.value = '';
    document.getElementById('info').innerHTML = "Drag to rotate. Click a star/planet for info.";
    draw();
}

// Initial draw and loading
window.addEventListener('DOMContentLoaded', () => {
    console.log('%cStar Map JS loaded v2025-10-12-6', 'color:#0bf');
    // Initialize time control to current local time (rounded to minute)
    if (timeControl) {
        const now = new Date();
        now.setSeconds(0, 0);
        const pad = (n) => n.toString().padStart(2, '0');
        const local = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
        timeControl.value = local;
        timeControl.addEventListener('change', draw);
    }
    if (timeNowBtn) {
        timeNowBtn.addEventListener('click', () => {
            const now = new Date();
            now.setSeconds(0, 0);
            const pad = (n) => n.toString().padStart(2, '0');
            const local = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
            if (timeControl) timeControl.value = local;
            draw();
        });
    }
    // Initialize flip vertical from localStorage, if present
    try {
        const saved = localStorage.getItem('starMap.flipVertical');
        if (flipVerticalCheckbox && (saved === '0' || saved === '1')) {
            invertControls = (saved === '1');
            flipVerticalCheckbox.checked = invertControls;
        } else if (flipVerticalCheckbox) {
            invertControls = !!flipVerticalCheckbox.checked;
        }
    } catch { invertControls = !!(flipVerticalCheckbox && flipVerticalCheckbox.checked); }
    console.log('DOM loaded. Star data:', stars.filter(s => s.type === 'planet'));
    // Precompute Cartesian coordinates (x,y,z) for all objects to reduce per-frame trig work
    function precomputeStars() {
        for (const obj of stars) {
            try {
                const _v = radecToXYZ(obj.ra, obj.dec);
                // Keep native coordinate orientation: +Dec (north) maps upward in project()
                obj.xyz = _v;
            } catch (e) {
                // Fallback in case of bad data
                const _v = radecToXYZ(0, 0);
                obj.xyz = _v;
            }
        }
    }
    precomputeStars();
    // Preload planet images first, then draw
    preloadPlanetImages().then(() => {
    console.log('Images preloaded, starting first draw...');
        draw();
        setTimeout(hideLoading, 400); // allow a short delay for effect
        
        // Start animation loop for search highlighting
        function animate() {
            if (searchedObject) {
                draw();
            }
            requestAnimationFrame(animate);
        }
        animate();
    });
});