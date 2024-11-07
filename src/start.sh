#!/usr/bin/env bash

# Use libtcmalloc for better memory management
TCMALLOC="$(ldconfig -p | grep -Po "libtcmalloc.so.\d" | head -n 1)"
export LD_PRELOAD="${TCMALLOC}"

mkdir -p /tmp/ckpts

# If /comfyui/models is not already a symlink and is a directory remove it. Also ensure that /runpod-volume/models exists
if [ -d "/runpod-volume/models" ] && [ -d "/comfyui/models" ] && [ ! -L "/comfyui/models" ]; then
    echo "runpod-worker-comfy: Removing /comfyui/models directory and creating symlink to /runpod-volume/models"
    rm -rf /comfyui/models
    cd /comfyui && ln -s /runpod-volume/models models
fi

if [ -d "/runpod-volume/custom_nodes/comfyui_controlnet_aux/ckpts" && [ ! -L "/comfyui/custom_nodes/comfyui_controlnet_aux/ckpts" ]]; then
    echo "runpod-worker-comfy: Removing /comfyui/custom_nodes/comfyui_controlnet_aux/ckpts directory and creating symlink to /runpod-volume/custom_nodes/comfyui_controlnet_aux/ckpts"
    rm -rf /comfyui/custom_nodes/comfyui_controlnet_aux/ckpts
    cd /comfyui/custom_nodes/comfyui_controlnet_aux && ln -s /runpod-volume/custom_nodes/comfyui_controlnet_aux/ckpts ckpts
fi

# Serve the API and don't shutdown the container
if [ "$SERVE_API_LOCALLY" == "true" ]; then
    echo "runpod-worker-comfy: Starting ComfyUI"
    python3 /comfyui/main.py --disable-auto-launch --listen &

    echo "runpod-worker-comfy: Starting RunPod Handler"
    python3 -u /rp_handler.py --rp_serve_api --rp_api_host=0.0.0.0
else
    echo "runpod-worker-comfy: Starting ComfyUI"
    python3 /comfyui/main.py --disable-auto-launch &

    echo "runpod-worker-comfy: Starting RunPod Handler"
    python3 -u /rp_handler.py
fi