// Learning Page JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize the page
    initializeLearningPage();
    // Pagination state
    window.__NEWS_STATE__ = { allItems: [], page: 0, pageSize: 9, filteredCategory: 'all', loading: false, reachedEnd: false };
    // Initial fetch
    fetchLiveNews(true);
    // Infinite scroll
    setupInfiniteScroll();
    // Ensure the page starts at the top and disable automatic restoration
    if ('scrollRestoration' in history) {
        history.scrollRestoration = 'manual';
    }
    window.scrollTo({ top: 0, behavior: 'auto' });
});

function initializeLearningPage() {
    // Category filtering removed
    
    // Set up interactive elements
    setupInteractiveElements();
    
    // Set up newsletter signup
    setupNewsletterSignup();
    
    // Add smooth scrolling for better UX
    setupSmoothScrolling();
}

function setupCategoryFiltering() {
    const categoryButtons = document.querySelectorAll('.category-btn');
    const state = window.__NEWS_STATE__ || { filteredCategory: 'all' };
    categoryButtons.forEach(button => {
        button.addEventListener('click', function() {
            const selectedCategory = this.getAttribute('data-category');
            categoryButtons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
            state.filteredCategory = selectedCategory;
            state.page = 0;
            state.reachedEnd = false;
            renderNextPage();
        });
    });
}

function filterNewsCards(category, newsCards) {
    newsCards.forEach(card => {
        const cardCategory = card.getAttribute('data-category');
        
        if (category === 'all' || cardCategory === category) {
            // Show the card with animation
            card.style.display = 'block';
            card.style.animation = 'fadeInUp 0.6s ease-out';
        } else {
            // Hide the card
            card.style.display = 'none';
        }
    });
    
    // Update the news grid layout
    updateNewsGridLayout();
}

function updateNewsGridLayout() {
    const newsGrid = document.querySelector('.news-grid');
    const visibleCards = Array.from(newsGrid.children).filter(card => 
        card.style.display !== 'none'
    );
    
    // Add staggered animation delay for visible cards
    visibleCards.forEach((card, index) => {
        card.style.animationDelay = `${index * 0.1}s`;
    });
}

function setupInteractiveElements() {
    // Remove modal behavior: allow native link navigation only
    // Load more button (legacy fallback if present)
    const loadMoreBtn = document.querySelector('.load-more-btn');
    if (loadMoreBtn) {
        loadMoreBtn.addEventListener('click', function() {
            loadMoreArticles();
        });
    }
}

async function fetchLiveNews(initial = false) {
    const grid = document.getElementById('news-grid');
    if (!grid) return;

    const state = window.__NEWS_STATE__;
    if (state.loading) return;
    state.loading = true;

    if (initial) {
        // Show skeletons while initial loading
        grid.innerHTML = createSkeletonCards(state.pageSize);
    }

    try {
        const response = await fetch('/api/news');
        if (!response.ok) throw new Error('Failed to load news');
        const data = await response.json();
        const items = Array.isArray(data.items) ? data.items : [];
        if (items.length === 0) {
            grid.innerHTML = emptyStateHTML();
            state.reachedEnd = true;
            return;
        }
        // Sort newest first if possible
        const sorted = items.slice();
        try {
            sorted.sort((a, b) => new Date(b.published || 0) - new Date(a.published || 0));
        } catch (e) {}
        state.allItems = sorted;
        state.page = 0;
        state.reachedEnd = false;
        renderFeatured(sorted[0]);
        renderNextPage();
    } catch (err) {
        console.error(err);
        grid.innerHTML = errorStateHTML();
    } finally {
        state.loading = false;
    }
}

function renderFeatured(item) {
    if (!item) return;
    
    const titleEl = document.getElementById('featured-title');
    const excerptEl = document.getElementById('featured-excerpt');
    const dateEl = document.getElementById('featured-date');
    const sourceEl = document.getElementById('featured-source');
    const linkEl = document.getElementById('featured-link');
    const imgEl = document.getElementById('featured-image');
    const phEl = document.getElementById('featured-placeholder');

    if (titleEl) titleEl.textContent = item.title || 'Latest news';
    if (excerptEl) excerptEl.textContent = (item.summary || '').slice(0, 220);
    if (dateEl) dateEl.innerHTML = `<i class="fas fa-calendar"></i> ${item.published || ''}`;
    if (sourceEl) sourceEl.innerHTML = `<i class="fas fa-newspaper"></i> ${item.source || ''}`;
    if (linkEl && item.link) {
        linkEl.href = item.link;
        
        // Add click event listener as fallback
        linkEl.onclick = function(e) {
            e.preventDefault();
            window.open(item.link, '_blank', 'noopener,noreferrer');
        };
    }
    const img = item.image;
    if (img && imgEl && phEl) {
        imgEl.src = img;
        imgEl.style.display = 'block';
        imgEl.loading = 'lazy';
        imgEl.referrerPolicy = 'no-referrer';
        phEl.style.display = 'none';
    }
}

