# 1. Use a secure, lightweight Python base
FROM python:3.11-slim

# 2. Set Environment Variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Security: Add a non-privileged user
RUN useradd -m sandboxuser
WORKDIR /workspace

# 4. Install Minimal Scientific Stack
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    numpy \
    pandas \
    matplotlib

# 5. Security: Set up directories and ensure sandboxuser owns them
RUN mkdir -p /workspace/input /workspace/output && \
    chown -R sandboxuser:sandboxuser /workspace

# 6. Final Security Lockdown
USER sandboxuser

# 7. Default Command (Safe fallback)
CMD ["python", "--version"]
