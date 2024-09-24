# Stage 1: Base image with common dependencies
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04 as base

# Environment configurations
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_PREFER_BINARY=1 \
    PYTHONUNBUFFERED=1 

# Install Python, git, and other necessary tools
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    python3-venv \
    git \
    wget && \
    apt-get autoremove -y && apt-get clean -y && rm -rf /var/lib/apt/lists/*

# Install runpod dependencies
RUN pip3 install runpod requests

# Add configuration files and scripts
ADD src/extra_model_paths.yaml ./ 
ADD src/start.sh src/rp_handler.py test_input.json src/setup.sh ./
RUN chmod +x /start.sh /setup.sh

RUN /setup.sh

# Stage 2: Final image
FROM base as final

# Set working directory and start the container
WORKDIR /comfyui
CMD ["/start.sh"]
