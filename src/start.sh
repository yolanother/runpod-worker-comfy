#!/usr/bin/env bash

# Use libtcmalloc for better memory management
TCMALLOC="$(ldconfig -p | grep -Po "libtcmalloc.so.\d" | head -n 1)"
export LD_PRELOAD="${TCMALLOC}"

# If /comfyui/models is not already a symlink and is a directory remove it. Also ensure that /runpod-volume/models exists
if [ -d "/runpod-volume/models" ] && [ -d "/comfyui/models" ] && [ ! -L "/comfyui/models" ]; then
    echo "runpod-worker-comfy: Removing /comfyui/models directory and creating symlink to /runpod-volume/models"
    rm -rf /comfyui/models
    cd /comfyui && ln -s /runpod-volume/models models
fi

# if /comfyui/custom_nodes is not already a symlink and is a directory remove it.
if [ -d "/runpod-volume/models" ] && [ -d "/comfyui/custom_nodes" ] && [ ! -L "/comfyui/custom_nodes" ]; then
    echo "runpod-worker-comfy: Removing /comfyui/custom_nodes directory and creating symlink to /runpod-volume/custom_nodes"
    rm -rf /comfyui/custom_nodes
    cd /comfyui && ln -s /runpod-volume/custom_nodes custom_nodes
fi

cd /comfyui
find ./ -name requirements.txt -exec sh -c 'echo "$1 $(dirname "$1")"; cd "$(dirname "$1")" && pip install -r requirements.txt' _ {} \;

# Serve the API and don't shutdown the container
if [ "$SERVE_API_LOCALLY" == "true" ]; then
    echo "runpod-worker-comfy: Starting ComfyUI"
    python3 /comfyui/main.py --disable-auto-launch --disable-metadata --listen &

    echo "runpod-worker-comfy: Starting RunPod Handler"
    python3 -u /rp_handler.py --rp_serve_api --rp_api_host=0.0.0.0
else
    echo "runpod-worker-comfy: Starting ComfyUI"
    python3 /comfyui/main.py --disable-auto-launch --disable-metadata &

    echo "runpod-worker-comfy: Starting RunPod Handler"
    python3 -u /rp_handler.py
fi