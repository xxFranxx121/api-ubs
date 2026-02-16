
# Use an official Python runtime as a parent image
# Switched to bullseye because buster repositories are archived/unstable
FROM python:3.9-slim-bullseye

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Install Chrome and dependencies
# Added cleanup to reduce image size
RUN apt-get update && apt-get install -y wget gnupg2 unzip \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the port
EXPOSE 8000

# Command to run the application
# Use PORT environment variable if available (Railway provides it)
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
