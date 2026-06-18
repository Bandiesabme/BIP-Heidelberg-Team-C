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

            // Helper function to update UI without freezing the labels
            const syncSlider = (sliderId, labelId, serverValue, formatFn) => {
                const slider = document.getElementById(sliderId);
                const label = document.getElementById(labelId);
                if (!slider || !label || serverValue === undefined) return;

                if (document.activeElement === slider) {
                    // While user is dragging, show the local slider value instantly
                    label.innerText = formatFn ? formatFn(slider.value) : slider.value;
                } else {
                    // When not dragging, sync both the slider and label to the server's truth
                    slider.value = serverValue;
                    label.innerText = formatFn ? formatFn(serverValue) : serverValue;
                }
            };

            // Sync all sliders dynamically
            syncSlider('speed-slider', 'speed-limit-val', data.target_speed);
            syncSlider('max-angle-slider', 'max-angle-val', data.max_steering_angle, v => v + '°');
            syncSlider('turn-frames-slider', 'turn-frames-val', data.turn_frames);
            syncSlider('white-thresh-slider', 'white-thresh-val', data.white_thresh);
            syncSlider('roi-slider', 'roi-ratio-val', data.roi_top_ratio);
            syncSlider('follow-offset-slider', 'follow-offset-val', data.follow_offset, v => Math.round(v));
            syncSlider('stop-trigger-slider', 'stop-trigger-val', data.stop_trigger_frac, v => Number(v).toFixed(2));
            syncSlider('cam-pan-slider', 'cam-pan-val', data.camera_pan, v => v + '°');
            syncSlider('cam-tilt-slider', 'cam-tilt-val', data.camera_tilt, v => v + '°');
            
            // HSV sync
            syncSlider('blue-h-min-slider', 'blue-h-min-val', data.blue_h_min);
            syncSlider('blue-h-max-slider', 'blue-h-max-val', data.blue_h_max);
            syncSlider('sign-s-min-slider', 'sign-s-min-val', data.sign_s_min);
            syncSlider('sign-v-min-slider', 'sign-v-min-val', data.sign_v_min);
            
        })
        .catch(err => console.error("Telemetry fetch error:", err));
}, 300);