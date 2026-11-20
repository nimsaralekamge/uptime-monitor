# ==========================================
# Stage 1: Builder (installs dependencies)
# ==========================================
FROM python:3.12-slim AS builder

WORKDIR /build

# Install Python dependencies into an isolated virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# ==========================================
# Stage 2: Runtime (lean, non-root production image)
# ==========================================
FROM python:3.12-slim AS runtime

WORKDIR /app

# Create a dedicated non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy ONLY the pre-built virtual environment from Stage 1
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source code
COPY ./app ./app

# Hand ownership to non-root user and switch to it
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Run Uvicorn ASGI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]