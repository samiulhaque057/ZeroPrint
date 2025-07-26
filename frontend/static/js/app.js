// Populate EcoScore
const ecoScore = 82; // Placeholder value
document.getElementById('ecoScore').textContent = ecoScore;

// Render emission trends chart (using Chart.js if available)
// For now, just draw a simple bar using canvas API as a placeholder
const canvas = document.getElementById('emissionTrends');
if (canvas && canvas.getContext) {
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#1a73e8';
    ctx.fillRect(50, 100, 50, -60); // Example bar
    ctx.fillRect(150, 100, 50, -40);
    ctx.fillRect(250, 100, 50, -80);
    ctx.fillRect(350, 100, 50, -30);
    ctx.fillStyle = '#222';
    ctx.font = '14px Arial';
    ctx.fillText('Apr', 55, 120);
    ctx.fillText('May', 155, 120);
    ctx.fillText('Jun', 255, 120);
    ctx.fillText('Jul', 355, 120);
}

// Populate leaderboard with mock data
const leaderboard = [
    { name: 'Alice', score: 95 },
    { name: 'Bob', score: 90 },
    { name: 'Charlie', score: 88 },
    { name: 'You', score: ecoScore },
];
const leaderboardList = document.getElementById('leaderboardList');
leaderboard.forEach(user => {
    const li = document.createElement('li');
    li.textContent = `${user.name}: EcoScore ${user.score}`;
    leaderboardList.appendChild(li);
}); 