class Presentation {
    constructor() {
        this.slides = document.querySelectorAll('.slide');
        this.currentSlideIndex = 0;
        this.totalSlides = this.slides.length;
        this.progressBar = document.getElementById('progressBar');
        this.slideCounter = document.getElementById('slideCounter');
        
        this.init();
    }

    init() {
        // Hide all slides except the first one
        this.slides.forEach((slide, index) => {
            if(index !== 0) {
                slide.classList.remove('active');
            } else {
                slide.classList.add('active');
            }
        });

        this.initComparisonBoxes();
        this.buildSideNav();
        this.updateUI();
        this.addEventListeners();
    }

    buildSideNav() {
        const topNav = document.createElement('nav');
        topNav.className = 'top-nav';
        this.topNavElement = topNav;
        this.navItems = [];

        const navCategories = [
            { title: '团队介绍', startIndex: 1 },
            { title: '项目背景', startIndex: 2 },
            { title: '项目介绍', startIndex: 3 },
            { title: '功能演示', startIndex: 4 },
            { title: '实战演示', startIndex: 7 },
            { title: '总结', startIndex: 10 }
        ];

        navCategories.forEach((cat) => {
            const navItem = document.createElement('div');
            navItem.className = 'nav-item';
            navItem.onclick = () => this.goToSlide(cat.startIndex);
            
            navItem.innerHTML = `
                <div class="nav-text">${cat.title}</div>
            `;
            
            topNav.appendChild(navItem);
            this.navItems.push({
                element: navItem,
                startIndex: cat.startIndex
            });
        });

        // Add to main container
        document.querySelector('.presentation-container').appendChild(topNav);
    }

    initComparisonBoxes() {
        const boxes = document.querySelectorAll('.comparison-box');
        boxes.forEach(box => {
            box.setAttribute('data-state', '0');
            box.addEventListener('click', (e) => {
                e.stopPropagation();
                let state = parseInt(box.getAttribute('data-state'));
                if (state < 2) {
                    box.setAttribute('data-state', (state + 1).toString());
                }
            });
        });
    }

    updateUI() {
        // Update Counter
        const current = String(this.currentSlideIndex + 1).padStart(2, '0');
        const max = String(this.totalSlides).padStart(2, '0');
        this.slideCounter.textContent = `${current} / ${max}`;

        // Reset comparison boxes on current slide when entering? 
        // Or just let them stay. Presentation usually prefers reset if re-entering.
        const currentSlideBoxes = this.slides[this.currentSlideIndex].querySelectorAll('.comparison-box');
        // currentSlideBoxes.forEach(box => box.setAttribute('data-state', '0'));

        // Update Nav Timeline
        if (this.navItems) {
            let activeNavIdx = -1;
            for (let i = this.navItems.length - 1; i >= 0; i--) {
                if (this.currentSlideIndex >= this.navItems[i].startIndex) {
                    activeNavIdx = i;
                    break;
                }
            }

            this.navItems.forEach((item, index) => {
                item.element.className = 'nav-item'; // Reset classes
                if (index === activeNavIdx) {
                    item.element.classList.add('active');
                }
            });
        }

        if (this.topNavElement) {
            if (this.currentSlideIndex === 0) {
                this.topNavElement.style.opacity = '0';
                this.topNavElement.style.pointerEvents = 'none';
            } else {
                this.topNavElement.style.opacity = '1';
                this.topNavElement.style.pointerEvents = 'auto';
            }
        }

        // Update Progress Bar
        const progress = ((this.currentSlideIndex) / (this.totalSlides - 1)) * 100;
        this.progressBar.style.width = `${progress}%`;
        
        // Disable/Enable buttons
        const prevBtn = document.getElementById('prevBtn');
        const nextBtn = document.getElementById('nextBtn');
        
        prevBtn.style.opacity = this.currentSlideIndex === 0 ? '0.3' : '1';
        prevBtn.style.pointerEvents = this.currentSlideIndex === 0 ? 'none' : 'auto';
        
        nextBtn.style.opacity = this.currentSlideIndex === this.totalSlides - 1 ? '0.3' : '1';
        nextBtn.style.pointerEvents = this.currentSlideIndex === this.totalSlides - 1 ? 'none' : 'auto';
    }

    nextSlide() {
        const currentSlide = this.slides[this.currentSlideIndex];
        const box = currentSlide.querySelector('.comparison-box');
        
        // PPT 逻辑：如果当前页有对比框且动画未完成，则先步进动画
        if (box) {
            let state = parseInt(box.getAttribute('data-state') || '0');
            if (state < 2) {
                box.setAttribute('data-state', (state + 1).toString());
                return;
            }
        }

        if (this.currentSlideIndex < this.totalSlides - 1) {
            this.slides[this.currentSlideIndex].classList.remove('active');
            this.currentSlideIndex++;
            this.slides[this.currentSlideIndex].classList.add('active');
            this.updateUI();
        }
    }

    prevSlide() {
        const currentSlide = this.slides[this.currentSlideIndex];
        const box = currentSlide.querySelector('.comparison-box');

        // PPT 逻辑：如果当前页有对比框且动画已开始，则先回退动画
        if (box) {
            let state = parseInt(box.getAttribute('data-state') || '0');
            if (state > 0) {
                box.setAttribute('data-state', (state - 1).toString());
                return;
            }
        }

        if (this.currentSlideIndex > 0) {
            this.slides[this.currentSlideIndex].classList.remove('active');
            this.currentSlideIndex--;
            this.slides[this.currentSlideIndex].classList.add('active');
            this.updateUI();
        }
    }
    
    goToSlide(index) {
        if(index >= 0 && index < this.totalSlides && index !== this.currentSlideIndex) {
            this.slides[this.currentSlideIndex].classList.remove('active');
            this.currentSlideIndex = index;
            this.slides[this.currentSlideIndex].classList.add('active');
            this.updateUI();
        }
    }

    addEventListeners() {
        // Keyboard navigation
        document.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') {
                e.preventDefault();
                this.nextSlide();
            } else if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
                e.preventDefault();
                this.prevSlide();
            }
        });
        
        // Check for click events (optional: click to advance)
        // document.addEventListener('click', (e) => { ... });
    }
}

// Initialize application when DOM is loaded
let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new Presentation();
});
