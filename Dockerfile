FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Copy dependency mappings
COPY requirements.txt .

# Install packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy all the contents including main.py and index.html
COPY . .

# Set PORT environment variable to port 8080 (Cloud Run expected port)
ENV PORT=8080
EXPOSE 8080

# Spin up Uvicorn listening on 0.0.0.0 and mapping to the dynamic PORT
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
