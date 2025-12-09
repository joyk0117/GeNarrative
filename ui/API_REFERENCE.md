# GeNarrative UI - API Reference

## 📡 REST API Endpoints

### Base URL
```
http://localhost:5000
```

## 🏠 Screen Display Endpoints

### GET /
**Home Screen Display**
- **Description**: Display application main screen
- **Response**: HTML (index.html)
- **Purpose**: Landing page, application overview display

### GET /scene
**Scene List Screen Display**
- **Description**: Display available scene list and narrative creation interface
- **Response**: HTML (scene_list.html)
- **Features**: 
  - Scene thumbnail display
  - Drag & drop narrative creation
  - Swiper slideshow generation

### GET /scene/{scene_id}
**Scene Detail Screen Display**
- **Parameters**: 
  - `scene_id` (string): Scene ID (e.g., "20250804_230555")
- **Description**: Display detailed information for specific scene
- **Response**: HTML (scene_detail.html)
- **Features**: List and preview all files within scene

### GET /narratives
**Narrative List Screen Display**
- **Description**: Display management screen for created narratives
- **Response**: HTML (narrative_list.html)
- **Features**: 
  - Narrative list display
  - View, download, delete operations

### GET /gallery
**Image Gallery Screen Display**
- **Description**: Display list of image files in shared folder
- **Response**: HTML (gallery.html)
- **Features**: Image preview, metadata display

## 🎬 Scene Related API

### GET /scene/{scene_id}/data
**Scene Integrated Data Retrieval**
```json
{
  "id": "20250804_230555",
  "hasImage": true,
  "image": "/scene/20250804_230555/file/image_20250804_230537.png",
  "text": "Curly brown hair danced as she ran...",
  "hasTTS": true,
  "hasMusic": true
}
```
- **Purpose**: Data retrieval for Swiper slideshow generation
- **Processing**: 
  1. Scan files in scene directory
  2. Check existence of various media files
  3. Load text content
  4. Return integrated JSON data

### GET /scene/{scene_id}/file/{filename}
**Scene File Delivery**
- **Description**: Deliver specific file within scene
- **Purpose**: Access to image, audio, text files
- **Example**: `/scene/20250804_230555/file/image_20250804_230537.png`

### GET /scene/{scene_id}/tts
**TTS Audio File Delivery**
- **Description**: Deliver scene's TTS (Text-to-Speech) audio
- **Format**: WAV, MP3
- **Purpose**: Audio playback in slideshow

### GET /scene/{scene_id}/music
**BGM Music File Delivery**
- **Description**: Deliver scene's BGM music file
- **Format**: WAV, MP3
- **Purpose**: Background music playback in slideshow

### GET /scene/{scene_id}/sis/{filename}
**SIS (formerly SIS) Structure Data Retrieval**
```json
{
  "structure": {
    "elements": [...],
    "relationships": [...]
  }
}
```
- **Description**: Return scene's SIS (Semantic Interface Structure; formerly SIS) data in JSON format
- **Purpose**: Analysis and display of structured story information

### GET /scene/{scene_id}/text/{filename}
**Text Content Retrieval**
- **Description**: Return scene's text file content
- **Format**: Plain text
- **Purpose**: Individual text content display and editing

## 📄 Narrative Related API

### POST /narrative/save
**Narrative Save (HTML Export)**

**Request**:
```json
{
  "narrative": [
    {
      "id": "20250804_230555",
      "hasImage": true,
      "image": "/scene/20250804_230555/file/image_20250804_230537.png",
      "text": "Scene description...",
      "hasTTS": true,
      "hasMusic": true
    }
  ],
  "title": "My First Narrative"
}
```

**Response**:
```json
{
  "success": true,
  "filename": "My First Narrative.html",
  "path": "/shared/narrative/My First Narrative.html"
}
```

**Processing Flow**:
1. Validate narrative data
2. Base64 encode each scene's assets (images, audio)
3. Generate self-contained HTML file
4. Save to shared/narrative/ directory
5. Return success response

**Error Example**:
```json
{
  "error": "No narrative data provided"
}
```

### GET /narrative/view/{filename}
**Narrative HTML File Delivery**
- **Description**: Deliver generated narrative HTML file
- **Purpose**: Browser display, download
- **Example**: `/narrative/view/My First Narrative.html`

### POST /narrative/delete/{filename}
**Narrative Deletion**

**Response**:
```json
{
  "success": true,
  "message": "Narrative deleted successfully"
}
```

**Error Example**:
```json
{
  "error": "File not found"
}
```

## 🖼️ Static File Delivery

### GET /shared/{filename}
**Shared Image File Delivery**
- **Description**: Deliver image files from shared/ directory
- **Purpose**: Gallery display, thumbnail display
- **Supported Extensions**: .png, .jpg, .jpeg, .gif, .bmp, .webp

## 🔧 Internal Processing Functions

### get_image_files()
```python
def get_image_files():
    """Retrieve image file list from shared folder"""
    # 1. Scan shared/ directory
    # 2. Filter by image extensions
    # 3. Get file information (size, modification date)
    # 4. Sort by modification date descending
    return image_files
```

### generate_narrative_html()
```python
def generate_narrative_html(narrative_data, title):
    """Generate self-contained HTML"""
    # 1. Base64 conversion of each scene's assets
    # 2. Build HTML template
    # 3. Embed CSS and JavaScript
    # 4. Integrate audio data
    return html_content
```

### generate_slides_html()
```python
def generate_slides_html(narrative_data):
    """Generate HTML for Swiper slides"""
    # 1. Convert scene data to slide format
    # 2. Proper placement of images and text
    # 3. Set data attributes
    return slides_html
```

## 🔍 Error Codes & Status

### Success Responses
- **200 OK**: Normal processing completed
- **201 Created**: Resource creation successful (narrative save)

### Client Errors
- **400 Bad Request**: Invalid request data
- **404 Not Found**: Specified resource not found

### Server Errors
- **500 Internal Server Error**: Internal server error

## 🔄 Real-time Updates

### Frontend State Management
```javascript
// Narrative creation state
let narrativeScenes = [];           // Selected scene array
let currentNarrativeData = [];      // Generated narrative data

// Audio playback state  
let currentTTSAudio = null;         // Currently playing TTS audio
let currentMusicAudio = null;       // Currently playing BGM music
let hasUserInteracted = false;      // User interaction flag
```

### AJAX Communication Patterns
```javascript
// Narrative save
const response = await fetch('/narrative/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ narrative: data, title: title })
});

// Narrative delete
const response = await fetch(`/narrative/delete/${filename}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
});
```

## 🎵 Audio Processing System

### Audio Playback Flow
```javascript
function playSlideAudio(slideIndex) {
    stopAllAudio();                           // Stop previous audio
    
    if (hasTTS && embeddedAudio[sceneId].tts) {
        playTTSAudio(sceneId);               // Play TTS immediately
    }
    
    if (hasMusic && embeddedAudio[sceneId].music) {
        setTimeout(() => {                    // Delayed BGM playback
            playMusicAudio(sceneId);
        }, hasTTS ? 1000 : 0);
    }
}
```

### Base64 Audio Data Format
```javascript
const embeddedAudio = {
    "scene_id": {
        "tts": "data:audio/wav;base64,UklGRi4AAABXQVZFZm10...",
        "music": "data:audio/wav;base64,UklGRi4AAABXQVZFZm10..."
    }
};
```

---

**Last Updated**: August 6, 2025  
**API Version**: 1.0.0
