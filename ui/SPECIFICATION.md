# GeNarrative UI Application Specification

## 📋 Overview

GeNarrative UI is a web application for multimedia storytelling. Users can create scenes, combine them to generate and manage interactive narratives.

### 🎯 Key Features
- Scene management (list view, detail view)
- Drag & drop narrative creation
- Multimedia slideshow generation using Swiper.js
- Synchronized TTS audio and BGM music playback
- Self-contained HTML narrative export
- Narrative list management (view, download, delete)

## 🏗️ Architecture

### System Configuration
```
GeNarrative-dev/
├── ui/                          # Main Web Application
│   ├── app/
│   │   ├── main.py             # Flask Main Application
│   │   ├── templates/          # HTML Templates
│   │   └── static/             # Static Files (CSS/JS)
│   ├── Dockerfile              # UI Container Configuration
│   └── requirements.txt        # Python Dependencies
├── shared/                      # Shared Data Directory
│   ├── scene/                  # Scene Data (images, audio, text)
│   └── narrative/              # Generated Narrative HTML
└── docker-compose.yml          # Container Orchestration
```

### Technology Stack
- **Backend**: Flask (Python)
- **Frontend**: HTML5, CSS3, JavaScript (ES6)
- **UI Library**: Swiper.js (Slideshow)
- **Containerization**: Docker, Docker Compose
- **File Format**: HTML5 with Base64 embedded assets

## 📂 Directory Structure Details

### UI Application (`/ui/app/`)

#### `main.py` - Main Application
```python
# Primary route handlers
@app.route("/")                          # Home screen
@app.route("/scene")                     # Scene list
@app.route("/scene/<scene_id>")          # Scene details
@app.route("/narratives")                # Narrative list
@app.route("/narrative/save")            # Narrative save API
@app.route("/narrative/view/<filename>") # Narrative view
@app.route("/narrative/delete/<filename>") # Narrative delete API
```

#### `templates/` - HTML Templates
```
templates/
├── base.html              # Base template (navigation)
├── index.html             # Home screen
├── scene_list.html        # Scene list & narrative creation screen
├── scene_detail.html      # Scene detail view
├── narrative_list.html    # Narrative list management screen
└── gallery.html           # Image gallery
```

## 🔧 Major Feature Details

### 1. Scene Management System

#### Scene Data Structure
```
shared/scene/{scene_id}/
├── image_{timestamp}.png      # Scene image
├── text_{timestamp}.txt       # Scene text
├── tts_{timestamp}.wav        # TTS audio
├── music_{timestamp}.wav      # BGM music
└── sis_structure_{timestamp}.json # SIS (formerly SIS) structure data
```

#### Internal Processing
```python
def get_scene_data(scene_id):
    """Integrated scene data retrieval"""
    # 1. Search files in directory
    # 2. Check existence of various media files
    # 3. Load text content
    # 4. Return integrated data in JSON format
```

### 2. Narrative Creation System

#### Drag & Drop Functionality
```javascript
// Using HTML5 Drag and Drop API
card.addEventListener('dragstart', handleDragStart);
timeline.addEventListener('drop', handleDrop);
timeline.addEventListener('dragover', handleDragOver);
```

#### Internal Processing Flow
1. **Scene Selection**: User drags scene card
2. **Timeline Placement**: Drop to add to narrative timeline
3. **Data Accumulation**: Store in `narrativeScenes[]` array
4. **Real-time Update**: Immediate timeline display update

### 3. Slideshow Generation System

#### Swiper.js Integration
```javascript
// Slideshow initialization
narrativeSwiper = new Swiper('.narrative-swiper', {
    direction: 'horizontal',
    navigation: { nextEl: '.swiper-button-next', prevEl: '.swiper-button-prev' },
    pagination: { el: '.swiper-pagination', clickable: true },
    on: { slideChange: function() { playSlideAudio(this.activeIndex); } }
});
```

#### Audio Synchronization System
```javascript
function playSlideAudio(slideIndex) {
    stopAllAudio();                    // Stop previous audio
    if (hasTTS) playTTSAudio(sceneId); // Play TTS
    if (hasMusic) setTimeout(() => {   // Delayed BGM play (1 second later)
        playMusicAudio(sceneId);
    }, 1000);
}
```

### 4. HTML Export System

#### Base64 Embedding Processing
```python
def generate_narrative_html(narrative_data, title):
    """Generate self-contained HTML"""
    processed_data = []
    for scene_data in narrative_data:
        # Image Base64 encoding
        with open(img_file_path, 'rb') as img_file:
            img_data = base64.b64encode(img_file.read()).decode('utf-8')
            processed_scene['image_data'] = f"data:image/png;base64,{img_data}"
        
        # TTS audio Base64 encoding
        with open(tts_file_path, 'rb') as tts_file:
            tts_data = base64.b64encode(tts_file.read()).decode('utf-8')
            processed_scene['tts_data'] = f"data:audio/wav;base64,{tts_data}"
        
        # BGM music Base64 encoding
        with open(music_file_path, 'rb') as music_file:
            music_data = base64.b64encode(music_file.read()).decode('utf-8')
            processed_scene['music_data'] = f"data:audio/wav;base64,{music_data}"
```

#### Generated HTML Features
- **Self-contained**: No external dependencies, complete in single file
- **Multimedia Support**: Integrated images, audio, and text
- **Interactive**: Smooth navigation with Swiper.js
- **Audio Control**: Auto-play, manual control, stop functionality
- **Responsive**: Mobile and tablet support

### 5. Narrative Management System

