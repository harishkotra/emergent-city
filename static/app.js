// Initialize Map
const map = L.map('map', {
    zoomControl: false // Move zoom control to bottom right
});

L.control.zoom({
    position: 'bottomright'
}).addTo(map);

// Store current tile layer so we can remove it later
let currentTileLayer = null;

const mapStyles = {
    dark: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    light: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    voyager: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
    satellite: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    watercolor: 'https://stamen-tiles-{s}.a.ssl.fastly.net/watercolor/{z}/{x}/{y}.jpg',
    terrain: 'https://stamen-tiles-{s}.a.ssl.fastly.net/terrain/{z}/{x}/{y}.jpg',
    cyclosm: 'https://{s}.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png'
};

function setMapStyle(styleKey) {
    if (currentTileLayer) {
        map.removeLayer(currentTileLayer);
    }

    let attribution = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>';
    if (styleKey === 'satellite') {
        attribution = 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community';
    }

    currentTileLayer = L.tileLayer(mapStyles[styleKey], {
        attribution: attribution,
        subdomains: 'abcd',
        maxZoom: 20
    }).addTo(map);
}

// Default to dark
setMapStyle('dark');

document.getElementById('map-style').addEventListener('change', (e) => {
    setMapStyle(e.target.value);
});

// Store agents and their visual elements
const agents = {};
let isFirstLoad = true;
let isSimulationRunning = false;

// Custom Icons for each role using DivIcon so we can use Emojis and CSS transitions
const createIcon = (role) => {
    let emoji = '🧍';
    if (role === 'shop') emoji = '🏪';
    if (role === 'driver') emoji = '🚗';

    return L.divIcon({
        className: 'agent-marker',
        html: `<div>${emoji}</div>`,
        iconSize: [30, 30],
        iconAnchor: [15, 15] // Center it
    });
};

const TICK_INTERVAL_MS = 2000;
const POLL_INTERVAL_MS = 500;
const SPEED = 0.0003; // Lat/Lon degrees per second (~30m/s)

function updateUI(data) {
    // Center map on first load
    if (isFirstLoad && data.center.lat !== 0) {
        map.setView([data.center.lat, data.center.lon], 15);
        isFirstLoad = false;
    }

    isSimulationRunning = data.running;
    const dot = document.getElementById('status-dot');
    const text = document.getElementById('status-text');
    const btn = document.getElementById('toggle-btn');
    const loadingOverlay = document.getElementById('loading-overlay');

    if (data.loading) {
        loadingOverlay.classList.remove('hidden');
    } else {
        loadingOverlay.classList.add('hidden');
    }

    if (isSimulationRunning) {
        dot.className = 'dot running';
        text.innerText = 'Running';
        btn.innerText = 'Stop Simulation';
        btn.style.backgroundColor = '#ef4444';
    } else {
        dot.className = 'dot stopped';
        text.innerText = 'Stopped';
        btn.innerText = 'Start Simulation';
        btn.style.backgroundColor = 'var(--accent)';
    }

    document.getElementById('val-total-money').innerText = `$${data.summary.total_money.toFixed(2)}`;
    document.getElementById('val-avg-wallet').innerText = `$${data.summary.avg_wallet.toFixed(2)}`;
    document.getElementById('val-tax').innerText = `$${data.summary.tax_collected.toFixed(2)}`;
    document.getElementById('val-congestion').innerText = data.summary.congestion;

    const activeIds = new Set();

    data.agents.forEach(agent => {
        activeIds.add(agent.id);

        const tooltipStr = `
            <b>ID:</b> ${agent.id}<br>
            <b>Role:</b> ${agent.role}<br>
            <b>Wallet:</b> $${agent.wallet.toFixed(2)}<br>
            <b>Action:</b> ${agent.action}
        `;

        if (!agents[agent.id]) {
            const marker = L.marker([agent.lat, agent.lon], {
                icon: createIcon(agent.role),
                zIndexOffset: agent.role === 'shop' ? -100 : 0
            }).bindTooltip(tooltipStr);

            const pathLine = L.polyline([], {
                color: agent.role === 'resident' ? '#60a5fa' : (agent.role === 'driver' ? '#f87171' : '#4ade80'),
                weight: 3,
                opacity: 0.4,
                dashArray: '5, 10',
                lineCap: 'round'
            });

            marker.addTo(map);
            pathLine.addTo(map);

            agents[agent.id] = {
                marker,
                pathLine,
                // If they have a path, head to the first node, else stay at current lat/lon
                fullPath: agent.path && agent.path.length > 0 ? agent.path : [[agent.lat, agent.lon]]
            };
        } else {
            const a = agents[agent.id];

            // Overwrite their goals with the new remaining path from the server
            if (agent.path && agent.path.length > 0) {
                // If the new path has changed, append it. We don't snap the marker to agent.lat.
                // This means the agent continuously walks towards the latest intended node.
                a.fullPath = agent.path;
            } else {
                a.fullPath = [[agent.lat, agent.lon]];
            }

            a.marker.setTooltipContent(tooltipStr);

            if (a.fullPath && a.fullPath.length > 0) {
                const currentPos = a.marker.getLatLng();
                const visualPath = [[currentPos.lat, currentPos.lng], ...a.fullPath];
                a.pathLine.setLatLngs(visualPath);
            } else {
                a.pathLine.setLatLngs([]);
            }
        }
    });

    Object.keys(agents).forEach(id => {
        if (!activeIds.has(id)) {
            map.removeLayer(agents[id].marker);
            map.removeLayer(agents[id].pathLine);
            delete agents[id];
        }
    });
}

