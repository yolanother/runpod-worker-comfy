#!/bin/bash

# Exit script on any error
set -e

# Log function to print bold light blue text in a box with the venv name before the command
log() {
    if [ -z "$VIRTUAL_ENV" ]; then
        venv_display="[ComfyUI Installer] "
    else
        venv_display="[ComfyUI Installer - $(basename $VIRTUAL_ENV)]"
    fi

    message="$venv_display $1"
    length=${#message}

    # Print the box
    printf "+%*s+\n" $((length + 2)) | tr ' ' '-'
    printf "| %s |\n" "$message"
    printf "+%*s+\n" $((length + 2)) | tr ' ' '-'
}

if [ ! -d /comfyui ] || [ ! -d /comfyui/.git ]; then
    cd /
    log "Cloning ComfyUI repository..."
    rm -rf /comfyui
    git clone https://github.com/comfyanonymous/ComfyUI.git /comfyui
else
    cd /comfyui
    log "Updating ComfyUI repository in `pwd`..."
    git pull --rebase
fi

log "Updating custom nodes"
rm -rf /comfyui/custom_nodes
git clone https://github.com/yolanother/comfyui-custom-nodes /comfyui/custom_nodes
cd /comfyui/custom_nodes
git submodule update --init --recursive

cd /comfyui

log "Using pip version $(pip3 --version) for python version $(python3 --version)"

log "Installing ninja"
# (Optional) Makes the build much faster
pip3 install ninja

log "Installing PyTorch, TorchVision, and other dependencies..."
pip3 install --upgrade --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

log "Installing xformers..."
pip3 install -U xformers --index-url https://download.pytorch.org/whl/cu121

cd /comfyui
log "Installing Base ComfyUI Python dependencies..."
pip3 install -r requirements.txt || { log "ERROR: Failed to install ComfyUI dependencies from requirements.txt"; exit 1; }

log "Installing custom nodes dependencies..."
cd /comfyui/custom_nodes
# Open each directory and run pip33 intall --upgrade -r requirements.txt
for dir in */; do
    # if requirements.txt exists install it
    if [ ! -f "${dir}requirements.txt" ]; then
        continue
    fi
    log "==> ${dir}"
    cd ${dir}
    pip3 install --upgrade -r requirements.txt || { log "ERROR: Failed to install custom node dependencies for ${dir}"; }
    cd ..
done

log "Installing llama-cpp-python..."
pip3 install llama-cpp-python || { log "ERROR: Failed to install llama-cpp-python"; exit 1; }

log "Setup script completed successfully!"
