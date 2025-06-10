// Chart.js Configuration for Centralized Logging Dashboard

// Global chart variables
let ingestionChart = null;
let sourcesChart = null;

// Chart.js default configuration (only if Chart.js is available)
if (typeof Chart !== 'undefined') {
    Chart.defaults.font.family = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif";
    Chart.defaults.font.size = 12;
    Chart.defaults.color = '#6c757d';
}

// Initialize ingestion chart
function initializeIngestionChart() {
    const ctx = document.getElementById('ingestionChart');
    if (!ctx) return;

    ingestionChart = new Chart(ctx.getContext('2d'), {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Logs per Minute',
                data: [],
                borderColor: '#0d6efd',
                backgroundColor: 'rgba(13, 110, 253, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                }
            },
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Time'
                    }
                },
                y: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Logs/min'
                    },
                    beginAtZero: true
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            }
        }
    });

    // Initialize with sample data
    updateIngestionChart('1h');
}

// Initialize sources chart
function initializeSourcesChart() {
    const ctx = document.getElementById('sourcesChart');
    if (!ctx) return;

    sourcesChart = new Chart(ctx.getContext('2d'), {
        type: 'doughnut',
        data: {
            labels: ['ssdev', 'sslog', 'ssdvr', 'ssmcp', 'ssrun'],
            datasets: [{
                data: [40, 25, 15, 10, 10],
                backgroundColor: [
                    '#0d6efd',
                    '#198754',
                    '#ffc107',
                    '#dc3545',
                    '#6f42c1'
                ],
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 20,
                        usePointStyle: true
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((value / total) * 100).toFixed(1);
                            return `${label}: ${value} logs (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });
}

// Update ingestion chart with time range
function updateIngestionChart(timeRange) {
    if (!ingestionChart) return;

    // Generate sample data based on time range
    const now = new Date();
    const labels = [];
    const data = [];
    
    let intervals, stepMinutes;
    
    switch(timeRange) {
        case '1h':
            intervals = 12;
            stepMinutes = 5;
            break;
        case '6h':
            intervals = 12;
            stepMinutes = 30;
            break;
        case '24h':
            intervals = 24;
            stepMinutes = 60;
            break;
        default:
            intervals = 12;
            stepMinutes = 5;
    }

    for (let i = intervals; i >= 0; i--) {
        const time = new Date(now.getTime() - (i * stepMinutes * 60000));
        labels.push(time.toLocaleTimeString('en-US', { 
            hour: '2-digit', 
            minute: '2-digit' 
        }));
        
        // Generate realistic sample data
        const baseRate = 15;
        const variation = Math.random() * 10 - 5;
        data.push(Math.max(0, baseRate + variation));
    }

    ingestionChart.data.labels = labels;
    ingestionChart.data.datasets[0].data = data;
    ingestionChart.update();
}

// Update sources chart with real data
function updateSourcesChart(sourcesData) {
    if (!sourcesChart || !sourcesData) return;

    const labels = Object.keys(sourcesData);
    const data = Object.values(sourcesData);
    
    sourcesChart.data.labels = labels;
    sourcesChart.data.datasets[0].data = data;
    sourcesChart.update();
}

// Update chart data with real-time information
function updateChartData(logData) {
    // This function can be called when new log data arrives
    // to update charts in real-time
    if (ingestionChart) {
        // Add new data point and remove old ones
        const now = new Date();
        const timeLabel = now.toLocaleTimeString('en-US', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
        
        ingestionChart.data.labels.push(timeLabel);
        ingestionChart.data.datasets[0].data.push(1); // Increment for new log
        
        // Keep only last 12 data points
        if (ingestionChart.data.labels.length > 12) {
            ingestionChart.data.labels.shift();
            ingestionChart.data.datasets[0].data.shift();
        }
        
        ingestionChart.update('none'); // No animation for real-time updates
    }
}

// Utility function to format chart tooltips
function formatChartTooltip(tooltipItem) {
    const value = tooltipItem.parsed.y || tooltipItem.parsed;
    return `${tooltipItem.label}: ${value.toFixed(1)}`;
}

// Export functions for global use
window.chartConfig = {
    initializeIngestionChart,
    initializeSourcesChart,
    updateIngestionChart,
    updateSourcesChart,
    updateChartData,
    formatChartTooltip
};
