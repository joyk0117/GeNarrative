# GeNarrative UI - Development Guide

## 🚀 Development Environment Setup

### Prerequisites
- Docker Desktop installed
- Git available
- Any text editor (VS Code recommended)

### Initial Setup
```bash
# Clone project
git clone <repository_url>
cd GeNarrative-dev

# Build and start containers
docker-compose up -d

# Access in browser
open http://localhost:5000
```

## 🏗️ Development Workflow

### 1. Code Editing
```bash
# Edit UI application
vim ui/app/main.py              # Backend logic
vim ui/app/templates/*.html     # Frontend templates
```

### 2. Real-time Reflection
- Automatic reflection via Docker volume mount on file save
- Hot reload enabled with Flask debug mode
- Verify changes by refreshing browser

### 3. Log Checking
```bash
# Display UI service logs
docker-compose logs -f ui

# Logs for specific time range
docker-compose logs --since=1h ui
```

### 4. Container Management
```bash
# Restart service
docker-compose restart ui

# Complete rebuild
docker-compose down
docker-compose up --build -d
```

## 📁 File Structure Navigation

### Important Files List
```
ui/app/
├── main.py                 # 🎯 Main Application
├── templates/
│   ├── base.html          # 📐 Base Template
│   ├── scene_list.html    # 🎬 Scene List & Narrative Creation
│   ├── narrative_list.html # 📊 Narrative Management Screen
│   └── scene_detail.html  # 🔍 Scene Detail Display
└── static/                # 🎨 Static Files (as needed)
```

### Classification by Edit Frequency

#### 🔥 High Frequency Edit Files
- `main.py` - API & business logic additions
- `scene_list.html` - Narrative creation UI improvements
- `narrative_list.html` - Management feature extensions

#### 🔧 Medium Frequency Edit Files  
- `base.html` - Navigation & common layout
- `scene_detail.html` - Scene display features

#### 📋 Low Frequency Edit Files
- `Dockerfile` - When changing environment settings
- `requirements.txt` - When adding Python dependencies

## 🔄 Feature Addition Guide

### New Page Addition Procedure

#### 1. Add Route (main.py)
```python
@app.route("/new-feature")
def new_feature():
    """New feature page"""
    # Data retrieval logic
    data = get_some_data()
    return render_template('new_feature.html', data=data)
```

#### 2. Create Template
```html
<!-- templates/new_feature.html -->
{% extends "base.html" %}
{% block title %}New Feature{% endblock %}
{% block content %}
<div class="container">
    <h1>New Feature</h1>
    <!-- Feature implementation -->
</div>
{% endblock %}
```

#### 3. Add Navigation (base.html)
```html
<div class="nav-links">
    <a href="/new-feature">New Feature</a>
</div>
```

### API Endpoint Addition

#### GET Endpoint
```python
@app.route("/api/data/<param>")
def get_data(param):
    """Data retrieval API"""
    try:
        result = process_data(param)
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

#### POST Endpoint
```python
@app.route("/api/data", methods=['POST'])
def create_data():
    """Data creation API"""
    try:
        data = request.get_json()
        validate_data(data)  # Validation
        result = save_data(data)
        return jsonify({'success': True, 'id': result}), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

### Frontend JavaScript Extensions

#### AJAX Communication Template
```javascript
async function callAPI(url, method = 'GET', data = null) {
    try {
        const options = {
            method: method,
            headers: { 'Content-Type': 'application/json' }
        };
        
        if (data) options.body = JSON.stringify(data);
        
        const response = await fetch(url, options);
        const result = await response.json();
        
        if (result.success) {
            return result.data;
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        console.error('API Error:', error);
        alert(`Error: ${error.message}`);
        throw error;
    }
}
```

#### DOM Manipulation Helpers
```javascript
// Element creation helper
function createElement(tag, className, textContent) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (textContent) element.textContent = textContent;
    return element;
}

// Confirmation dialog helper
function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}
```

## 🎨 CSS & UI Development

### Style Guide
```css
/* Color variables */
:root {
    --primary: #007bff;
    --success: #28a745;
    --danger: #dc3545;
    --warning: #ffc107;
    --info: #17a2b8;
    --light: #f8f9fa;
    --dark: #343a40;
}

/* Responsive breakpoints */
@media (max-width: 768px) { /* Mobile */ }
@media (min-width: 769px) and (max-width: 1024px) { /* Tablet */ }
@media (min-width: 1025px) { /* Desktop */ }
```

