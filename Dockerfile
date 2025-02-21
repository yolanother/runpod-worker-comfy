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
    python3.11 \
    python3-pip \
    libgl1 \
    libglib2.0-0 \
    git \
    wget \
    curl \
    fuse-overlayfs

# Clean up to reduce image size
RUN apt-get autoremove -y && apt-get clean -y && rm -rf /var/lib/apt/lists/*

# Install ComfyUI dependencies
RUN pip3 install --upgrade --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

RUN pip3 install ninja
RUN pip3 install --no-cache-dir importlib_metadata
RUN pip3 install --no-cache-dir huggingface_hub
RUN pip3 install --no-cache-dir scipy
RUN pip3 install --no-cache-dir 'opencv-python>=4.7.0.72'
RUN pip3 install --no-cache-dir filelock
RUN pip3 install --no-cache-dir numpy
RUN pip3 install --no-cache-dir Pillow
RUN pip3 install --no-cache-dir einops
RUN pip3 install --no-cache-dir pyyaml
RUN pip3 install --no-cache-dir scikit-image
RUN pip3 install --no-cache-dir python-dateutil
RUN pip3 install --no-cache-dir mediapipe
RUN pip3 install --no-cache-dir svglib
RUN pip3 install --no-cache-dir fvcore
RUN pip3 install --no-cache-dir yapf
RUN pip3 install --no-cache-dir omegaconf
RUN pip3 install --no-cache-dir ftfy
RUN pip3 install --no-cache-dir addict
RUN pip3 install --no-cache-dir yacs
RUN pip3 install --no-cache-dir 'trimesh[easy]'
RUN pip3 install --no-cache-dir albumentations
RUN pip3 install --no-cache-dir scikit-learn
RUN pip3 install --no-cache-dir matplotlib
RUN pip3 install --no-cache-dir 'numpy<2'
RUN pip3 install --no-cache-dir accelerate
RUN pip3 install --no-cache-dir diffusers
RUN pip3 install --no-cache-dir OpenEXR
RUN pip3 install --no-cache-dir Imath
RUN pip3 install --no-cache-dir pathlib
RUN pip3 install --no-cache-dir timm
RUN pip3 install --no-cache-dir deepdiff
RUN pip3 install --no-cache-dir surrealist
RUN pip3 install --no-cache-dir aisuite
RUN pip3 install --no-cache-dir ollama
RUN pip3 install --no-cache-dir git+https://github.com/deepseek-ai/Janus.git
RUN pip3 install --no-cache-dir groq
RUN pip3 install --no-cache-dir openai

# Install runpod
RUN pip3 install runpod requests websocket-client

ADD "https://api.github.com/repos/comfyanonymous/ComfyUI/commits?per_page=1" latest_commit
# Clone ComfyUI repository
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /comfyui

ADD "https://api.github.com/repos/yolanother/comfyui-custom-nodes/commits?per_page=1" latest_commit
RUN echo "Installing custom nodes..."
RUN rm -rf /comfyui/custom_nodes
RUN git clone https://github.com/yolanother/comfyui-custom-nodes /comfyui/custom_nodes

WORKDIR /comfyui/custom_nodes
RUN git submodule update --init --recursive
RUN rm -rf /comfyui/custom_nodes/.git

RUN df -h

WORKDIR /comfyui/custom_nodes
RUN for dir in */; do \
        if [ -f "${dir}requirements.txt" ]; then \
            echo "==> Installing requirements in ${dir}"; \
            pip3 install --upgrade -r ${dir}requirements.txt --extra-index-url https://download.pytorch.org/whl/cu121 ; \
        fi; \
    done

WORKDIR /comfyui

RUN df -h
RUN pip3 install --upgrade -r requirements.txt

RUN df -h

# Support for the network volume
# ADD src/extra_model_paths.yaml ./

# Go back to the root
WORKDIR /

# Add the start and the handler
ADD src/start.sh src/rp_handler.py src/comfy_websockets.py src/comfyclient.py test_input.json src/install-ollama.sh ./
RUN chmod +x /start.sh
RUN chmod +x /install-ollama.sh
RUN /install-ollama.sh

RUN df -h

# Stage 3: Final image
FROM base as final

RUN python3 -u /comfyui/main.py --cpu --quick-test-for-ci

# Ensure the Ollama service starts
CMD /start.sh