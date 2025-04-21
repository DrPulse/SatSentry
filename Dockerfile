## ------------------------------- Builder Stage ------------------------------ ##
FROM --platform=$BUILDPLATFORM python:3.12-alpine AS builder

# Install build dependencies, then install Python dependencies
# and remove build dependencies to keep the image small
RUN apk add --no-cache --virtual .build-deps \
    gcc \
    musl-dev \
    libffi-dev \
    && apk del .build-deps

# Download the latest installer, install it and then remove it
ADD https://astral.sh/uv/install.sh /install.sh
RUN chmod -R 655 /install.sh && /install.sh && rm /install.sh

# Set up the UV environment path correctly
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

COPY ./pyproject.toml .

RUN uv sync --no-dev --no-install-project

## ------------------------------- Production Stage ------------------------------ ##
FROM python:3.12-alpine AS production

WORKDIR /app

COPY /app ./app
COPY main.py .
COPY --from=builder /app/.venv .venv

# Create directories and set permissions for the non-root user
RUN mkdir -p /app/data /app/logs && chown -R 1000:1000 /app/data /app/logs
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 5000
USER 1000

CMD ["python3", "main.py"]
