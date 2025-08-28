<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Anush S Jathan - Data Scientist</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #fff;
            overflow-x: hidden;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }

        .hero {
            text-align: center;
            padding: 80px 20px;
            position: relative;
        }

        .hero::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="1" fill="rgba(255,255,255,0.1)"><animate attributeName="r" values="1;10;1" dur="3s" repeatCount="indefinite"/></circle></svg>') repeat;
            animation: float 6s ease-in-out infinite;
            z-index: -1;
        }

        @keyframes float {
            0%, 100% { transform: translateY(0px); }
            50% { transform: translateY(-20px); }
        }

        .profile-img {
            width: 150px;
            height: 150px;
            border-radius: 50%;
            border: 4px solid rgba(255, 255, 255, 0.3);
            margin: 0 auto 30px;
            background: linear-gradient(45deg, #ff6b6b, #4ecdc4);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 60px;
            cursor: pointer;
            transition: transform 0.3s ease;
        }

        .profile-img:hover {
            transform: scale(1.1) rotate(5deg);
        }

        .typing-text {
            font-size: 2.5em;
            font-weight: bold;
            margin-bottom: 20px;
            min-height: 80px;
        }

        .description {
            font-size: 1.2em;
            opacity: 0.9;
            max-width: 600px;
            margin: 0 auto;
            line-height: 1.6;
        }

        .section {
            margin: 60px 0;
            padding: 40px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(31, 38, 135, 0.37);
            border: 1px solid rgba(255, 255, 255, 0.18);
        }

        .section h2 {
            text-align: center;
            font-size: 2.2em;
            margin-bottom: 40px;
            position: relative;
        }

        .section h2::after {
            content: '';
            width: 100px;
            height: 3px;
            background: linear-gradient(45deg, #ff6b6b, #4ecdc4);
            position: absolute;
            bottom: -10px;
            left: 50%;
            transform: translateX(-50%);
            border-radius: 2px;
        }

        .tech-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 20px;
            margin: 40px 0;
        }

        .tech-item {
            background: rgba(255, 255, 255, 0.1);
            padding: 20px;
            border-radius: 15px;
            text-align: center;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            cursor: pointer;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }

        .tech-item:hover {
            transform: translateY(-10px);
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.2);
            background: rgba(255, 255, 255, 0.2);
        }

        .tech-item .icon {
            font-size: 2.5em;
            margin-bottom: 10px;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 30px;
            margin: 40px 0;
        }

        .stat-card {
            background: rgba(255, 255, 255, 0.1);
            padding: 30px;
            border-radius: 15px;
            text-align: center;
            transition: transform 0.3s ease;
            cursor: pointer;
        }

        .stat-card:hover {
            transform: scale(1.05);
        }

        .stat-number {
            font-size: 2.5em;
            font-weight: bold;
            color: #4ecdc4;
            margin-bottom: 10px;
            counter-reset: num var(--num);
        }

        .stat-number::after {
            content: counter(num);
            animation: counter 2s ease-out forwards;
        }

        @keyframes counter {
            from { --num: 0; }
            to { --num: var(--target); }
        }

        .connect-buttons {
            display: flex;
            justify-content: center;
            gap: 20px;
            flex-wrap: wrap;
            margin: 40px 0;
        }

        .btn {
            padding: 12px 30px;
            background: linear-gradient(45deg, #ff6b6b, #4ecdc4);
            color: white;
            text-decoration: none;
            border-radius: 25px;
            font-weight: bold;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .btn:hover {
            transform: translateY(-3px);
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
        }

        .skills-progress {
            margin: 30px 0;
        }

        .skill-item {
            margin: 20px 0;
        }

        .skill-name {
            font-weight: bold;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
        }

        .progress-bar {
            height: 8px;
            background: rgba(255, 255, 255, 0.2);
            border-radius: 4px;
            overflow: hidden;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(45deg, #ff6b6b, #4ecdc4);
            border-radius: 4px;
            transition: width 2s ease;
            width: 0%;
        }

        .wave {
            position: absolute;
            bottom: 0;
            left: 0;
            width: 100%;
            height: 100px;
            background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 120" preserveAspectRatio="none"><path d="M985.66,92.83C906.67,72,823.78,31,743.84,14.19c-82.26-17.34-168.06-16.33-250.45.39-57.84,11.73-114,31.07-172,41.86A600.21,600.21,0,0,1,0,27.35V120H1200V95.8C1132.19,118.92,1055.71,111.31,985.66,92.83Z" fill="rgba(255,255,255,0.1)"/></svg>') repeat-x;
            animation: wave 10s linear infinite;
        }

        @keyframes wave {
            0% { background-position-x: 0; }
            100% { background-position-x: 1200px; }
        }

        .activity-graph {
            background: rgba(255, 255, 255, 0.1);
            padding: 20px;
            border-radius: 15px;
            margin: 30px 0;
            text-align: center;
        }

        .graph-grid {
            display: grid;
            grid-template-columns: repeat(52, 1fr);
            gap: 3px;
            margin: 20px 0;
        }

        .graph-day {
            width: 12px;
            height: 12px;
            background: rgba(255, 255, 255, 0.2);
            border-radius: 2px;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .graph-day:hover {
            transform: scale(1.5);
        }

        .graph-day.active-1 { background: rgba(76, 205, 196, 0.3); }
        .graph-day.active-2 { background: rgba(76, 205, 196, 0.6); }
        .graph-day.active-3 { background: rgba(76, 205, 196, 0.9); }
        .graph-day.active-4 { background: rgba(76, 205, 196, 1); }

        @media (max-width: 768px) {
            .typing-text { font-size: 1.8em; }
            .tech-grid { grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); }
            .stats-grid { grid-template-columns: 1fr; }
            .connect-buttons { flex-direction: column; align-items: center; }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Hero Section -->
        <div class="hero">
            <div class="profile-img" onclick="this.style.transform='scale(1.2) rotate(360deg)'">
                👋
            </div>
            <div class="typing-text" id="typing-text"></div>
            <p class="description">
                I am a passionate Data Scientist from India with a love for building useful and beautiful applications. 
                I'm always looking to learn and grow as a developer and I enjoy collaborating with others. 
                Let's connect and build something awesome! 🚀
            </p>
        </div>

        <!-- Tech Stack Section -->
        <div class="section">
            <h2>💻 My Tech Stack</h2>
            <div class="tech-grid">
                <div class="tech-item" data-skill="Python">
                    <div class="icon">🐍</div>
                    <div>Python</div>
                </div>
                <div class="tech-item" data-skill="R">
                    <div class="icon">📊</div>
                    <div>R</div>
                </div>
                <div class="tech-item" data-skill="JavaScript">
                    <div class="icon">⚡</div>
                    <div>JavaScript</div>
                </div>
                <div class="tech-item" data-skill="Machine Learning">
                    <div class="icon">🤖</div>
                    <div>ML</div>
                </div>
                <div class="tech-item" data-skill="Data Viz">
                    <div class="icon">📈</div>
                    <div>Data Viz</div>
                </div>
                <div class="tech-item" data-skill="Flask">
                    <div class="icon">🌶️</div>
                    <div>Flask</div>
                </div>
                <div class="tech-item" data-skill="Django">
                    <div class="icon">🎯</div>
                    <div>Django</div>
                </div>
                <div class="tech-item" data-skill="Git">
                    <div class="icon">🔧</div>
                    <div>Git</div>
                </div>
            </div>
        </div>

        <!-- Skills Progress -->
        <div class="section">
            <h2>🚀 Skills Progress</h2>
            <div class="skills-progress">
                <div class="skill-item">
                    <div class="skill-name">
                        <span>Python</span>
                        <span>90%</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" data-width="90"></div>
                    </div>
                </div>
                <div class="skill-item">
                    <div class="skill-name">
                        <span>Data Science</span>
                        <span>85%</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" data-width="85"></div>
                    </div>
                </div>
                <div class="skill-item">
                    <div class="skill-name">
                        <span>Machine Learning</span>
                        <span>80%</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" data-width="80"></div>
                    </div>
                </div>
                <div class="skill-item">
                    <div class="skill-name">
                        <span>Web Development</span>
                        <span>75%</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" data-width="75"></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- GitHub Activity -->
        <div class="section">
            <h2>📈 GitHub Activity</h2>
            <div class="activity-graph">
                <p>Contribution Activity (Simulated)</p>
                <div class="graph-grid" id="activity-grid"></div>
                <p style="font-size: 0.9em; opacity: 0.8; margin-top: 15px;">
                    🟩 Less ← → More contributions
                </p>
            </div>
        </div>

        <!-- Stats Section -->
        <div class="section">
            <h2>📊 GitHub Stats</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number" style="--target: 50">0</div>
                    <div>Public Repos</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" style="--target: 1000">0</div>
                    <div>Total Commits</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" style="--target: 15">0</div>
                    <div>Projects</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" style="--target: 500">0</div>
                    <div>Lines of Code</div>
                </div>
            </div>
        </div>

        <!-- Connect Section -->
        <div class="section">
            <h2>🔗 Connect with Me</h2>
            <div class="connect-buttons">
                <a href="https://www.linkedin.com/in/anush-s-jathan" class="btn" target="_blank">
                    <span>💼</span> LinkedIn
                </a>
                <a href="https://neaasj.netlify.app" class="btn" target="_blank">
                    <span>🌐</span> Website
                </a>
                <a href="https://github.com/NeoASJ" class="btn" target="_blank">
                    <span>📱</span> GitHub
                </a>
                <a href="mailto:your.email@example.com" class="btn" target="_blank">
                    <span>📧</span> Email
                </a>
            </div>
        </div>
    </div>

    <div class="wave"></div>

    <script>
        // Typing animation
        const texts = [
            "Hello there, I'm Anush S Jathan! 👋",
            "Data Scientist 📊",
            "Data Analyst 📈", 
            "AI Enthusiast 🤖",
            "Problem Solver 🧩"
        ];
        
        let textIndex = 0;
        let charIndex = 0;
        let isDeleting = false;
        
        function typeText() {
            const currentText = texts[textIndex];
            const typingElement = document.getElementById('typing-text');
            
            if (isDeleting) {
                typingElement.textContent = currentText.substring(0, charIndex - 1);
                charIndex--;
                
                if (charIndex === 0) {
                    isDeleting = false;
                    textIndex = (textIndex + 1) % texts.length;
                }
            } else {
                typingElement.textContent = currentText.substring(0, charIndex + 1);
                charIndex++;
                
                if (charIndex === currentText.length) {
                    isDeleting = true;
                    setTimeout(typeText, 2000);
                    return;
                }
            }
            
            setTimeout(typeText, isDeleting ? 50 : 100);
        }
        
        // Start typing animation
        typeText();
        
        // Animate progress bars on scroll
        function animateProgressBars() {
            const progressBars = document.querySelectorAll('.progress-fill');
            progressBars.forEach(bar => {
                const width = bar.getAttribute('data-width');
                setTimeout(() => {
                    bar.style.width = width + '%';
                }, 500);
            });
        }
        
        // Generate activity graph
        function generateActivityGraph() {
            const grid = document.getElementById('activity-grid');
            for (let i = 0; i < 364; i++) {
                const day = document.createElement('div');
                day.className = 'graph-day';
                
                const random = Math.random();
                if (random > 0.8) day.classList.add('active-4');
                else if (random > 0.6) day.classList.add('active-3');
                else if (random > 0.4) day.classList.add('active-2');
                else if (random > 0.2) day.classList.add('active-1');
                
                day.addEventListener('mouseover', function() {
                    this.style.transform = 'scale(1.5)';
                });
                
                day.addEventListener('mouseout', function() {
                    this.style.transform = 'scale(1)';
                });
                
                grid.appendChild(day);
            }
        }
        
        // Animate counters
        function animateCounters() {
            const counters = document.querySelectorAll('.stat-number');
            counters.forEach(counter => {
                const target = parseInt(counter.style.getPropertyValue('--target'));
                let current = 0;
                const increment = target / 100;
                
                const updateCounter = () => {
                    current += increment;
                    if (current < target) {
                        counter.textContent = Math.ceil(current);
                        requestAnimationFrame(updateCounter);
                    } else {
                        counter.textContent = target;
                    }
                };
                
                updateCounter();
            });
        }
        
        // Initialize animations
        setTimeout(animateProgressBars, 1000);
        setTimeout(animateCounters, 1500);
        generateActivityGraph();
        
        // Add hover effects to tech items
        document.querySelectorAll('.tech-item').forEach(item => {
            item.addEventListener('click', function() {
                const skill = this.getAttribute('data-skill');
                alert(`You clicked on ${skill}! 🎉`);
            });
        });
        
        // Add particle effect on mouse move
        document.addEventListener('mousemove', function(e) {
            const particle = document.createElement('div');
            particle.style.position = 'fixed';
            particle.style.width = '5px';
            particle.style.height = '5px';
            particle.style.backgroundColor = 'rgba(255, 255, 255, 0.5)';
            particle.style.borderRadius = '50%';
            particle.style.pointerEvents = 'none';
            particle.style.left = e.clientX + 'px';
            particle.style.top = e.clientY + 'px';
            particle.style.zIndex = '9999';
            
            document.body.appendChild(particle);
            
            setTimeout(() => {
                particle.remove();
            }, 1000);
        });
    </script>
</body>
</html>