### Component Creation
```css
/* Button component */
.btn {
    padding: 8px 16px;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    transition: background-color 0.2s ease;
}

.btn-primary { background-color: var(--primary); color: white; }
.btn-primary:hover { background-color: #0056b3; }

/* Card component */
.card {
    background: white;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    overflow: hidden;
    transition: transform 0.2s ease;
}

.card:hover { transform: translateY(-2px); }
```

## 🔧 Debug & Troubleshooting

### Common Issues and Solutions

#### 1. Container won't start
```bash
# Check port conflicts
lsof -i :5000

# Check container logs
docker-compose logs ui

# Force rebuild
docker-compose down --volumes
docker-compose up --build -d
```

#### 2. File changes not reflected
```bash
# Check volume mount
docker-compose exec ui ls -la /app

# Check Flask configuration
docker-compose exec ui env | grep FLASK

# Clear cache
docker-compose restart ui
```

#### 3. JavaScript errors
```javascript
// Debug with browser developer tools
console.log('Debug point:', variable);

// Enhanced error handling
try {
    // Processing
} catch (error) {
    console.error('Error details:', error);
    alert('Error occurred. Check console for details.');
}
```

#### 4. Audio not playing
```javascript
// Check browser autoplay policy
navigator.permissions.query({name: 'autoplay'}).then(result => {
    console.log('Autoplay permission:', result.state);
});

// Play after user interaction
document.addEventListener('click', enableAudio, {once: true});
```

### Enhanced Logging
```python
import logging

# Log configuration
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Log output during processing
logger.debug(f"Processing scene: {scene_id}")
logger.info(f"Narrative saved: {filename}")
logger.warning(f"File not found: {file_path}")
logger.error(f"Error occurred: {str(e)}")
```

## 📊 Performance Optimization

### Backend Optimization
```python
# File caching
from functools import lru_cache

@lru_cache(maxsize=128)
def get_scene_metadata(scene_id):
    """Scene metadata cache"""
    return load_scene_data(scene_id)

# Large file processing
def stream_large_file(file_path):
    """Stream delivery of large files"""
    def generate():
        with open(file_path, 'rb') as f:
            while True:
                data = f.read(4096)
                if not data:
                    break
                yield data
    return Response(generate(), mimetype='application/octet-stream')
```

### Frontend Optimization
```javascript
// Lazy loading
const lazyLoad = (selector) => {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                loadContent(entry.target);
                observer.unobserve(entry.target);
            }
        });
    });
    
    document.querySelectorAll(selector).forEach(el => {
        observer.observe(el);
    });
};

// Debounce
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
```

## 🧪 Test Implementation

### Unit Test Example
```python
import unittest
from main import app

class TestGeNarrativeAPI(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_scene_list(self):
        """Scene list retrieval test"""
        response = self.app.get('/scene')
        self.assertEqual(response.status_code, 200)

    def test_narrative_save(self):
        """Narrative save test"""
        data = {
            'narrative': [{'id': 'test_scene', 'text': 'test'}],
            'title': 'Test Narrative'
        }
        response = self.app.post('/narrative/save', 
                                json=data,
                                content_type='application/json')
        self.assertEqual(response.status_code, 200)

if __name__ == '__main__':
    unittest.main()
```

### Manual Test Checklist
- [ ] Scene list display
- [ ] Drag & drop functionality
- [ ] Slideshow generation
- [ ] Audio autoplay (after click)
- [ ] Narrative save
- [ ] Narrative list display
- [ ] Narrative deletion
- [ ] Responsive display (mobile)

## 🚀 Deployment

### Production Environment Preparation
```bash
# Environment variable setup
export FLASK_ENV=production
export SECRET_KEY=your-secret-key-here

# Install dependencies
pip install -r requirements.txt

# Start application
gunicorn -w 4 -b 0.0.0.0:5000 main:app
```

### Docker Production Configuration
```dockerfile
# Dockerfile.prod
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "main:app"]
```

---

**Updated**: August 6, 2025  
**Target Version**: 1.0.0
