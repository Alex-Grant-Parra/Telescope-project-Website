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
const showBelowHorizon = document.getElementById('show-below-horizon');
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
const minZoom = 1; // 80% - only slightly zoomed out
const maxZoom = 6.7; // 500% - zoomed way in
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
// Date/time helpers for local datetime input handling with rollover
function formatLocalDateTime(date) {
    // Formats a Date as YYYY-MM-DDTHH:MM in local time
    const pad = (n) => n.toString().padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function parseLocalDateTime(str) {
    // Safely parse local datetime string (YYYY-MM-DDTHH:MM)
    // new Date(str) with no timezone is treated as local time by modern browsers
    const d = new Date(str);
    if (isNaN(d.getTime())) return null;
    return d;
}

function setTimeControlFromDate(d, preserveSelectionSegment) {
    if (!timeControl || !(d instanceof Date) || isNaN(d)) return;
    const segBounds = preserveSelectionSegment ? getCurrentSegmentBounds(timeControl) : null;
    timeControl.value = formatLocalDateTime(d);
    // Try to keep the caret on the same segment if supported
    if (segBounds && typeof timeControl.setSelectionRange === 'function') {
        try { timeControl.setSelectionRange(segBounds.start, segBounds.end); } catch {}
    }
}

// Determine which segment of the datetime string the caret is on
// Returns one of: 'year'|'month'|'day'|'hour'|'minute' or null if unknown
function getCaretSegment(input) {
    if (!input) return null;
    const v = input.value || '';
    // Expect pattern YYYY-MM-DDTHH:MM (length 16)
    const pos = (typeof input.selectionStart === 'number') ? input.selectionStart : -1;
    if (pos < 0 || v.length < 16) return null;
    if (pos <= 4) return 'year';
    if (pos >= 5 && pos <= 7) return 'month';
    if (pos >= 8 && pos <= 10) return 'day';
    if (pos >= 11 && pos <= 13) return 'hour';
    return 'minute';
}

function getCurrentSegmentBounds(input) {
    const seg = getCaretSegment(input);
    if (!seg) return null;
    switch (seg) {
        case 'year': return { start: 0, end: 4 };
        case 'month': return { start: 5, end: 7 };
        case 'day': return { start: 8, end: 10 };
        case 'hour': return { start: 11, end: 13 };
        case 'minute': return { start: 14, end: 16 };
        default: return null;
    }
}

function adjustDateByUnit(date, unit, delta) {
    // Returns a new Date adjusted in local time, relying on JS rollover behavior
    const d = new Date(date.getTime());
    switch (unit) {
        case 'minute': d.setMinutes(d.getMinutes() + delta); break;
        case 'hour': d.setHours(d.getHours() + delta); break;
        case 'day': d.setDate(d.getDate() + delta); break;
        case 'month': d.setMonth(d.getMonth() + delta); break;
        case 'year': d.setFullYear(d.getFullYear() + delta); break;
        default: d.setMinutes(d.getMinutes() + delta); break;
    }
    // Zero seconds and ms for stability with our control
    d.setSeconds(0, 0);
    return d;
}

function handleTimeControlKeydown(e) {
    if (!timeControl) return;
    const key = e.key;
    if (key !== 'ArrowUp' && key !== 'ArrowDown') return;

    const raw = timeControl.value;
    let baseDate = parseLocalDateTime(raw);
    if (!baseDate) {
        baseDate = new Date();
        baseDate.setSeconds(0, 0);
    }

    // Determine which unit to adjust. Prefer caret segment when available.
    let unit = getCaretSegment(timeControl);
    // Fallback to modifier keys if caret segment is unavailable
    // Alt: month, Ctrl: day, Shift: hour, Ctrl+Shift: year. Default: minute
    if (!unit) {
        if (e.ctrlKey && e.shiftKey) unit = 'year';
        else if (e.altKey) unit = 'month';
        else if (e.ctrlKey) unit = 'day';
        else if (e.shiftKey) unit = 'hour';
        else unit = 'minute';
    }

    const delta = (key === 'ArrowUp') ? 1 : -1;
    const newDate = adjustDateByUnit(baseDate, unit, delta);

    // Prevent native stepping to avoid double changes
    e.preventDefault();
    // Update input and redraw. Try to preserve caret segment.
    setTimeControlFromDate(newDate, true);
    draw();
}
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

// Convert RA/Dec to Alt/Az for a given date, latitude, and longitude (degrees)
function radecToAltAz(raDeg, decDeg, date, latDeg, lonDeg) {
    const lstDegVal = lstDegrees(new Date(date.toISOString()), lonDeg);
    const H = (lstDegVal - raDeg) * Math.PI / 180; // hour angle in radians
    const dec = decDeg * Math.PI / 180;
    const lat = latDeg * Math.PI / 180;

    const sinAlt = Math.sin(dec) * Math.sin(lat) + Math.cos(dec) * Math.cos(lat) * Math.cos(H);
    const alt = Math.asin(sinAlt);

    // Azimuth: 0° = North, 90° = East (matches our horizon grid)
    const y = -Math.cos(dec) * Math.sin(H);
    const x = Math.tan(dec) * Math.cos(lat) - Math.cos(H) * Math.sin(lat);
    let az = Math.atan2(y, x);
    if (az < 0) az += 2 * Math.PI;

    return { altDeg: alt * 180 / Math.PI, azDeg: az * 180 / Math.PI };
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

// 3D rotation (optional pre-rotation by latitude/longitude, then user rotation)
function rotate([x, y, z], rotX, rotY, lat, lon) {
    // Apply longitude (azimuthal) rotation about Y axis
    let x1 = x * Math.cos(lon) - z * Math.sin(lon);
    let z1 = x * Math.sin(lon) + z * Math.cos(lon);
    // Apply latitude rotation about X axis
    let y1 = y * Math.cos(lat) - z1 * Math.sin(lat);
    let z2 = y * Math.sin(lat) + z1 * Math.cos(lat);
    // User rotation: Y then X
    let x2 = x1 * Math.cos(rotY) - z2 * Math.sin(rotY);
    let z3 = x1 * Math.sin(rotY) + z2 * Math.cos(rotY);
    let y2 = y1 * Math.cos(rotX) - z3 * Math.sin(rotX);
    let z4 = y1 * Math.sin(rotX) + z3 * Math.cos(rotX);
    return [x2, y2, z4];
}

// Project 3D point to 2D canvas
function project([x, y, z]) {
    // Perspective projection for camera inside sphere looking outward
    const fov = 1.2;
    const scale = Math.max(width, height) * 0.8 * zoom / (fov + z);
    return [
        width / 2 + x * scale,
        height / 2 - y * scale
    ];
}

// Ecliptic coordinate conversion
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

function drawEcliptic() {
    // Draw the ecliptic (beta=0) converted to horizon coordinates
    ctx.save();
    ctx.strokeStyle = "rgba(255, 215, 0, 0.6)"; // golden line
    ctx.lineWidth = 1.5;
    const cullThreshold = 0;
    ctx.beginPath();
    let started = false;

    const latDeg = parseFloat(latInput.value) || 0;
    const lonDeg = parseFloat(lonInput.value) || 0;
    let selectedDate = new Date();
    try { if (timeControl && timeControl.value) selectedDate = new Date(timeControl.value); } catch {}

    for (let lam = 0; lam <= 360; lam += 2) {
        const { raDeg, decDeg } = eclipticToEquatorial(lam, 0);
        const { altDeg, azDeg } = radecToAltAz(raDeg, decDeg, selectedDate, latDeg, lonDeg);
        let [x, y, z] = altazToXYZ(altDeg, azDeg);
        [x, y, z] = rotate([x, y, z], rotX, rotY, 0, 0);
        if (z <= cullThreshold) { started = false; continue; }
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
            if (z <= cullThreshold) { firstPoint = true; continue; } // break path across back side
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
            if (z <= cullThreshold) { firstPoint = true; continue; } // break path across back side
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

// Draw a translucent green tint for the region below the horizon (alt < 0)
function drawBelowHorizonTint() {
    ctx.save();
    ctx.fillStyle = 'rgba(50, 205, 50, 0.30)'; // grass green at ~30%
    const altStep = 5; // degrees
    const azStep = 5;  // degrees
    const cullThreshold = 0; // front hemisphere only

    // Iterate small horizon cells and fill quads that are fully visible (all corners z>0)
    for (let alt = -90; alt < 0; alt += altStep) {
        const alt2 = Math.min(alt + altStep, 0);
        for (let az = 0; az < 360; az += azStep) {
            const az2 = az + azStep;

            // Compute four corners in horizon coords
            let p1 = altazToXYZ(alt, az);
            let p2 = altazToXYZ(alt2, az);
            let p3 = altazToXYZ(alt2, az2);
            let p4 = altazToXYZ(alt, az2);

            // Apply only user rotation (horizon base frame)
            p1 = rotate(p1, rotX, rotY, 0, 0);
            p2 = rotate(p2, rotX, rotY, 0, 0);
            p3 = rotate(p3, rotX, rotY, 0, 0);
            p4 = rotate(p4, rotX, rotY, 0, 0);

            // Cull any cell that is partially or fully behind the camera to avoid artifacts
            if (p1[2] <= cullThreshold || p2[2] <= cullThreshold || p3[2] <= cullThreshold || p4[2] <= cullThreshold) {
                continue;
            }

            // Project and fill the quad
            const a = project(p1);
            const b = project(p2);
            const c = project(p3);
            const d = project(p4);
            ctx.beginPath();
            ctx.moveTo(a[0], a[1]);
            ctx.lineTo(b[0], b[1]);
            ctx.lineTo(c[0], c[1]);
            ctx.lineTo(d[0], d[1]);
            ctx.closePath();
            ctx.fill();
        }
    }
    ctx.restore();
}

// Draw equatorial coordinate grid
function drawEquatorialGrid() {
    ctx.save();
    ctx.strokeStyle = "rgba(255, 150, 100, 0.3)"; // Light orange
    ctx.lineWidth = 1;
    ctx.font = "12px sans-serif";
    ctx.fillStyle = "rgba(255, 150, 100, 0.6)";

    // Simple back-face culling - only draw lines facing the viewer
    const cullThreshold = 0;

    // Observer/time
    const latDeg = parseFloat(latInput.value) || 0;
    const lonDeg = parseFloat(lonInput.value) || 0;
    let selectedDate = new Date();
    try { if (timeControl && timeControl.value) selectedDate = new Date(timeControl.value); } catch {}
    currentLSTDeg = lstDegrees(new Date(selectedDate.toISOString()), lonDeg);

    // Draw declination circles in equatorial coords, converted to horizon
    for (let dec = -90; dec <= 90; dec += 10) {
        ctx.strokeStyle = (dec === 0) ? "rgba(255, 150, 100, 0.5)" : "rgba(255, 150, 100, 0.3)";
        ctx.beginPath();
        let firstPoint = true;
        for (let ra = 0; ra <= 360; ra += 3) {
            const { altDeg, azDeg } = radecToAltAz(ra, dec, selectedDate, latDeg, lonDeg);
            let [x, y, z] = altazToXYZ(altDeg, azDeg);
            // Only apply user rotation; horizon is our base frame
            [x, y, z] = rotate([x, y, z], rotX, rotY, 0, 0);
            if (z <= cullThreshold) { firstPoint = true; continue; }
            const [cx, cy] = project([x, y, z]);
            if (firstPoint) { ctx.moveTo(cx, cy); firstPoint = false; }
            else ctx.lineTo(cx, cy);
        }
        ctx.stroke();

        // Label declination lines every 30°
        if (dec % 30 === 0) {
            const { altDeg, azDeg } = radecToAltAz(0, dec, selectedDate, latDeg, lonDeg); // RA=0h point
            let [x, y, z] = altazToXYZ(altDeg, azDeg);
            [x, y, z] = rotate([x, y, z], rotX, rotY, 0, 0);
            if (z > cullThreshold) {
                const [cx, cy] = project([x, y, z]);
                ctx.fillText(`${dec}°`, cx + 5, cy - 5);
            }
        }
    }

    // Draw hour angle (HA) lines by converting HA -> RA (RA = LST - HA)
    ctx.strokeStyle = "rgba(255, 150, 100, 0.3)";
    for (let ha = -180; ha < 180; ha += 10) {
        let ra = currentLSTDeg - ha; // degrees
        ra = ((ra % 360) + 360) % 360;
        ctx.beginPath();
        let firstPoint = true;
        for (let dec = -90; dec <= 90; dec += 2) {
            const { altDeg, azDeg } = radecToAltAz(ra, dec, selectedDate, latDeg, lonDeg);
            let [x, y, z] = altazToXYZ(altDeg, azDeg);
            [x, y, z] = rotate([x, y, z], rotX, rotY, 0, 0);
            if (z <= cullThreshold) { firstPoint = true; continue; }
            const [cx, cy] = project([x, y, z]);
            if (firstPoint) { ctx.moveTo(cx, cy); firstPoint = false; }
            else ctx.lineTo(cx, cy);
        }
        ctx.stroke();

        // Label HA at celestial equator for multiples of 30° (2 hours)
        const norm30 = ((ha % 30) + 30) % 30;
        if (Math.abs(norm30) < 1e-6) {
            const { altDeg, azDeg } = radecToAltAz(ra, 0, selectedDate, latDeg, lonDeg);
            let [x, y, z] = altazToXYZ(altDeg, azDeg);
            [x, y, z] = rotate([x, y, z], rotX, rotY, 0, 0);
            if (z > cullThreshold) {
                const [cx, cy] = project([x, y, z]);
                let haHours = ha / 15;
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
    const latDeg = parseFloat(latInput.value) || 0;
    const lonDeg = parseFloat(lonInput.value) || 0;
    let selectedDate = new Date();
    try { if (timeControl && timeControl.value) selectedDate = new Date(timeControl.value); } catch {}
    currentLSTDeg = lstDegrees(new Date(selectedDate.toISOString()), lonDeg);

    const showStarsVal = showStars.checked;
    const showPlanetsVal = showPlanets.checked;

    // Optional below-horizon tint, draw first so grids and stars are above
    if (showBelowHorizon && showBelowHorizon.checked) {
        drawBelowHorizonTint();
    }

    // Draw coordinate grids (before stars so they appear behind stars but above tint)
    if (showHorizonGrid.checked) {
        // Horizon grid is defined directly in Alt/Az, only user rotation applies
        drawHorizonGrid(0, 0);
    }
    if (showEquatorialGrid.checked) {
        drawEquatorialGrid();
    }
    if (showEcliptic && showEcliptic.checked) {
        drawEcliptic();
    }

    // Draw stars/planets using true Alt/Az for given time and location
    for (const obj of stars) {
        const effectiveMag = obj.mag == null ? 50 : obj.mag; // Treat null magnitudes as 50
        if (effectiveMag > magLimit) continue;
        if (obj.type === "star" && !showStarsVal) continue;
        if (obj.type === "planet" && !showPlanetsVal) continue;

        const { altDeg, azDeg } = radecToAltAz(obj.ra, obj.dec, selectedDate, latDeg, lonDeg);
        let [x, y, z] = altazToXYZ(altDeg, azDeg);
        [x, y, z] = rotate([x, y, z], rotX, rotY, 0, 0);
        if (z <= 0) continue; // Only render objects in the front hemisphere
        const [cx, cy] = project([x, y, z]);

        if (obj.type === "planet") {
            const size = fixedPlanetSize; // Use fixed size for all planets
            ctx.globalAlpha = 1;
            if (obj.icon && planetImages[obj.icon]) {
                const img = planetImages[obj.icon];
                ctx.drawImage(img, cx - size/2, cy - size/2, size, size);
            } else {
                ctx.fillStyle = "#ffa500";
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
            ctx.globalAlpha = 1;
        }
    }

    // Draw orange highlight ring for searched object (using Alt/Az)
    if (searchedObject) {
        const effectiveMag = searchedObject.mag == null ? 50 : searchedObject.mag;
        if (effectiveMag <= magLimit) {
            const { altDeg, azDeg } = radecToAltAz(searchedObject.ra, searchedObject.dec, selectedDate, latDeg, lonDeg);
            let [x, y, z] = altazToXYZ(altDeg, azDeg);
            [x, y, z] = rotate([x, y, z], rotX, rotY, 0, 0);
            if (z > 0) {
                const [cx, cy] = project([x, y, z]);
                highlightAnimation += 0.1;
                const ringSize = 20 + Math.sin(highlightAnimation) * 5;
                const opacity = 0.7 + Math.sin(highlightAnimation * 2) * 0.3;
                ctx.strokeStyle = `rgba(255, 165, 0, ${opacity})`;
                ctx.lineWidth = 3;
                ctx.beginPath();
                ctx.arc(cx, cy, ringSize, 0, 2*Math.PI);
                ctx.stroke();
                ctx.lineWidth = 1;
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
    const latDeg = parseFloat(latInput.value) || 0;
    const lonDeg = parseFloat(lonInput.value) || 0;
    let selectedDate = new Date();
    try { if (timeControl && timeControl.value) selectedDate = new Date(timeControl.value); } catch {}

    for (const obj of stars) {
        const effectiveMag = obj.mag == null ? 50 : obj.mag;
        if (effectiveMag > magLimit) continue;
        if (obj.type === "star" && !showStars.checked) continue;
        if (obj.type === "planet" && !showPlanets.checked) continue;

        const { altDeg, azDeg } = radecToAltAz(obj.ra, obj.dec, selectedDate, latDeg, lonDeg);
        let [x, y, z] = altazToXYZ(altDeg, azDeg);
        [x, y, z] = rotate([x, y, z], rotX, rotY, 0, 0);
        if (z <= 0) continue;
        const [cx, cy] = project([x, y, z]);

        let size = obj.type === "planet" ? fixedPlanetSize : Math.max(1, 6 - effectiveMag);
        let hitRadius = obj.type === "planet" ? fixedPlanetSize/2 : size;
        if ((mx-cx)**2 + (my-cy)**2 < hitRadius*hitRadius*1.5) {
            const displayMag = obj.mag == null ? "null" : obj.mag;
            const lstDegNow = lstDegrees(new Date((timeControl && timeControl.value) ? new Date(timeControl.value).toISOString() : new Date().toISOString()), parseFloat(lonInput.value));
            const ha = hourAngleDegrees(obj.ra, lstDegNow);
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
if (showBelowHorizon) showBelowHorizon.addEventListener('change', draw);
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
    // Observer/time
    const latDeg = parseFloat(latInput.value) || 0;
    const lonDeg = parseFloat(lonInput.value) || 0;
    let selectedDate = new Date();
    try { if (timeControl && timeControl.value) selectedDate = new Date(timeControl.value); } catch {}

    function testRotation(testRotX, testRotY) {
        const { altDeg, azDeg } = radecToAltAz(obj.ra, obj.dec, selectedDate, latDeg, lonDeg);
        let [x, y, z] = altazToXYZ(altDeg, azDeg);
        [x, y, z] = rotate([x, y, z], testRotX, testRotY, 0, 0);
        if (z <= 0) return null; // Behind camera
        const [screenX, screenY] = project([x, y, z]);
        return [screenX, screenY, z];
    }

    const centerX = width / 2;
    const centerY = height / 2;
    let bestRotX = rotX;
    let bestRotY = rotY;
    let bestDistance = Infinity;

    const searchRange = Math.PI; // 180 degrees
    const searchSteps = 20;

    for (let i = 0; i < searchSteps; i++) {
        for (let j = 0; j < searchSteps; j++) {
            const testRotY = rotY + (i - searchSteps/2) * searchRange / searchSteps;
            const testRotX = rotX + (j - searchSteps/2) * searchRange / searchSteps;
            const constrainedRotX = Math.max(-Math.PI/2, Math.min(Math.PI/2, testRotX));
            const result = testRotation(constrainedRotX, testRotY);
            if (result) {
                const [screenX, screenY, z] = result;
                const distance = Math.hypot(screenX - centerX, screenY - centerY);
                if (distance < bestDistance && z > 0) {
                    bestDistance = distance;
                    bestRotX = constrainedRotX;
                    bestRotY = testRotY;
                }
            }
        }
    }

    if (bestDistance > 100) {
        for (let i = 0; i < searchSteps; i++) {
            for (let j = 0; j < searchSteps; j++) {
                const testRotY = (i / searchSteps) * 2 * Math.PI - Math.PI;
                const testRotX = (j / searchSteps) * Math.PI - Math.PI/2;
                const constrainedRotX = Math.max(-Math.PI/2, Math.min(Math.PI/2, testRotX));
                const result = testRotation(constrainedRotX, testRotY);
                if (result) {
                    const [screenX, screenY, z] = result;
                    const distance = Math.hypot(screenX - centerX, screenY - centerY);
                    if (distance < bestDistance && z > 0) {
                        bestDistance = distance;
                        bestRotX = constrainedRotX;
                        bestRotY = testRotY;
                    }
                }
            }
        }
    }

    while (bestRotY - rotY > Math.PI) bestRotY -= 2*Math.PI;
    while (bestRotY - rotY < -Math.PI) bestRotY += 2*Math.PI;

    const startRotX = rotX;
    const startRotY = rotY;
    const steps = 30;
    let step = 0;

    function animateMove() {
        if (step <= steps) {
            const progress = step / steps;
            const eased = 1 - Math.pow(1 - progress, 3);
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
    console.log('%cStar Map JS loaded v2025-10-13-5', 'color:#0bf');
    // Initialize time control to current local time (rounded to minute)
    if (timeControl) {
        const now = new Date();
        now.setSeconds(0, 0);
        timeControl.value = formatLocalDateTime(now);
        timeControl.addEventListener('change', draw);
        // Add keyboard rollover handling for ArrowUp/ArrowDown
        timeControl.addEventListener('keydown', handleTimeControlKeydown);
    }
    if (timeNowBtn) {
        timeNowBtn.addEventListener('click', () => {
            const now = new Date();
            now.setSeconds(0, 0);
            if (timeControl) timeControl.value = formatLocalDateTime(now);
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