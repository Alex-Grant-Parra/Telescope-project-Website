// Interface Controls JavaScript
// Toggle full screen mode
function toggleFullscreen() {
    let panel = document.getElementById("mainPanel");
    if (!document.fullscreenElement) {
        panel.requestFullscreen().catch(err => {
            alert(`Error attempting to enable full-screen mode: ${err.message} (${err.name})`);
        });
    } else {
        document.exitFullscreen();
    }
}

// Make the panels draggable
document.querySelectorAll(".draggable-panel").forEach(panel => {
    let header = panel.querySelector(".panel-header");
    header.addEventListener("mousedown", (event) => {
        let shiftX = event.clientX - panel.getBoundingClientRect().left;
        let shiftY = event.clientY - panel.getBoundingClientRect().top;

        function moveAt(pageX, pageY) {
            panel.style.left = pageX - shiftX + "px";
            panel.style.top = pageY - shiftY + "px";
        }

        function onMouseMove(event) {
            moveAt(event.pageX, event.pageY);
        }

        document.addEventListener("mousemove", onMouseMove);
        document.addEventListener("mouseup", () => {
            document.removeEventListener("mousemove", onMouseMove);
        }, { once: true });
    });
});

// Fetch camera choices and populate dropdowns
function populateCameraChoices() {
    fetch("/interface/get_camera_choices")
        .then(response => response.json())
        .then(data => {
            // Populate shutter speed
            let shutterSelect = document.getElementById("shutterSpeedSelect");
            shutterSelect.innerHTML = "";
            (data.shutterSpeed || []).forEach(choice => {
                let opt = document.createElement("option");
                opt.value = choice;
                opt.text = choice;
                shutterSelect.appendChild(opt);
            });

            // Populate ISO
            let isoSelect = document.getElementById("isoSelect");
            isoSelect.innerHTML = "";
            (data.iso || []).forEach(choice => {
                let opt = document.createElement("option");
                opt.value = choice;
                opt.text = choice;
                isoSelect.appendChild(opt);
            });
        })
        .catch(error => {
            console.error("Failed to fetch camera choices:", error);
        });
}

// Call on page load
document.addEventListener("DOMContentLoaded", function() {
    populateCameraChoices();
    loadTelescopes();
    loadSelectedTelescope();
});

// Update settings to backend
function updateSetting() {
    let data = {
        shutterSpeed: document.getElementById("shutterSpeedSelect").value,
        iso: document.getElementById("isoSelect").value,
        aperture: document.getElementById("apertureValue").innerText,
        whiteBalance: document.getElementById("whiteBalance").value,
        photoFormat: document.getElementById("photoFormat").value
    };
    fetch("/interface/update_camera", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
    }).then(response => response.json())
    .then(data => console.log("Response from server:", data))
    .catch(error => console.error("Fetch error:", error));
}

function takePhoto() {
    fetch("/interface/take_photo", {
        method: "POST"
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === "success") {
            alert("Photo taken and saved!");
        } else {
            alert("Failed to take photo: " + (data.message || "Unknown error"));
        }
    })
    .catch(error => {
        alert("Error taking photo: " + error);
    });
}

// Live View Toggle Logic
let liveViewActive = false;
function toggleLiveView() {
    console.log("Live view toggled");
    
    const btn = document.getElementById("liveViewToggleBtn");
    
    if (!btn) {
        console.error("Live view button not found! Make sure an element with ID 'liveViewToggleBtn' exists.");
        alert("Live view button not found in the page!");
        return;
    }
    
    // console.log("Button found, current liveViewActive state:", liveViewActive);
    
    if (liveViewActive) {
        // Stop live view
        console.log("Attempting to stop live view...");
        console.log("Making POST request to /interface/stop_live_view");
        fetch("/interface/stop_live_view", {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        })
        .then(response => {
            console.log("Stop live view response received:", response);
            return response.json();
        })
        .then(data => {
            console.log("Stop live view data:", data);
            if (data.status === "success") {
                liveViewActive = false;
                btn.textContent = "Start";
                btn.classList.remove("btn-outline-danger");
                btn.classList.add("btn-outline-primary");
                console.log("Live view stopped successfully");
            } else {
                console.error("Failed to stop live view:", data.message);
                alert("Error stopping live view: " + data.message);
            }
        })
        .catch(error => {
            console.error("Error stopping live view:", error);
            alert("Error stopping live view: " + error);
        });
    } else {
        // Start live view
        console.log("Attempting to start live view...");
        console.log("Making POST request to /interface/start_live_view");
        fetch("/interface/start_live_view", {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        })
        .then(response => {
            console.log("Start live view response received:", response);
            return response.json();
        })
        .then(data => {
            console.log("Start live view data:", data);
            if (data.status === "success") {
                liveViewActive = true;
                btn.textContent = "Stop";
                btn.classList.remove("btn-outline-primary");
                btn.classList.add("btn-outline-danger");
                console.log("Live view started successfully");
            } else {
                console.error("Failed to start live view:", data.message);
                alert("Error starting live view: " + data.message);
            }
        })
        .catch(error => {
            console.error("Error starting live view:", error);
            alert("Error starting live view: " + error);
        });
    }
}

