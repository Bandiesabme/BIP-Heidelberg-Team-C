// --- Control Functions (Sent to backend) ---

function updateParam(param, value) {
    fetch(`/api/set?${param}=${value}`)
        .catch(err => console.error("Error setting parameter:", err));
}

function toggleAutodrive(enabled) {
    const val = enabled ? 1 : 0;
    fetch(`/api/set?autodrive=${val}`)
        .catch(err => console.error("Error toggling autodrive:", err));
}

function emergencyStop() {
    // Uncheck the UI toggle
    const check = document.getElementById('autodrive-checkbox');
    if (check) check.checked = false;
    
    // Send stop command
    toggleAutodrive(false);
    console.log("EMERGENCY STOP TRIGGERED");
}

// Spacebar listener for Emergency Stop
document.addEventListener('keydown', (event) => {
    if (event.code === 'Space') {
        event.preventDefault(); // Prevent page from scrolling down
        emergencyStop();
    }
});

// --- Telemetry Polling (Receives from backend) ---

setInterval(() => {
    fetch('/api/status')
        .then(res => res.json())
        .then(data => {
            const check = document.getElementById('autodrive-checkbox');
            if (check.checked !== data.autodrive_enabled) {
                check.checked = data.autodrive_enabled;
                const label = document.getElementById('mode-label');
                label.innerText = data.autodrive_enabled ? 'AUTODRIVE ON' : 'AUTODRIVE OFF';
                label.style.color = data.autodrive_enabled ? 'var(--success)' : 'var(--text-muted)';
            }

            const laneDot = document.getElementById('lane-dot');
            const laneText = document.getElementById('lane-text');
            if (data.lane_found) {
                laneDot.className = "status-dot status-active";
                laneText.innerText = "Locked";
                laneText.style.color = "var(--success)";
            } else {
                laneDot.className = "status-dot status-inactive";
                laneText.innerText = "Lost";
                laneText.style.color = "var(--danger)";
            }

            document.getElementById('speed-value').innerText = data.motor_speed;
            document.getElementById('angle-value').innerText = data.steering_angle.toFixed(1) + '°';
            
            const errorVal = data.steering_error;
            document.getElementById('error-value').innerText = errorVal.toFixed(2);

            const wheel = document.getElementById('wheel-svg');
            const rotation = data.steering_angle * 3;
            wheel.style.transform = `rotate(${rotation}deg)`;

            const bar = document.getElementById('deviation-bar');
            const sideLabel = document.getElementById('offset-side');
            if (errorVal >= 0) {
                bar.style.left = '50%';
                bar.style.width = (errorVal * 50) + '%';
                bar.style.background = 'var(--accent)';
                sideLabel.innerText = errorVal > 0.05 ? 'Offset Right' : 'Centered';
            } else {
                const pct = Math.abs(errorVal) * 50;
                bar.style.left = (50 - pct) + '%';
                bar.style.width = pct + '%';
                bar.style.background = 'var(--primary)';
                sideLabel.innerText = errorVal < -0.05 ? 'Offset Left' : 'Centered';
            }

            // Update sign detected telemetry
            const signEl = document.getElementById('sign-detected');
            const signText = data.last_sign ? data.last_sign.toUpperCase() : 'NONE';
            signEl.innerText = signText;
            
            if (data.last_sign === 'stop') signEl.style.color = 'var(--danger)';
            else if (data.last_sign) signEl.style.color = 'var(--accent)';
            else signEl.style.color = 'var(--text-main)';

            // Sync sliders
            if (document.activeElement !== document.getElementById('speed-slider')) {
                document.getElementById('speed-slider').value = data.target_speed;
                document.getElementById('speed-limit-val').innerText = data.target_speed;
            }
            if (document.activeElement !== document.getElementById('max-angle-slider')) {
                document.getElementById('max-angle-slider').value = data.max_steering_angle;
                document.getElementById('max-angle-val').innerText = data.max_steering_angle + '°';
            }
            if (data.turn_frames !== undefined && document.activeElement !== document.getElementById('turn-frames-slider')) {
                document.getElementById('turn-frames-slider').value = data.turn_frames;
                document.getElementById('turn-frames-val').innerText = data.turn_frames;
            }
            if (document.activeElement !== document.getElementById('white-thresh-slider')) {
                document.getElementById('white-thresh-slider').value = data.white_thresh;
                document.getElementById('white-thresh-val').innerText = data.white_thresh;
            }
            if (document.activeElement !== document.getElementById('roi-slider')) {
                document.getElementById('roi-slider').value = data.roi_top_ratio;
                document.getElementById('roi-ratio-val').innerText = data.roi_top_ratio;
            }
            if (data.follow_offset !== undefined && document.activeElement !== document.getElementById('follow-offset-slider')) {
                document.getElementById('follow-offset-slider').value = Math.round(data.follow_offset);
                document.getElementById('follow-offset-val').innerText = Math.round(data.follow_offset);
            }
            if (data.stop_trigger_frac !== undefined && document.activeElement !== document.getElementById('stop-trigger-slider')) {
                document.getElementById('stop-trigger-slider').value = data.stop_trigger_frac;
                document.getElementById('stop-trigger-val').innerText = data.stop_trigger_frac.toFixed(2);
            }
            if (document.activeElement !== document.getElementById('cam-pan-slider')) {
                document.getElementById('cam-pan-slider').value = data.camera_pan;
                document.getElementById('cam-pan-val').innerText = data.camera_pan + '°';
            }
            if (document.activeElement !== document.getElementById('cam-tilt-slider')) {
                document.getElementById('cam-tilt-slider').value = data.camera_tilt;
                document.getElementById('cam-tilt-val').innerText = data.camera_tilt + '°';
            }
            // HSV sync
            if (data.blue_h_min !== undefined && document.activeElement !== document.getElementById('blue-h-min-slider')) {
                document.getElementById('blue-h-min-slider').value = data.blue_h_min;
                document.getElementById('blue-h-min-val').innerText = data.blue_h_min;
            }
            if (data.blue_h_max !== undefined && document.activeElement !== document.getElementById('blue-h-max-slider')) {
                document.getElementById('blue-h-max-slider').value = data.blue_h_max;
                document.getElementById('blue-h-max-val').innerText = data.blue_h_max;
            }
            if (data.sign_s_min !== undefined && document.activeElement !== document.getElementById('sign-s-min-slider')) {
                document.getElementById('sign-s-min-slider').value = data.sign_s_min;
                document.getElementById('sign-s-min-val').innerText = data.sign_s_min;
            }
            if (data.sign_v_min !== undefined && document.activeElement !== document.getElementById('sign-v-min-slider')) {
                document.getElementById('sign-v-min-slider').value = data.sign_v_min;
                document.getElementById('sign-v-min-val').innerText = data.sign_v_min;
            }
        })
        .catch(err => console.error("Telemetry fetch error:", err));
}, 300);