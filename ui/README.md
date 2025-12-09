# GeNarrative UI - README

## 🎬 GeNarrative UI

**Multimedia Storytelling Web Application**

GeNarrative UI is a web application for creating, managing, and sharing interactive narratives that combine multimedia elements (images, audio, text).

![GeNarrative Demo](https://via.placeholder.com/800x400/007bff/ffffff?text=GeNarrative+UI+Demo)

## ✨ Key Features

### 🎥 Scene Management
- Visual scene list display with thumbnails
- Detailed scene information view (images, text, audio, structure data)
- Real-time file information updates

### 🎭 Narrative Creation
- **Drag & Drop Interface**: Intuitive scene arrangement
- **Swiper.js Slideshow**: Smooth multimedia presentation
- **Synchronized Audio Playback**: TTS (Text-to-Speech) + BGM music auto-sync
- **Responsive Design**: Desktop, tablet, and smartphone support

### 💾 HTML Export
- **Self-contained HTML**: All assets embedded as Base64
- **Offline Playback**: No internet connection required
- **Cross-platform**: Playable on any device
- **Professional Quality**: High-quality slideshow output

### 📊 Narrative Management
- Created narrative list display
- View, download, and delete functionality
- File information display (size, creation date)

## 🚀 Quick Start

### Prerequisites
- Docker Desktop
- Git

### Installation & Startup
```bash
# Clone repository
git clone <repository_url>
cd GeNarrative-dev

# Start application
docker-compose up -d

# Access in browser
open http://localhost:5000
```

### Basic Usage

1. **Scene Overview**: Visit `/scene` to view scene list
2. **Narrative Creation**: Drag & drop scenes to timeline
3. **Slideshow Generation**: Click "Generate Narrative" for multimedia display
4. **Save**: Export as HTML file with "Save Narrative"
5. **Management**: Use `/narratives` to manage created narratives

## 📱 Screenshots

### Scene List & Narrative Creation Interface
```
┌─────────────────────────────────────────────────┐
│ 🎬 Available Scenes                             │
├─────────────────────────────────────────────────┤
│ [Scene1] [Scene2] [Scene3] [Scene4] [Scene5]   │
│    📷       📷       📷       📷       📷      │
├─────────────────────────────────────────────────┤
│ 🎭 Create Narrative                             │
│ ┌─────────────────────────────────────────────┐ │
│ │ Drop scenes here to create your narrative   │ │
│ └─────────────────────────────────────────────┘ │
│ [Generate Narrative] [Clear All]                │
└─────────────────────────────────────────────────┘
```

### Generated Slideshow
```
┌─────────────────────────────────────────────────┐
│ 📖 Generated Narrative              [Save] [✕] │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌─────────┐  │  Scene Description Text        │
│  │  📷     │  │  Lorem ipsum dolor sit amet,   │
│  │ Image   │  │  consectetur adipiscing elit.  │
│  │         │  │  Sed do eiusmod tempor...      │
│  └─────────┘  │                                │
│               │                     [1 / 5]    │
├─────────────────────────────────────────────────┤
│ 🔊 [Auto Play: ON] [Stop Audio] [Play Current] │
└─────────────────────────────────────────────────┘
```

## 🏗️ Technology Stack

### Backend
- **Flask** (Python 3.9+) - Web Framework
- **Docker** - Containerization

### Frontend  
- **HTML5** - Semantic Markup
- **CSS3** - Modern Styling (Grid, Flexbox)
- **JavaScript ES6** - Interactive Features
- **Swiper.js** - Slideshow Library

### Data Processing
- **Base64 Encoding** - Asset Embedding
- **JSON** - Data Exchange Format
- **File I/O** - Local File System Operations

## 📁 Project Structure

```
GeNarrative-dev/
├── ui/                           # Main Web Application
│   ├── app/
│   │   ├── main.py              # 🎯 Flask Application
│   │   ├── templates/           # 📄 HTML Templates
│   │   │   ├── base.html        # Base Layout
│   │   │   ├── scene_list.html  # Scene List & Creation
│   │   │   ├── narrative_list.html # Narrative Management
│   │   │   └── scene_detail.html # Scene Details
│   │   └── static/              # Static Files
│   ├── Dockerfile               # Container Configuration
│   └── requirements.txt         # Python Dependencies
├── shared/                      # Shared Data
│   ├── scene/                   # Scene Files
│   │   └── {scene_id}/
│   │       ├── image_*.png      # Scene Images
│   │       ├── text_*.txt       # Text Content
│   │       ├── tts_*.wav        # TTS Audio
│   │       ├── music_*.wav      # BGM Music
│   │       └── sis_*.json       # Structure Data
│   └── narrative/               # Generated Narratives
│       └── *.html               # Exported HTML
└── docker-compose.yml           # Development Environment
```

## 🔧 Developer Information

### LLM/SD/Music/TTS 設定（Ollama を使用）

本プロジェクトでは、テキストおよび各種プロンプト生成に LLM サーバー（Ollama）を使用します。画像生成は Stable Diffusion、音楽は Music サーバー、音声は TTS サーバーを使用します。

- 既定のサービス URI（docker-compose 利用時）
	- Ollama: http://ollama:11434
	- Stable Diffusion: http://sd:7860
	- Music: http://music:5003
	- TTS: http://tts:5002

これらは `ui/scripts/common_base.py` の `APIConfig` で既定設定されています。

#### モデル設定（Ollama）

- 使用モデルは `APIConfig.ollama_model`（既定: `gemma3:4b-it-qat`）で切り替え可能です。
- 変更方法の例：
	- コードから `APIConfig(ollama_model="llama3.1:8b-instruct-q4_K_M")` を渡す
	- テストスクリプトでは `make_api_config()` を編集することで変更可能

#### ローカルホストでの実行

Docker Compose の代わりにホスト上のサービスへ接続したい場合は、環境変数 `GENARRATIVE_USE_LOCALHOST=1` を設定すると、以下の URI に切り替わります。

- Ollama: http://localhost:11434
- SD: http://localhost:7860
- Music: http://localhost:5003
- TTS: http://localhost:5002

テストランナー `ui/scripts/test/run_unified_tests.py` はこの環境変数を自動認識します。

> Windows PowerShell で環境変数を一時的に設定する場合は `$env:GENARRATIVE_USE_LOCALHOST = "1"` を利用してください。

### Development Environment Setup
```bash
# Start development mode (hot reload enabled)
docker-compose up -d

# Monitor logs
docker-compose logs -f ui

# Access container shell
docker-compose exec ui bash
```

### API Endpoints

#### Scene Related
- `GET /scene` - Scene list display
- `GET /scene/{scene_id}` - Scene details
- `GET /scene/{scene_id}/data` - Scene integrated data
- `GET /scene/{scene_id}/tts` - TTS audio delivery
- `GET /scene/{scene_id}/music` - BGM music delivery

#### Narrative Related
- `GET /narratives` - Narrative list
- `POST /narrative/save` - Narrative save
- `GET /narrative/view/{filename}` - Narrative display
- `POST /narrative/delete/{filename}` - Narrative deletion

### Detailed Documentation
- 📋 [Specification](SPECIFICATION.md) - Complete technical specification
- 📡 [API Reference](API_REFERENCE.md) - All API endpoint details
- 🛠️ [Development Guide](DEVELOPMENT.md) - Development procedures & best practices
  
### テストレポート（統合 E2E）

`ui/scripts/test/run_unified_tests.py` を実行すると、以下をまとめた HTML レポート（`ui/scripts/test/unified_test_report.html`）を生成します。

- Content→SIS 抽出（画像・テキスト）
- SIS→コンテンツ生成（画像プロンプト+画像、音楽プロンプト+音楽、物語テキスト+TTS）
- 入力ファイル、生成プロンプト内容、生成物のプレビュー
- すべての成果物は `ui/scripts/test/test_result_<timestamp>/` に保存されます

Docker Compose 環境内（UI コンテナ）での実行を推奨します。

## 🎯 Use Cases & Examples

### Education
- **Language Learning**: Multimedia materials combining images, audio, and text
- **History Lessons**: Timeline multimedia presentations of events
- **Science Explanation**: Visual and audio explanation of experiment processes

### Business
- **Product Introduction**: Integrated presentations with feature explanations and demos
- **Training Materials**: Interactive training content
- **Proposals**: Visually impactful project proposals

### Creative
- **Digital Storytelling**: Artist portfolio presentations
- **Travel Journals**: Experience sharing with photos, audio, and text
- **Portfolio**: Background and production process explanations

## 🔒 Security & Privacy

### Data Processing
- **Local Processing**: All processing completed in local environment
- **No External Transmission**: No user data sent externally
- **File Validation**: Only safe file extensions processed

### Generated Files
- **Self-contained HTML**: Safe without external dependencies
- **Embedded Assets**: Complete containment in Base64 format
- **XSS Protection**: Proper escaping measures

## 🤝 Contributing

### Bug Reports
When you find an issue, please create an Issue with the following information:
- Environment (OS, Browser)
- Reproduction steps
- Expected behavior
- Actual behavior
- Error messages (if any)

### Feature Requests
New feature suggestions are welcome:
- Specific use cases
- Detailed expected behavior
- Implementation priority

### Development Participation
Pull requests are welcome:
1. Create a fork
2. Create feature branch
3. Implement and test changes
4. Create pull request

## 📄 License

[MIT License](LICENSE) - Free to use, modify, and distribute

## 🙏 Acknowledgments

- **Swiper.js** - Excellent slideshow library
- **Flask** - Simple and powerful web framework
- **Docker** - Consistent development environment

---

**Created by**: GitHub Copilot  
**Version**: 1.0.0  
**Last Updated**: August 6, 2025

**📧 Support**: For technical questions and support, please use [Issues](../../issues).

---

⭐ **If this project helped you, please give it a star!**

## 📝 UI Notes

- The "Available Samplers" info panel on `/servers/image` has been removed by request. The sampler dropdown for txt2img tests remains available and continues to use the backend-provided `samplers_info` for options.
- The "Memory Usage" panel on `/servers/image` has also been removed by request.
- The "GPU Information" panel on `/servers/text` has been removed by request. The simple "GPU Available" indicator remains.
- The "Health Check Response" panel on `/servers/text` has been removed by request. Status refresh remains available via the button.
- The "Text Prompt" section was removed from the scene detail page (`/scene/<scene_id>`). Image/Music prompts remain.

