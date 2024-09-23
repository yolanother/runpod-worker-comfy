#!/usr/bin/env bash
log() {
    if [ -z "$VIRTUAL_ENV" ]; then
        venv_display="[ComfyUI Init] "
    else
        venv_display="[ComfyUI Init - $(basename $VIRTUAL_ENV)]"
    fi

    message="$venv_display $1"
    length=${#message}

    # Print the box
    printf "+%*s+\n" $((length + 2)) | tr ' ' '-'
    printf "| %s |\n" "$message"
    printf "+%*s+\n" $((length + 2)) | tr ' ' '-'
}

# Use libtcmalloc for better memory management
TCMALLOC="$(ldconfig -p | grep -Po "libtcmalloc.so.\d" | head -n 1)"
export LD_PRELOAD="${TCMALLOC}"

# If /comfyui/models is not already a symlink and is a directory remove it. Also ensure that /runpod-volume/models exists
if [ -d "/runpod-volume/models" ] && [ -d "/comfyui/models" ] && [ ! -L "/comfyui/models" ]; then
    echo "runpod-worker-comfy: Removing /comfyui/models directory and creating symlink to /runpod-volume/models"
    rm -rf /comfyui/models
    cd /comfyui && ln -s /runpod-volume/models models
fi

# Print a list of all custom_nodes in the /comfyui/custom_nodes directory
if [ -d "/comfyui/custom_nodes" ]; then
    echo "runpod-worker-comfy: Custom Nodes:"
    ls /comfyui/custom_nodes
else
    echo "runpod-worker-comfy: No custom nodes found"
fi

# List all of the models in /comfyui/models/checkpoints
if [ -d "/comfyui/models/checkpoints" ]; then
    echo "runpod-worker-comfy: Models:"
    ls /comfyui/models/checkpoints
else
    echo "runpod-worker-comfy: No models found"
fi

cd /comfyui/custom_nodes
# Open each directory and run pip33 intall --upgrade -r requirements.txt
for dir in */; do
    # if requirements.txt exists install it
    if [ ! -f "${dir}requirements.txt" ]; then
        log "--> No requirements.txt found for ${dir}"
        continue
    fi
    log "==> ${dir}"
    cd ${dir}
    pip3 install --upgrade -r requirements.txt || { log "ERROR: Failed to install custom node dependencies for ${dir}"; }
    cd ..
done

# Temporary debugging to validate build contents
ls -lah /comfyui/*.py
ls -lah /comfyui/custom_nodes/

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