#### List Display Function
```python
@app.route("/narratives")
def narrative_list():
    """Retrieve and display narrative file list"""
    # 1. Scan narrative/ directory
    # 2. Extract HTML files
    # 3. Get file information (size, modification date)
    # 4. Sort by newest first
    # 5. Pass to template for display
```

#### CRUD Operations
- **View**: `/narrative/view/<filename>` - Play in new tab
- **Download**: Direct HTML file delivery
- **Delete**: `/narrative/delete/<filename>` - AJAX deletion processing

## 🎨 UI/UX Design

### Design System
```css
/* Color Palette */
--primary-color: #007bff;      /* Main actions */
--success-color: #28a745;      /* Success, creation */
--danger-color: #dc3545;       /* Delete, warning */
--secondary-color: #6c757d;    /* Secondary actions */

/* Layout */
--container-max-width: 1200px;
--card-border-radius: 12px;
--shadow-light: 0 2px 4px rgba(0,0,0,0.1);
--shadow-medium: 0 4px 8px rgba(0,0,0,0.15);
```

### Responsive Breakpoints
- **Desktop**: `>= 1024px` - Full grid layout
- **Tablet**: `768px - 1023px` - 2-column grid
- **Mobile**: `< 768px` - 1-column stack

### Accessibility Support
- Semantic HTML usage
- ARIA attribute application
- Keyboard navigation support
- Information design not dependent on color alone

## 🔄 Data Flow

### Narrative Creation Flow
```
1. [Scene List] User views scenes
      ↓
2. [Drag & Drop] Place scenes on timeline
      ↓
3. [Generate Narrative] Request slideshow generation
      ↓
4. [Data Retrieval] API calls for each scene's detailed data
      ↓
5. [Swiper Generation] Frontend slideshow construction
      ↓
6. [Save Narrative] HTML export processing
      ↓
7. [Base64 Conversion] Embed all assets
      ↓
8. [File Save] Save to shared/narrative/
```

### Audio Playback Flow
```
1. [Page Load] Wait for user interaction state
      ↓
2. [User Click] Obtain audio playback permission
      ↓
3. [Slide Change] Detect Swiper event
      ↓
4. [Audio Stop] Stop previous slide audio
      ↓
5. [TTS Play] Play text-to-speech audio
      ↓
6. [BGM Delayed Play] Start BGM music after 1 second
```

## 🔐 Security & Error Handling

### File Access Control
```python
# File extension validation
if not filename.endswith('.html'):
    return jsonify({'error': 'Invalid file type'}), 400

# Path traversal prevention
safe_path = os.path.join(narrative_dir, os.path.basename(filename))
```

### Error Handling
```python
try:
    # File operations
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return jsonify({'success': True, 'data': content})
except FileNotFoundError:
    return jsonify({'error': 'File not found'}), 404
except Exception as e:
    return jsonify({'error': f'Server error: {str(e)}'}), 500
```

### Browser Compatibility Support
```javascript
// Audio autoplay policy support
hasUserInteracted = false;
document.addEventListener('click', enableAudioAfterInteraction, {once: true});

// Audio playback with error handling
audio.play().catch(error => {
    console.error('Audio playback failed:', error);
    // Fallback processing
});
```

## 🚀 Deployment & Development

### Docker Environment
```yaml
# docker-compose.yml
services:
  ui:
    build: ./ui
    ports: ["5000:5000"]
    volumes: ["./shared:/app/shared"]  # Hot reload support
    environment: ["FLASK_DEBUG=1"]
```

### Development Workflow
1. **Code Changes**: Edit files on host machine
2. **Auto Reflection**: Hot reload via Docker volume mount
3. **Browser Verification**: Real-time verification at `http://localhost:5000`
4. **Debug**: Detailed error display with Flask debug mode

### Production Environment Considerations
- **SECRET_KEY Configuration**: Flask production secret key
- **File Size Limits**: Upload/export size limits
- **Logging Configuration**: Proper access and error log output
- **HTTPS Support**: SSL/TLS certificate configuration

## 📊 Performance Optimization

### Frontend Optimization
- **Lazy Loading**: Fast initialization using Swiper.js CDN
- **Base64 Caching**: Browser-level image and audio caching
- **CSS Optimization**: Inline critical styles, minimize external CSS

### Backend Optimization
- **File I/O**: Read files only when necessary
- **Memory Management**: Proper handling of large Base64 data
- **Concurrent Processing**: Flask async support (as needed)

## 🔧 Future Extension Points

### Feature Enhancement Candidates
1. **User Authentication**: Multi-user support
2. **Template Functionality**: Save and reuse narrative templates
3. **Collaboration**: Multi-user collaborative editing
4. **Analytics**: Narrative viewing statistics
5. **API**: RESTful API for external integrations

### Technical Improvement Candidates
1. **React/Vue.js Migration**: Richer frontend
2. **Database Introduction**: PostgreSQL/MongoDB etc.
3. **Cloud Storage**: Large capacity support with AWS S3 etc.
4. **CDN Utilization**: Static content delivery optimization
5. **Microservices Architecture**: Function-specific service separation

---

## 📞 Support & Maintenance

### Troubleshooting
- **Audio Not Playing**: Browser autoplay policy → Encourage user click
- **File Not Found**: Check path and permissions
- **Slideshow Display Issues**: Check Swiper.js CDN connection

### Regular Maintenance
- **Log Rotation**: Regular log file cleanup
- **Storage Cleanup**: Remove unnecessary narrative files
- **Dependency Updates**: Apply security updates

---

**Created**: August 6, 2025  
**Version**: 1.0.0  
**Author**: GitHub Copilot  
**Update History**: Initial version created
