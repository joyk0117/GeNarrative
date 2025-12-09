FROM python:3.10

WORKDIR /app

# Install Node.js and ffmpeg (headless; no GTK/WebKit dev packages)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get update && apt-get install -y \
    nodejs \
    ffmpeg \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Node.js dependencies
COPY package.json package-lock.json* ./
RUN npm cache clean --force && npm install --no-package-lock

# Copy application files
COPY app/ ./

# Copy Swiper.js to static folder
RUN mkdir -p static/css static/js \
    && cp node_modules/swiper/swiper-bundle.min.css static/css/ \
    && cp node_modules/swiper/swiper-bundle.min.js static/js/

CMD ["python", "main.py"]