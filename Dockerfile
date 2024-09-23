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
    git \
    wget && \
    apt-get autoremove -y && apt-get clean -y && rm -rf /var/lib/apt/lists/*

# Add configuration files and scripts
ADD src/extra_model_paths.yaml ./ 
ADD src/start.sh src/rp_handler.py test_input.json src/setup.sh ./
RUN chmod +x /start.sh /setup.sh

# Clone ComfyUI and custom nodes repositories
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /comfyui && \
    rm -rf /comfyui/custom_nodes && \
    git clone https://github.com/yolanother/comfyui-custom-nodes /comfyui/custom_nodes

# Initialize submodules for custom nodes
WORKDIR /comfyui/custom_nodes
RUN git submodule update --init --recursive

# Install ComfyUI dependencies and custom node requirements
WORKDIR /comfyui
RUN pip3 install ninja && \
    pip3 install --upgrade --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 && \
    pip3 install -U xformers --index-url https://download.pytorch.org/whl/cu121 && \
    pip3 install runpod requests llama-cpp-python && \
    pip3 install -r requirements.txt && \
    for dir in */; do \
        if [ -f "${dir}requirements.txt" ]; then \
            echo "==> Installing requirements in ${dir}"; \
            pip3 install --upgrade -r ${dir}requirements.txt; \
        fi; \
    done

# Link models directory to network volume
RUN rm -rf models && ln -s /runpod-volume/models /comfyui/models

# Stage 2: Final image
FROM base as final

# Set working directory and start the container
WORKDIR /comfyui
CMD ["/start.sh"]