function showStarInfo(star) {
    const existingModal = document.getElementById("starInfoModal");
    if (existingModal) existingModal.remove();

    const modal = document.createElement("div");
    modal.id = "starInfoModal";
    modal.style.position = "fixed";
    modal.style.top = "50%";
    modal.style.left = "50%";
    modal.style.transform = "translate(-50%, -50%)";
    modal.style.background = "black";
    modal.style.color = "white";
    modal.style.padding = "15px";
    modal.style.borderRadius = "8px";
    modal.style.zIndex = 1000;
    modal.style.maxWidth = "300px";
    modal.style.boxShadow = "0 0 10px #fff";

    modal.innerHTML = `
        <h2>${star.name || star.Name}</h2>
        <p><b>RA:</b> ${star.ra !== undefined ? star.ra : star.RA}°</p>
        <p><b>DEC:</b> ${star.dec !== undefined ? star.dec : star.DEC}°</p>
        <p><b>Magnitude:</b> ${star.mag !== undefined ? star.mag : star["V-Mag"]}</p>
        <button id="trackStarBtn" class="btn btn-success">Track</button>
        <button id="closeStarInfo" class="btn btn-secondary ms-2">Close</button>
    `;

    document.body.appendChild(modal);

    document.getElementById("closeStarInfo").addEventListener("click", () => {
        modal.remove();
    });

    document.getElementById("trackStarBtn").addEventListener("click", () => {
        // Send tracking request to backend
        fetch("/track_star", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                name: star.name || star.Name,
                ra: star.ra !== undefined ? star.ra : star.RA,
                dec: star.dec !== undefined ? star.dec : star.DEC,
                mag: star.mag !== undefined ? star.mag : star["V-Mag"]
            })
        })
        .then(response => response.json())
        .then(data => {
            // alert("Tracking started!");
            modal.remove();
        })
        .catch(error => {
            // alert("Failed to start tracking.");
            console.error(error);
        });
    });
}

function searchObject() {
    let searchValue = document.getElementById("searchObject").value;
    if (searchValue) {
        fetch("/interface/search_object", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ searchValue: searchValue })
        }).then(response => response.json())
        .then(data => {
            if (data.status === "success" && data.data) {
                showStarInfo(data.data);
            } else {
                alert(data.message || "Object not found.");
            }
        })
        .catch(error => console.error("Fetch error:", error));
    } else {
        alert("Please enter a valid HD, NGC, or IC number.");
    }
}

// Telescope selection functions
function loadTelescopes() {
    fetch("/interface/get_telescopes")
        .then(response => response.json())
        .then(data => {
            if (data.status === "success") {
                populateTelescopeDropdown(data.telescopes);
            } else {
                console.error("Failed to load telescopes:", data.message);
            }
        })
        .catch(error => {
            console.error("Error loading telescopes:", error);
        });
}

function populateTelescopeDropdown(telescopes) {
    const select = document.getElementById("telescopeSelect");
    select.innerHTML = '<option value="">Select a telescope...</option>';
    
    telescopes.forEach(telescope => {
        const option = document.createElement("option");
        option.value = telescope.telescopeId;
        option.text = `${telescope.telescopeId} (${telescope.online ? 'Online' : 'Offline'})`;
        option.dataset.telescope = JSON.stringify(telescope);
        select.appendChild(option);
    });
}

function selectTelescope() {
    const select = document.getElementById("telescopeSelect");
    const selectedValue = select.value;
    
    if (!selectedValue) {
        document.getElementById("telescopeInfo").style.display = "none";
        return;
    }
    
    const selectedOption = select.options[select.selectedIndex];
    const telescope = JSON.parse(selectedOption.dataset.telescope);
    
    // Update UI with telescope info
    document.getElementById("telescopeId").textContent = telescope.telescopeId;
    document.getElementById("telescopeIp").textContent = telescope.ipAddress;
    document.getElementById("telescopeVersion").textContent = telescope.firmwareVersion;
    document.getElementById("telescopeStatus").textContent = telescope.online ? 'Online' : 'Offline';
    document.getElementById("telescopeStatus").className = telescope.online ? 'text-success' : 'text-danger';
    document.getElementById("telescopeInfo").style.display = "block";
    
    // Send selection to backend
    fetch("/interface/select_telescope", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ telescopeId: selectedValue })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === "success") {
            console.log("Telescope selected:", data.message);
        } else {
            alert("Failed to select telescope: " + data.message);
        }
    })
    .catch(error => {
        console.error("Error selecting telescope:", error);
        alert("Error selecting telescope");
    });
}

function refreshTelescopes() {
    loadTelescopes();
}

function loadSelectedTelescope() {
    fetch("/interface/get_selected_telescope")
        .then(response => response.json())
        .then(data => {
            if (data.status === "success" && data.telescope) {
                // Set the dropdown to show the selected telescope
                const select = document.getElementById("telescopeSelect");
                for (let i = 0; i < select.options.length; i++) {
                    if (select.options[i].value === data.telescope.telescopeId) {
                        select.selectedIndex = i;
                        selectTelescope(); // Update the info panel
                        break;
                    }
                }
            }
        })
        .catch(error => {
            console.error("Error loading selected telescope:", error);
        });
}