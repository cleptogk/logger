// Centralized Logging Dashboard JavaScript

// Global variables
let socket = null;
let charts = {};
let settings = {
    refreshInterval: 300,  // 5 minutes
    maxLogEntries: 100,
    autoRefresh: true,
    soundAlerts: false
};

// Initialize dashboard
$(document).ready(function() {
    initializeSocket();
    loadSettings();
    setupEventListeners();
    showConnectionStatus('connecting');
});

// Socket.IO Connection
function initializeSocket() {
    socket = io();
    
    socket.on('connect', function() {
        console.log('Connected to logging server');
        showConnectionStatus('connected');
        showNotification('Connected to logging server', 'success');
    });
    
    socket.on('disconnect', function() {
        console.log('Disconnected from logging server');
        showConnectionStatus('disconnected');
        showNotification('Disconnected from logging server', 'warning');
    });
    
    socket.on('log_update', function(data) {
        handleLogUpdate(data);
    });
    
    socket.on('metrics_update', function(data) {
        handleMetricsUpdate(data);
    });
    
    socket.on('status', function(data) {
        console.log('Server status:', data.message);
    });
    
    socket.on('subscription_confirmed', function(data) {
        console.log('Subscription confirmed:', data);
    });
}

// Connection Status
function showConnectionStatus(status) {
    const statusIcon = $('#connection-status');
    const statusText = $('#connection-text');
    
    statusIcon.removeClass('text-success text-warning text-danger');
    
    switch(status) {
        case 'connected':
            statusIcon.addClass('text-success');
            statusText.text('Connected');
            break;
        case 'connecting':
            statusIcon.addClass('text-warning');
            statusText.text('Connecting...');
            break;
        case 'disconnected':
            statusIcon.addClass('text-danger');
            statusText.text('Disconnected');
            break;
    }
}

// Event Listeners
function setupEventListeners() {
    // Settings form
    $('#settingsForm').on('submit', function(e) {
        e.preventDefault();
        saveSettings();
    });
    
    // Auto-refresh toggle
    $('#autoRefresh').on('change', function() {
        settings.autoRefresh = $(this).is(':checked');
        saveSettings();
    });
    
    // Refresh interval change
    $('#refreshInterval').on('change', function() {
        settings.refreshInterval = parseInt($(this).val());
        saveSettings();
    });
}

// Settings Management
function loadSettings() {
    const savedSettings = localStorage.getItem('loggingDashboardSettings');
    if (savedSettings) {
        settings = { ...settings, ...JSON.parse(savedSettings) };
    }
    
    // Apply settings to form
    $('#refreshInterval').val(settings.refreshInterval);
    $('#maxLogEntries').val(settings.maxLogEntries);
    $('#autoRefresh').prop('checked', settings.autoRefresh);
    $('#soundAlerts').prop('checked', settings.soundAlerts);
}

function saveSettings() {
    // Get values from form
    settings.refreshInterval = parseInt($('#refreshInterval').val());
    settings.maxLogEntries = parseInt($('#maxLogEntries').val());
    settings.autoRefresh = $('#autoRefresh').is(':checked');
    settings.soundAlerts = $('#soundAlerts').is(':checked');
    
    // Save to localStorage
    localStorage.setItem('loggingDashboardSettings', JSON.stringify(settings));
    
    // Close modal
    $('#settingsModal').modal('hide');
    
    showNotification('Settings saved successfully', 'success');
}

// Log Updates
function handleLogUpdate(logData) {
    // Update real-time log displays
    if (typeof updateLogViewer === 'function') {
        updateLogViewer(logData);
    }
    
    // Play sound alert for errors if enabled
    if (settings.soundAlerts && (logData.level === 'error' || logData.level === 'critical')) {
        playAlertSound();
    }
    
    // Update charts if on dashboard
    if (typeof updateChartData === 'function') {
        updateChartData(logData);
    }
}

// Metrics Updates
function handleMetricsUpdate(metricsData) {
    // Update dashboard metrics
    if (typeof updateDashboardMetrics === 'function') {
        updateDashboardMetrics(metricsData);
    }
}

// Notifications
function showNotification(message, type = 'info', duration = 3000) {
    const alertClass = `alert-${type}`;
    const iconClass = type === 'success' ? 'fa-check-circle' : 
                     type === 'warning' ? 'fa-exclamation-triangle' : 
                     type === 'danger' ? 'fa-times-circle' : 'fa-info-circle';
    
    const notification = $(`
        <div class="alert ${alertClass} alert-dismissible fade show position-fixed" 
             style="top: 20px; right: 20px; z-index: 9999; min-width: 300px;">
            <i class="fas ${iconClass} me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `);
    
    $('body').append(notification);
    
    // Auto-dismiss after duration
    setTimeout(function() {
        notification.alert('close');
    }, duration);
}

function showError(message) {
    showNotification(message, 'danger', 5000);
}

function showSuccess(message) {
    showNotification(message, 'success');
}

// Sound Alerts
function playAlertSound() {
    if (settings.soundAlerts) {
        // Create audio context for alert sound
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        oscillator.frequency.value = 800;
        oscillator.type = 'sine';
        
        gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
        
        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.5);
    }
}

// Utility Functions
function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString();
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDuration(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
        return `${hours}h ${minutes}m ${secs}s`;
    } else if (minutes > 0) {
        return `${minutes}m ${secs}s`;
    } else {
        return `${secs}s`;
    }
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// API Helpers
function apiGet(endpoint, params = {}) {
    return $.get(endpoint, params)
        .fail(function(xhr) {
            const message = xhr.responseJSON?.error || 'API request failed';
            showError(message);
        });
}

function apiPost(endpoint, data = {}) {
    return $.post(endpoint, data)
        .fail(function(xhr) {
            const message = xhr.responseJSON?.error || 'API request failed';
            showError(message);
        });
}

// Export functions for use in other scripts
window.dashboard = {
    showNotification,
    showError,
    showSuccess,
    formatTimestamp,
    formatBytes,
    formatDuration,
    apiGet,
    apiPost,
    settings,
    socket
};
