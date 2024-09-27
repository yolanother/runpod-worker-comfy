# This is an example that uses the websockets api and the SaveImageWebsocket node to get images directly without
# them being saved to disk

import websocket  # NOTE: websocket-client (https://github.com/websocket-client/websocket-client)
import uuid
import json
import urllib.request
import urllib.parse


class ComfyWebsocket:
    def __init__(self, server_address, client_id):
        """
        Initialize a new ComfyWebsocket instance.

        Args:
            self.server_address (str): The address of the server to connect to.
        """
        self.server_address = server_address
        self.client_id = client_id
        self.ws = websocket.WebSocket()
        self.ws.connect("ws://{}/ws?clientId={}".format(self.server_address, self.client_id))

    def queue_prompt(self, prompt):
        """
        Queue a prompt to the server and retrieve the response.

        Args:
          prompt (str): The prompt to be queued.

        Returns:
          dict: The server's response to the queued prompt.
        """
        p = {"prompt": prompt, "self.client_id": self.client_id}
        data = json.dumps(p).encode('utf-8')
        req = urllib.request.Request("http://{}/prompt".format(self.server_address), data=data)
        return json.loads(urllib.request.urlopen(req).read())

    def get_image(self, data={"filename": "", "subfolder": "", "type": ""}):
        """
        Retrieve an image from the server based on the provided data.

        Args:
            data (dict): A dictionary containing the following keys:
                - filename (str): The name of the file to retrieve.
                - subfolder (str): The subfolder where the file is located.
                - type (str): The type of the file.

        Returns:
            bytes: The
            raw image data retrieved from the server.
        """
        url_values = urllib.parse.urlencode(data)
        with urllib.request.urlopen("http://{}/view?{}".format(self.server_address, url_values)) as response:
            return response.read()

    def get_history(self, prompt_id):
        """
        Retrieve the history of a given prompt using its ID

        Args:
        prompt_id (str): The ID of the prompt whose history is to be retrieved

        Returns:
        dict: The history of the prompt, containing all the processing steps and results
        """
        with urllib.request.urlopen(f"http://{self.server_address}/history/{prompt_id}") as response:
            return json.loads(response.read())

    def get_images(self, prompt):
        ws = websocket.WebSocket()
        ws.connect("ws://{}/ws?clientId={}".format(self.server_address, self.client_id))

        try:
            prompt_id = self.queue_prompt(prompt)['prompt_id']
            output_images = {}
            current_node = ""
            while True:
                history = self.get_history(prompt_id)
                if history[prompt_id] is not None:
                    break
                out = ws.recv()
                if isinstance(out, str):
                    message = json.loads(out)
                    if message['type'] == 'executing':
                        data = message['data']
                        if data['prompt_id'] == prompt_id:
                            if data['node'] is None:
                                break  # Execution is done
                            else:
                                current_node = data['node']
                    elif message['type'] == 'error':
                        raise Exception(message['data'])

                else:
                    if current_node == 'save_image_websocket_node':
                        images_output = output_images.get(current_node, [])
                        images_output.append(out[8:])
                        output_images[current_node] = images_output

            history = self.get_history(prompt_id)
            images = []
            # iterate over history[prompt_id]['output'] to get all of the output nodes
            outputs = history[prompt_id]['outputs']
            for node_id in outputs:
                # iterate over the output nodes to get the image data
                for image in outputs[node_id]['images']:
                    if image['type'] == 'output':
                        images.append(image)
        finally:
            ws.close()

        return images


# if Main
if __name__ == "__main__":
    server_address = "127.0.0.1:7861"
    client_id = str(uuid.uuid4())
    comfy = ComfyWebsocket(server_address, client_id)
    prompt = {
        "1": {
            "inputs": {
                "unet_name": "FLUX1/flux1-dev-Q4_K_S.gguf"
            },
            "class_type": "UnetLoaderGGUF"
        },
        "2": {
            "inputs": {
                "clip_name1": "t5xxl_fp16.safetensors",
                "clip_name2": "clip_l.safetensors",
                "type": "flux"
            },
            "class_type": "DualCLIPLoaderGGUF"
        },
        "8": {
            "inputs": {
                "samples": [
                    "11",
                    0
                ],
                "vae": [
                    "9",
                    0
                ]
            },
            "class_type": "VAEDecode"
        },
        "9": {
            "inputs": {
                "vae_name": "FLUX1/ae.sft"
            },
            "class_type": "VAELoader"
        },
        "11": {
            "inputs": {
                "noise": [
                    "13",
                    0
                ],
                "guider": [
                    "15",
                    0
                ],
                "sampler": [
                    "14",
                    0
                ],
                "sigmas": [
                    "16",
                    0
                ],
                "latent_image": [
                    "12",
                    0
                ]
            },
            "class_type": "SamplerCustomAdvanced"
        },
        "12": {
            "inputs": {
                "width": 1920,
                "height": 1080,
                "batch_size": 1
            },
            "class_type": "EmptyLatentImage"
        },
        "13": {
            "inputs": {
                "noise_seed": 106559586841938
            },
            "class_type": "RandomNoise"
        },
        "14": {
            "inputs": {
                "sampler_name": "dpmpp_2m"
            },
            "class_type": "KSamplerSelect"
        },
        "15": {
            "inputs": {
                "model": [
                    "1",
                    0
                ],
                "conditioning": [
                    "18",
                    0
                ]
            },
            "class_type": "BasicGuider"
        },
        "16": {
            "inputs": {
                "scheduler": "sgm_uniform",
                "steps": 20,
                "denoise": 1,
                "model": [
                    "1",
                    0
                ]
            },
            "class_type": "BasicScheduler"
        },
        "17": {
            "inputs": {
                "filename_prefix": "ComfyUI",
                "images": [
                    "8",
                    0
                ]
            },
            "class_type": "SaveImage"
        },
        "18": {
            "inputs": {
                "clip_l": "",
                "t5xxl": "closeup portrait of a sci-fi warrior robot, rusty metal, mech, cinematic, red eyes, dark interior background, movie scene, sharp, rim light, epic, golden hour",
                "guidance": 3.5,
                "clip": [
                    "2",
                    0
                ]
            },
            "class_type": "CLIPTextEncodeFlux"
        },
        "19": {
            "inputs": {
                "preprocessor": "Metric3D-DepthMapPreprocessor",
                "resolution": 512,
                "image": [
                    "8",
                    0
                ]
            },
            "class_type": "AIO_Preprocessor"
        },
        "20": {
            "inputs": {
                "images": [
                    "19",
                    0
                ]
            },
            "class_type": "PreviewImage"
        }
    }

    images = comfy.get_images(prompt)

    from PIL import Image
    import io

    for image in images:
        image_data = comfy.get_image(image)
        image = Image.open(io.BytesIO(image_data))
        image.show()