let lastTime = performance.now();

// Animation loop to smoothly move marker along the full path
function animateMarkers(time) {
    let dt = (time - lastTime) / 1000.0;
    lastTime = time;
    if (dt > 0.5) dt = 0.5; // Cap dt for lag spikes

    if (isSimulationRunning) {
        Object.values(agents).forEach(a => {
            if (a.fullPath && a.fullPath.length > 0) {
                let target = a.fullPath[0];
                let currentPos = a.marker.getLatLng();

                let dx = target[0] - currentPos.lat;
                let dy = target[1] - currentPos.lng;
                let dist = Math.sqrt(dx * dx + dy * dy);

                let moveAmount = SPEED * dt;

                if (dist > 0.00001) {
                    if (dist < moveAmount) {
                        a.marker.setLatLng([target[0], target[1]]);
                        a.fullPath.shift();
                    } else {
                        a.marker.setLatLng([
                            currentPos.lat + (dx / dist) * moveAmount,
                            currentPos.lng + (dy / dist) * moveAmount
                        ]);
                    }
                } else if (dist <= 0.00001 && a.fullPath.length > 1) {
                    a.fullPath.shift();
                }
            }
        });
    }

    requestAnimationFrame(animateMarkers);
}

// Start the animation loop
requestAnimationFrame(animateMarkers);

async function fetchState() {
    try {
        const res = await fetch('/api/state');
        const data = await res.json();
        updateUI(data);
    } catch (err) {
        console.error("Failed to fetch state:", err);
    }
}

document.getElementById('toggle-btn').addEventListener('click', async () => {
    try {
        await fetch('/api/toggle', { method: 'POST' });
        fetchState();
    } catch (err) {
        console.error("Failed to toggle:", err);
    }
});

document.getElementById('city-select').addEventListener('change', async (e) => {
    try {
        const city = e.target.value;
        await fetch('/api/change-city', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ city })
        });

        // Let the normal polling pick up the loading state and clear out agents
        fetchState();

        // Re-center map slightly early to make the transition feel faster
        // The backend will also send the exact center of the new nodes later
        isFirstLoad = true;
    } catch (err) {
        console.error("Failed to change city:", err);
    }
});

setInterval(() => {
    fetchState();
}, POLL_INTERVAL_MS);

fetchState();
