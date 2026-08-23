# Use an official lightweight Python image.
FROM python:3.12-slim

# Set environment variables to optimize Python for containers
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Set the working directory in the container
WORKDIR /app

# Install dependencies from pyproject.toml (cached layer)
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir .

# Copy only the runtime code required by the job.
COPY main.py ./main.py
COPY pipelines ./pipelines

# Create a non-privileged user for better security and switch to it
RUN useradd -u 10001 appuser && chown -R appuser /app
USER appuser

# Command to execute the job
CMD ["python", "main.py"]
