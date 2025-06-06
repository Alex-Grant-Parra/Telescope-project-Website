$distroName = "Ubuntu-24.04"

# Start WSL distro in background, detach the process
Start-Process wsl -ArgumentList "-d $distroName -u root --exec bash -c 'nohup bash >/dev/null 2>&1 &' " -WindowStyle Hidden

# Wait a few seconds for it to start
Start-Sleep -Seconds 3

# Get the list of USB devices from usbipd
$usbipdOutput = usbipd list

# Find all device lines matching Canon EOS 5D Mark II
$deviceLines = $usbipdOutput | Where-Object { $_ -match "Canon EOS 5D Mark II" }

if (-not $deviceLines) {
    Write-Output "Canon EOS 5D Mark II not found."
    exit 1
}

# Check if there is any device Not attached
$notAttachedDevice = $deviceLines | Where-Object { $_ -match "Not attached" }

if (-not $notAttachedDevice) {
    Write-Output "Canon EOS 5D Mark II is already attached."
    exit 1
}

# Extract the busid (first whitespace-separated token) from the first not attached device
$busid = ($notAttachedDevice[0] -split '\s+')[0]

# Attach the device to WSL using the correct busid
usbipd attach --busid $busid --wsl $distroName
