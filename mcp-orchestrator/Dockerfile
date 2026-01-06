FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for runtime data
RUN mkdir -p /app/state /app/logs /app/plans

# Expose port
EXPOSE 8000

# Run the server
CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]
