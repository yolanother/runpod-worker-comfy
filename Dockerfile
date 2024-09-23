# Stage 1: Base image with common dependencies
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04 as base

# Prevents prompts from packages asking for user input during installation
ENV DEBIAN_FRONTEND=noninteractive
# Prefer binary wheels over source distributions for faster pip installations
ENV PIP_PREFER_BINARY=1
# Ensures output from python is printed immediately to the terminal without buffering
ENV PYTHONUNBUFFERED=1 

# Install Python, git and other necessary tools
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    git \
    wget

# Clean up to reduce image size
RUN apt-get autoremove -y && apt-get clean -y && rm -rf /var/lib/apt/lists/*

# Install ComfyUI dependencies
RUN pip3 install --upgrade --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
RUN pip3 install -U xformers --index-url https://download.pytorch.org/whl/cu121

# Install runpod
RUN pip3 install runpod requests

# Support for the network volume
ADD src/extra_model_paths.yaml ./

# Go back to the root
WORKDIR /

# Add the start and the handler
ADD src/start.sh src/rp_handler.py test_input.json src/setup.sh ./
RUN chmod +x /start.sh
RUN chmod +x /setup.sh

RUN git clone https://github.com/comfyanonymous/ComfyUI.git /comfyui
RUN rm -rf /comfyui/custom_nodes
RUN git clone https://github.com/yolanother/comfyui-custom-nodes /comfyui/custom_nodes

WORKDIR /comfyui/custom_nodes
RUN git submodule update --init --recursive

WORKDIR /comfyui
RUN pip3 install ninja
RUN pip3 install --upgrade --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
RUN pip3 install -U xformers --index-url https://download.pytorch.org/whl/cu121
RUN pip3 install -r requirements.txt
RUN for dir in */; do \
    if [ ! -f "${dir}requirements.txt" ]; then \
      continue \
    fi \
    log "==> ${dir}" \
    cd ${dir} \
    pip3 install --upgrade -r requirements.txt \
    cd .. \
  done

RUN pip3 install llama-cpp-python

WORKDIR /comfyui
RUN rm -rf models
RUN ln -s /runpod-volume/models

# Stage 3: Final image
FROM base as final

# Start the container
CMD /start.sh