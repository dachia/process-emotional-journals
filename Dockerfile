FROM python:3.10-slim

# Create a non-root user
RUN useradd -m -s /bin/bash devuser

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt && \
    rm requirements.txt

# Switch to non-root user
USER devuser

# The actual code will be mounted at runtime
CMD ["python", "app.py"]