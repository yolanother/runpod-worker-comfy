# Fail on error
set -e

cd /comfyui/custom_nodes
# Open each directory and run pip3 intall --upgrade -r requirements.txt
for dir in */; do
    echo "runpod-worker-comfy: Installing custom node dependencies for ${dir}"
    cd ${dir}
    pip3 install --upgrade -r requirements.txt
    cd ..
done

echo "runpod-worker-comfy: Installing custom node dependencies for Upgraded-Depth-Anything-V2"
# if /comfyui/custom_nodes/Upgraded-Depth-Anything-V2 exists, make the one_click_instal.sh executable and run it in that directory
if [ -d "/comfyui/custom_nodes/Upgraded-Depth-Anything-V2" ]; then
    chmod +x /comfyui/custom_nodes/Upgraded-Depth-Anything-V2/one_click_install.sh
    /comfyui/custom_nodes/Upgraded-Depth-Anything-V2/one_click_install.sh
fi

# Install ComfyUI dependencies
echo "runpod-worker-comfy: Installing ComfyUI dependencies"
pip3 install --upgrade --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip3 install --upgrade -r requirements.txt

pip3 install -U xformers --index-url https://download.pytorch.org/whl/cu121