function renderNextPage() {
    const grid = document.getElementById('news-grid');
    const state = window.__NEWS_STATE__;
    if (!grid || state.reachedEnd) return;

    const start = state.page * state.pageSize;
    const filtered = state.filteredCategory === 'all'
        ? state.allItems
        : state.allItems.filter(i => (i.category || 'other') === state.filteredCategory);
    const pageItems = filtered.slice(start, start + state.pageSize);

    if (state.page === 0) grid.innerHTML = '';

    if (pageItems.length === 0) {
        if (state.page === 0) grid.innerHTML = emptyStateHTML();
        state.reachedEnd = true;
        return;
    }

    const html = pageItems.map(renderNewsItem).join('');
    grid.insertAdjacentHTML('beforeend', html);
    state.page += 1;

    // Re-bind interactions for newly added cards
    setupInteractiveElements();
}

function setupInfiniteScroll() {
    window.addEventListener('scroll', () => {
        const state = window.__NEWS_STATE__;
        if (state.loading || state.reachedEnd) return;
        const scrollPosition = window.innerHeight + window.scrollY;
        const threshold = document.body.offsetHeight - 300;
        if (scrollPosition >= threshold) {
            renderNextPage();
        }
    });
}

function renderNewsItem(item) {
    const category = (item.category || 'other').toLowerCase();
    const icon = categoryIcon(category);
    const source = escapeHTML(item.source || '');
    const title = escapeHTML(item.title || '');
    const summary = escapeHTML(item.summary || '');
    const link = item.link || '#';
    const date = escapeHTML(item.published || '');
    const image = item.image || '';

    return `
        <article class="news-card" data-category="${category}">
            <a href="${link}" target="_blank" rel="noopener" style="text-decoration:none;color:inherit;">
                <div class="news-image">
                    ${image ? `<img src="${image}" alt="${title}" onerror="this.style.display='none'"/>` : `<div class=\"image-placeholder small\"><i class=\"${icon}\"></i></div>`}
                </div>
                <div class="news-content">
                    <div class="news-category">${prettyCategory(category)}${source ? ` · ${source}` : ''}</div>
                    <h3>${title}</h3>
                    <p>${summary}</p>
                    <div class="news-meta">
                        <span class="date">${date}</span>
                        <span class="read-time">Live</span>
                    </div>
                </div>
            </a>
        </article>
    `;
}

function createSkeletonCards(count) {
    return Array.from({ length: count }).map(() => `
        <article class="news-card" aria-busy="true">
            <div class="news-image">
                <div class="image-placeholder small" style="animation:pulse 1.2s infinite ease-in-out;"></div>
            </div>
            <div class="news-content">
                <div class="news-category" style="width:160px;height:20px;background:#e2e8f0;border-radius:8px;animation:pulse 1.2s infinite ease-in-out;"></div>
                <div style="height:20px;margin-top:12px;background:#e2e8f0;border-radius:8px;animation:pulse 1.2s infinite ease-in-out;"></div>
                <div style="height:14px;margin-top:10px;background:#edf2f7;border-radius:6px;animation:pulse 1.2s infinite ease-in-out;"></div>
                <div style="height:14px;margin-top:8px;background:#edf2f7;border-radius:6px;animation:pulse 1.2s infinite ease-in-out;"></div>
                <div class="news-meta" style="margin-top:12px;opacity:.6;">
                    <span class="date">Loading…</span>
                    <span class="read-time">Live</span>
                </div>
            </div>
        </article>
    `).join('');
}

function emptyStateHTML() {
    return `
        <div style="grid-column:1/-1;text-align:center;padding:2rem;color:#718096;">
            No news found right now. Please try again later.
        </div>
    `;
}

function errorStateHTML() {
    return `
        <div style="grid-column:1/-1;text-align:center;padding:2rem;color:#e53e3e;">
            Could not load news. Please refresh the page.
        </div>
    `;
}

function categoryIcon(category) {
    switch (category) {
        case 'technology': return 'fas fa-microchip';
        case 'policy': return 'fas fa-gavel';
        case 'science': return 'fas fa-flask';
        case 'business': return 'fas fa-briefcase';
        default: return 'fas fa-globe';
    }
}

function prettyCategory(category) {
    return category.charAt(0).toUpperCase() + category.slice(1);
}

function escapeHTML(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function setupNewsletterSignup() {
    const newsletterForm = document.querySelector('.newsletter-form');
    const newsletterInput = document.querySelector('.newsletter-input');
    const newsletterBtn = document.querySelector('.newsletter-btn');
    
    if (newsletterForm && newsletterInput && newsletterBtn) {
        newsletterForm.addEventListener('submit', function(e) {
            e.preventDefault();
            handleNewsletterSignup();
        });
        
        newsletterBtn.addEventListener('click', function(e) {
            e.preventDefault();
            handleNewsletterSignup();
        });
    }
}

function handleNewsletterSignup() {
    const email = document.querySelector('.newsletter-input').value.trim();
    
    if (!email) {
        showNotification('Please enter a valid email address', 'error');
        return;
    }
    
    if (!isValidEmail(email)) {
        showNotification('Please enter a valid email format', 'error');
        return;
    }
    
    // Simulate newsletter signup
    showNotification('Thank you for subscribing! You\'ll receive updates soon.', 'success');
    document.querySelector('.newsletter-input').value = '';
    
    // Add success animation
    const newsletterBtn = document.querySelector('.newsletter-btn');
    newsletterBtn.innerHTML = '<i class="fas fa-check"></i> Subscribed!';
    newsletterBtn.style.background = '#48bb78';
    
    setTimeout(() => {
        newsletterBtn.innerHTML = 'Subscribe';
        newsletterBtn.style.background = '#2d3748';
    }, 3000);
}

function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

function setupSmoothScrolling() {
    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

// Modal removed as per requirement: clicking opens the article link directly

// Modal styles removed since modal is no longer used

function getFeaturedArticleContent() {
    return `
        <p>New research published in Nature Climate Change reveals that global carbon emissions have reached unprecedented levels in 2024, despite international efforts to curb greenhouse gas production.</p>
        
        <p>The study, conducted by an international team of climate scientists, analyzed data from over 100 monitoring stations worldwide and found that atmospheric CO2 concentrations have increased by 2.4 parts per million (ppm) compared to 2023 levels.</p>
        
        <p>"This is deeply concerning," says Dr. Sarah Chen, lead author of the study. "We're seeing emissions continue to rise even as renewable energy adoption accelerates. It suggests that our current decarbonization efforts, while positive, are not yet sufficient to offset the continued growth in fossil fuel consumption."</p>
        
        <p>The research highlights several key findings:</p>
        <ul>
            <li>Transportation sector emissions increased by 3.2% globally</li>
            <li>Industrial emissions rose by 1.8% despite efficiency improvements</li>
            <li>Electricity generation emissions decreased by 2.1% due to renewable energy growth</li>
            <li>Land-use change contributed 15% of total emissions</li>
        </ul>
        
        <p>The study emphasizes the urgent need for more aggressive climate policies and accelerated deployment of clean energy technologies. "We have the solutions available," notes Dr. Chen. "What we need now is the political will and investment to scale them up rapidly."</p>
        
        <p>This research comes ahead of the upcoming UN Climate Change Conference, where world leaders will discuss strengthening commitments under the Paris Agreement.</p>
    `;
}

function getArticleContent(title, category) {
    // Sample article content based on title and category
    const articles = {
        'Breakthrough in Solar Panel Efficiency': `
            <p>Scientists at the National Renewable Energy Laboratory have achieved a breakthrough in solar panel technology, with new perovskite solar cells reaching 29.8% efficiency.</p>
            
            <p>This represents a significant improvement over traditional silicon-based panels, which typically achieve 15-20% efficiency. The new technology could dramatically reduce the cost of solar energy and accelerate the transition to renewable power sources.</p>
            
            <p>"This is a game-changer for the solar industry," says Dr. Michael Rodriguez, lead researcher on the project. "We're not just improving efficiency; we're making solar power more accessible to everyone."</p>
            
            <p>The research team expects commercial deployment to begin within the next 3-5 years, with initial applications in utility-scale solar farms and residential installations.</p>
        `,
        'EU Announces Stricter Carbon Trading Rules': `
            <p>The European Union has unveiled comprehensive reforms to its Emissions Trading System (ETS), introducing stricter carbon pricing mechanisms and expanded coverage.</p>
            
            <p>Key changes include:</p>
            <ul>
                <li>Reduction of free allowances by 50% by 2030</li>
                <li>Inclusion of maritime transport emissions</li>
                <li>New carbon border adjustment mechanism</li>
                <li>Enhanced monitoring and verification requirements</li>
            </ul>
            
            <p>These reforms are expected to increase carbon prices from current levels of €80 per ton to over €150 per ton by 2030, providing stronger incentives for emission reductions across all sectors.</p>
            
            <p>"This sends a clear signal to investors and businesses that the EU is serious about achieving climate neutrality," says EU Climate Commissioner Frans Timmermans.</p>
        `,
        'Ocean Carbon Sequestration Study Reveals New Insights': `
            <p>Marine scientists have discovered that ocean currents play a crucial role in natural carbon absorption, with implications for climate models and carbon removal strategies.</p>
            
            <p>The study, published in Science, used advanced oceanographic techniques to track carbon flow through major ocean currents. Researchers found that the Atlantic Meridional Overturning Circulation (AMOC) is responsible for transporting approximately 20% of anthropogenic CO2 into the deep ocean.</p>
            
            <p>"Understanding these natural processes is crucial for predicting future climate scenarios," explains Dr. Elena Martinez, oceanographer at the Woods Hole Oceanographic Institution. "The ocean is our largest carbon sink, and we need to understand how it works."</p>
            
            <p>The research also highlights the potential for enhanced ocean carbon sequestration through artificial upwelling and other geoengineering approaches, though the authors caution that such interventions require careful consideration of ecological impacts.</p>
        `,
        'Major Corporations Commit to Net-Zero Supply Chains': `
            <p>Twenty-five Fortune 500 companies have announced ambitious plans to eliminate carbon emissions from their entire supply chain by 2030, representing a combined market value of over $2 trillion.</p>
            
            <p>The initiative, called "Net-Zero Supply Chain 2030," includes companies from various sectors including technology, retail, manufacturing, and finance. Each company has committed to:</p>
            <ul>
                <li>Conduct comprehensive supply chain audits</li>
                <li>Set science-based emission reduction targets</li>
                <li>Invest in supplier decarbonization programs</li>
                <li>Report progress annually with third-party verification</li>
            </ul>
            
            <p>"This is the most significant corporate climate action we've seen to date," says climate analyst Jennifer Kim. "These companies are recognizing that addressing supply chain emissions is essential for achieving their climate goals."</p>
            
            <p>The initiative is expected to catalyze similar commitments from other companies and could significantly accelerate the decarbonization of global supply chains.</p>
        `,
        'Electric Vehicle Adoption Surges Globally': `
            <p>Global electric vehicle sales have reached new heights in 2024, with battery technology improvements and expanding charging infrastructure driving adoption across major markets.</p>
            
            <p>According to the International Energy Agency, EV sales increased by 35% compared to 2023, with particularly strong growth in Europe, China, and North America. Battery costs have decreased by 15% year-over-year, while energy density has improved by 20%.</p>
            
            <p>"We're seeing a virtuous cycle in the EV market," says automotive analyst David Chen. "Better technology leads to more sales, which leads to more investment in infrastructure and technology."</p>
            
            <p>Key developments include:</p>
            <ul>
                <li>New solid-state battery technology entering production</li>
                <li>Ultra-fast charging networks expanding rapidly</li>
                <li>Government incentives driving adoption in emerging markets</li>
                <li>Automakers committing to full electrification by 2035</li>
            </ul>
            
            <p>This rapid adoption is expected to significantly reduce transportation sector emissions and accelerate the transition to sustainable mobility.</p>
        `,
        'Reforestation Projects Show Promising Results': `
            <p>Large-scale tree planting initiatives around the world are demonstrating measurable impact on local carbon levels and biodiversity restoration, according to new research published in Global Change Biology.</p>
            
            <p>The study analyzed 150 reforestation projects across 25 countries, finding that well-designed projects can sequester an average of 2.5 tons of CO2 per hectare per year. Projects that incorporate native species and consider local ecological conditions showed the best results.</p>
            
            <p>"Reforestation is not just about planting trees," emphasizes Dr. Maria Santos, forest ecologist and study co-author. "It's about restoring entire ecosystems and working with local communities to ensure long-term success."</p>
            
            <p>Notable success stories include:</p>
            <ul>
                <li>China's Loess Plateau restoration (2.5 million hectares)</li>
                <li>Brazil's Atlantic Forest restoration (1.2 million hectares)</li>
                <li>Ethiopia's Green Legacy Initiative (20 billion trees)</li>
                <li>India's Compensatory Afforestation Fund projects</li>
            </ul>
            
            <p>The research also highlights the importance of protecting existing forests alongside reforestation efforts, as mature forests store significantly more carbon than newly planted areas.</p>
        `
    };
    
    return articles[title] || `
        <p>This article is currently being prepared. Please check back soon for the full content.</p>
        <p>In the meantime, explore other articles in our learning center to discover more about carbon emissions and environmental sustainability.</p>
    `;
}

function loadMoreArticles() {
    const loadMoreBtn = document.querySelector('.load-more-btn');
    const newsGrid = document.querySelector('.news-grid');
    
    // Show loading state
    loadMoreBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';
    loadMoreBtn.disabled = true;
    
    // Simulate loading delay
    setTimeout(() => {
        // Add new sample articles
        const newArticles = [
            {
                category: 'Technology',
                title: 'Carbon Capture Technology Breakthrough',
                excerpt: 'New direct air capture systems show 40% improvement in efficiency and cost reduction.',
                date: 'Dec 8, 2024',
                readTime: '4 min read',
                icon: 'fas fa-filter'
            },
            {
                category: 'Policy & Regulations',
                title: 'US Announces New Climate Investment Fund',
                excerpt: 'Biden administration launches $50 billion fund for clean energy infrastructure projects.',
                date: 'Dec 7, 2024',
                readTime: '3 min read',
                icon: 'fas fa-dollar-sign'
            }
        ];
        
        newArticles.forEach(article => {
            const articleHTML = createArticleHTML(article);
            newsGrid.insertAdjacentHTML('beforeend', articleHTML);
        });
        
        // Reset button
        loadMoreBtn.innerHTML = '<i class="fas fa-plus"></i> Load More Articles';
        loadMoreBtn.disabled = false;
        
        // Show success message
        showNotification('New articles loaded successfully!', 'success');
        
        // Add click handlers to new articles
        const newCards = newsGrid.querySelectorAll('.news-card:not([data-initialized])');
        newCards.forEach(card => {
            card.setAttribute('data-initialized', 'true');
            card.addEventListener('click', function() {
                const title = this.querySelector('h3').textContent;
                const category = this.querySelector('.news-category').textContent;
                const content = getArticleContent(title, category);
                showArticleModal(title, content);
            });
        });
        
    }, 1500);
}

function createArticleHTML(article) {
    return `
        <article class="news-card" data-category="${article.category.toLowerCase().replace(' & ', '-').replace(' ', '-')}">
            <div class="news-image">
                <div class="image-placeholder small">
                    <i class="${article.icon}"></i>
                </div>
            </div>
            <div class="news-content">
                <div class="news-category">${article.category}</div>
                <h3>${article.title}</h3>
                <p>${article.excerpt}</p>
                <div class="news-meta">
                    <span class="date">${article.date}</span>
                    <span class="read-time">${article.readTime}</span>
                </div>
            </div>
        </article>
    `;
}

function showNotification(message, type = 'info') {
    // Remove existing notifications
    const existingNotifications = document.querySelectorAll('.notification');
    existingNotifications.forEach(notification => notification.remove());
    
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
            <span>${message}</span>
        </div>
    `;
    
    // Add notification styles
    addNotificationStyles();
    
    // Add to page
    document.body.appendChild(notification);
    
    // Show notification
    setTimeout(() => {
        notification.classList.add('show');
    }, 100);
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 5000);
}

function addNotificationStyles() {
    if (document.querySelector('#notification-styles')) return;
    
    const style = document.createElement('style');
    style.id = 'notification-styles';
    style.textContent = `
        .notification {
            position: fixed;
            top: 20px;
            right: 20px;
            background: white;
            border-radius: 10px;
            padding: 1rem 1.5rem;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
            z-index: 1001;
            transform: translateX(400px);
            transition: transform 0.3s ease;
            max-width: 400px;
        }
        
        .notification.show {
            transform: translateX(0);
        }
        
        .notification-content {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }
        
        .notification i {
            font-size: 1.2rem;
        }
        
        .notification-success i {
            color: #48bb78;
        }
        
        .notification-error i {
            color: #f56565;
        }
        
        .notification-info i {
            color: #4299e1;
        }
        
        @media (max-width: 768px) {
            .notification {
                right: 10px;
                left: 10px;
                max-width: none;
            }
        }
    `;
    document.head.appendChild(style);
}
