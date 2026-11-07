# Multi-arch compatible Debian image with pre-installed security tools
FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.title="CyGuide" \
      org.opencontainers.image.description="TUI-Based Guided Cybersecurity Learning and Terminal Tool Orchestration Platform" \
      org.opencontainers.image.url="https://github.com/h45sh/cyguide" \
      org.opencontainers.image.source="https://github.com/h45sh/cyguide"

# Prevent interactive prompts during apt installs
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    TERM=xterm-256color \
    CYGUIDE_DATA_DIR=/root/.cyguide

# Install core security tool dependencies:
# - nmap, gobuster, nikto, whois: standard CLI tool adapters
# - libxml-writer-perl: required by nikto for XML output
# - ca-certificates, curl, unzip: needed for secure asset downloading
RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap \
    gobuster \
    nikto \
    whois \
    libxml-writer-perl \
    ca-certificates \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install subfinder binary from official ProjectDiscovery release
ARG SUBFINDER_VERSION=2.6.6
RUN ARCH="$(dpkg --print-architecture)" && \
    case "${ARCH}" in \
        amd64) SUBFINDER_ARCH="amd64" ;; \
        arm64) SUBFINDER_ARCH="arm64" ;; \
        *) echo "Unsupported architecture for subfinder: ${ARCH}" && exit 1 ;; \
    esac && \
    curl -fsSL "https://github.com/projectdiscovery/subfinder/releases/download/v${SUBFINDER_VERSION}/subfinder_${SUBFINDER_VERSION}_linux_${SUBFINDER_ARCH}.zip" -o /tmp/subfinder.zip && \
    unzip -q /tmp/subfinder.zip -d /tmp/subfinder_bin && \
    mv /tmp/subfinder_bin/subfinder /usr/local/bin/subfinder && \
    chmod +x /usr/local/bin/subfinder && \
    rm -rf /tmp/subfinder*

# Set working directory for package installation
WORKDIR /app

# Copy packaging manifests and source code
COPY pyproject.toml requirements.txt ./
COPY cyguide/ cyguide/
COPY tools/ tools/
COPY README.md LICENSE ./

# Install CyGuide in the container
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Create persistent storage directory for sessions and configurations
RUN mkdir -p /root/.cyguide
VOLUME ["/root/.cyguide"]

WORKDIR /root

ENTRYPOINT ["cyg"]
