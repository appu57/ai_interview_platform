FROM python:3.11-slim

# Install system dependencies required for audio processing and networking
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libffi-dev \
    libssl-dev \
    portaudio19-dev \
    libasound2-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency file and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project directory
COPY . .

# Expose the port your FastAPI/Agent uses (e.g., 8000)
EXPOSE 8000

# Start the agent worker
CMD ["python", "audio_pipeline.py"]