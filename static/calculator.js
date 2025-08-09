class CarbonFootprintCalculator {
    constructor() {
        this.transportData = {
            bus: { distance: 0, emission: 0.12 }, // kg CO2 per km
            car: { distance: 0, emission: 0.21 },
            bike: { distance: 0, emission: 0.075 },
            cycle: { distance: 0, emission: 0 },
            walking: { distance: 0, emission: 0 }
        };
        
        this.init();
    }

    init() {
        console.log('Initializing calculator...');
        this.setupSliders();
        this.setupResetButton();
        this.setupEmissionsButton();
        this.updateCalculations();
        console.log('Calculator initialization complete');
    }

    setupSliders() {
        const sliders = document.querySelectorAll('.slider');
        sliders.forEach(slider => {
            slider.addEventListener('input', (e) => {
                const transport = e.target.dataset.transport;
                const value = parseFloat(e.target.value);
                
                this.transportData[transport].distance = value;
                this.updateTransportValue(transport, value);
                this.updateCalculations();
            });
        });
    }

    setupResetButton() {
        const resetBtn = document.getElementById('reset-btn');
        resetBtn.addEventListener('click', () => {
            this.resetCalculator();
        });
    }

    setupEmissionsButton() {
        const emissionsBtn = document.querySelector('.emissions-btn');
        console.log('Looking for emissions button:', emissionsBtn);
        
        if (emissionsBtn) {
            emissionsBtn.addEventListener('click', () => {
                console.log('Emissions button clicked!');
                this.generateTailoredTips();
            });
            
            // Also add a mouseover event to test
            emissionsBtn.addEventListener('mouseover', () => {
                console.log('Mouse over emissions button');
            });
        } else {
            console.error('Emissions button not found!');
        }
    }

    async generateTailoredTips() {
        console.log('generateTailoredTips called');
        console.log('Current transport data:', this.transportData);
        
        // Show loading state
        const tipsSection = document.querySelector('.tips-section');
        
        console.log('Tips section found:', tipsSection);
        
        // Clear ALL existing content in the tips section except the title and description
        const tipsTitle = tipsSection.querySelector('h4');
        const tipsDescription = tipsSection.querySelector('p');
        
        // Remove all content after the description
        let nextElement = tipsDescription.nextElementSibling;
        while (nextElement) {
            const toRemove = nextElement;
            nextElement = nextElement.nextElementSibling;
            toRemove.remove();
        }
        
        // Create loading element
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'tips-loading';
        loadingDiv.innerHTML = `
            <div class="loading-spinner"></div>
            <p>Generating tailored tips based on your transport data...</p>
        `;
        
        // Insert loading element after the tips description
        tipsDescription.insertAdjacentElement('afterend', loadingDiv);

        try {
            // Prepare transport data for the API
            const transportData = {
                bus: this.transportData.bus.distance,
                car: this.transportData.car.distance,
                bike: this.transportData.bike.distance,
                cycle: this.transportData.cycle.distance,
                walking: this.transportData.walking.distance,
                totalDistance: Object.values(this.transportData).reduce((sum, data) => sum + data.distance, 0),
                totalEmission: Object.entries(this.transportData).reduce((sum, [transport, data]) => sum + (data.distance * data.emission), 0)
            };

            console.log('Sending transport data:', transportData);

            // Call the API with transport data
            const response = await fetch('/api/tailored-tips', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(transportData)
            });

            console.log('API response status:', response.status);
            const data = await response.json();
            console.log('API response data:', data);
            
            // Remove loading element
            loadingDiv.remove();

            if (data.tips && data.tips.length > 0) {
                // Create new tips content
                const newTipsContent = document.createElement('div');
                newTipsContent.className = 'tips-content';
                newTipsContent.style.display = 'block';
                
                const tipsList = document.createElement('ul');
                tipsList.className = 'tips-list';
                
                // Only add the first 5 tips
                const tipsToShow = data.tips.slice(0, 5);
                
                tipsToShow.forEach(tip => {
                    const li = document.createElement('li');
                    li.textContent = tip;
                    tipsList.appendChild(li);
                });
                
                newTipsContent.appendChild(tipsList);
                
                // Add new content after the tips description
                tipsDescription.insertAdjacentElement('afterend', newTipsContent);
            } else {
                // Show error message
                const errorDiv = document.createElement('div');
                errorDiv.className = 'tips-error';
                errorDiv.style.display = 'block';
                errorDiv.innerHTML = '<p style="color: #6b7280; font-style: italic; margin-top: 1rem;">Unable to generate tailored tips. Please try again.</p>';
                
                tipsDescription.insertAdjacentElement('afterend', errorDiv);
            }
        } catch (error) {
            console.error('Error generating tailored tips:', error);
            
            // Remove loading element
            loadingDiv.remove();
            
            // Show error message
            const errorDiv = document.createElement('div');
            errorDiv.className = 'tips-error';
            errorDiv.style.display = 'block';
            errorDiv.innerHTML = '<p style="color: #6b7280; font-style: italic; margin-top: 1rem;">Error generating tailored tips. Please try again.</p>';
            
            tipsDescription.insertAdjacentElement('afterend', errorDiv);
        }
    }

    updateTransportValue(transport, value) {
        const valueElement = document.getElementById(`${transport}-value`);
        valueElement.textContent = `${value} km`;
    }

    updateCalculations() {
        this.updateTotalDistance();
        this.updateEmissions();
        this.updateBarChart();
        this.updateProgressCircle();
        this.updateAchievement();
    }

    updateTotalDistance() {
        const totalDistance = Object.values(this.transportData)
            .reduce((sum, data) => sum + data.distance, 0);
        
        document.getElementById('total-distance').textContent = `${totalDistance.toFixed(0)} km`;
    }

    updateEmissions() {
        let totalEmission = 0;
        let totalSaved = 0;

        Object.entries(this.transportData).forEach(([transport, data]) => {
            const emission = data.distance * data.emission;
            totalEmission += emission;
            
            // Calculate potential savings (compared to car travel)
            if (transport !== 'car') {
                const carEmission = data.distance * 0.21;
                const saved = Math.max(0, carEmission - emission);
                totalSaved += saved;
            }
            
            // Update bar chart values
            const barValue = document.getElementById(`${transport}-emission`);
            if (barValue) {
                barValue.textContent = emission.toFixed(1);
            }
        });

        document.getElementById('total-emission').textContent = `${totalEmission.toFixed(1)} kg`;
        document.getElementById('co2-saved').textContent = `${totalSaved.toFixed(1)} kg`;
    }

    updateBarChart() {
        const maxEmission = Math.max(...Object.entries(this.transportData)
            .map(([transport, data]) => data.distance * data.emission));

        Object.entries(this.transportData).forEach(([transport, data]) => {
            const emission = data.distance * data.emission;
            const percentage = maxEmission > 0 ? (emission / maxEmission) * 100 : 0;
            
            const bar = document.getElementById(`${transport}-bar`);
            if (bar) {
                bar.style.height = `${Math.max(percentage, 5)}%`;
            }
        });
    }

    updateProgressCircle() {
        const totalDistance = Object.values(this.transportData)
            .reduce((sum, data) => sum + data.distance, 0);
        
        const maxDistance = 500; // Assuming max distance for progress calculation
        const percentage = Math.min((totalDistance / maxDistance) * 100, 100);
        
        const circle = document.getElementById('progress-circle');
        const circumference = 2 * Math.PI * 100; // radius = 100 (updated from 80)
        const offset = circumference - (percentage / 100) * circumference;
        
        circle.style.strokeDashoffset = offset;
    }

    updateAchievement() {
        const zeroEmissionDistance = this.transportData.cycle.distance + 
                                   this.transportData.walking.distance;
        const totalDistance = Object.values(this.transportData)
            .reduce((sum, data) => sum + data.distance, 0);
        
        const zeroEmissionPercentage = totalDistance > 0 ? 
            (zeroEmissionDistance / totalDistance) * 100 : 0;
        
        const achievementText = document.querySelector('.achievement-text');
        const achievementDiv = document.querySelector('.achievement');
        
        if (zeroEmissionPercentage >= 50) {
            achievementText.textContent = 'Outstanding! Over 50% of your travel is zero-emission.';
            achievementDiv.style.background = '#d4edda';
        } else if (zeroEmissionPercentage >= 25) {
            achievementText.textContent = 'Good progress! 25% of your travel is zero-emission.';
            achievementDiv.style.background = '#fff3cd';
        } else {
            achievementText.textContent = 'Try to increase zero-emission transportation for better impact.';
            achievementDiv.style.background = '#f8d7da';
        }
    }

    resetCalculator() {
        // Reset to zero values
        this.transportData = {
            bus: { distance: 0, emission: 0.12 },
            car: { distance: 0, emission: 0.21 },
            bike: { distance: 0, emission: 0.075 },
            cycle: { distance: 0, emission: 0 },
            walking: { distance: 0, emission: 0 }
        };

        // Reset sliders to zero
        Object.entries(this.transportData).forEach(([transport, data]) => {
            const slider = document.getElementById(`${transport}-slider`);
            if (slider) {
                slider.value = 0;
            }
            this.updateTransportValue(transport, 0);
        });

        // Update all calculations
        this.updateCalculations();
    }
}

// Initialize the calculator when the page loads
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing calculator...');
    const calculator = new CarbonFootprintCalculator();
    console.log('Calculator initialized:', calculator);
    
    // Test direct button click
    setTimeout(() => {
        const testBtn = document.querySelector('.emissions-btn');
        console.log('Direct test - button found:', testBtn);
        if (testBtn) {
            testBtn.addEventListener('click', () => {
                console.log('Direct click test - button clicked!');
            });
        }
    }, 1000);
});

// Add some interactive animations
document.addEventListener('DOMContentLoaded', () => {
    // Animate bars on load
    setTimeout(() => {
        const bars = document.querySelectorAll('.bar');
        bars.forEach(bar => {
            bar.style.transition = 'height 0.8s ease-in-out';
        });
    }, 500);

    // Add hover effects to transport items
    const transportItems = document.querySelectorAll('.transport-item');
    transportItems.forEach(item => {
        item.addEventListener('mouseenter', () => {
            item.style.transform = 'translateX(5px)';
            item.style.transition = 'transform 0.2s ease';
        });
        
        item.addEventListener('mouseleave', () => {
            item.style.transform = 'translateX(0)';
        });
    });
});