import runpod
from runpod.serverless.utils import rp_upload
import urllib.request
import urllib.parse
import time
import os
import requests
import base64
from io import BytesIO
import websocket
import json
import urllib.request
import urllib.parse
import comfyclient

# Time to wait between API check attempts in milliseconds
COMFY_API_AVAILABLE_INTERVAL_MS = 50
# Maximum number of API check attempts
COMFY_API_AVAILABLE_MAX_RETRIES = 6000
# Time to wait between poll attempts in milliseconds
COMFY_POLLING_INTERVAL_MS = os.environ.get("COMFY_POLLING_INTERVAL_MS", 250)
# Maximum number of poll attempts
COMFY_POLLING_MAX_RETRIES = os.environ.get("COMFY_POLLING_MAX_RETRIES", 500)
# Host where ComfyUI is running
COMFY_HOST = "127.0.0.1:8188"
# Enforce a clean state after each job is done
# see https://docs.runpod.io/docs/handler-additional-controls#refresh-worker
REFRESH_WORKER = os.environ.get("REFRESH_WORKER", "false").lower() == "true"


def validate_input(job_input):
    """
    Validates the input for the handler function.

    Args:
        job_input (dict): The input data to validate.

    Returns:
        tuple: A tuple containing the validated data and an error message, if any.
               The structure is (validated_data, error_message).
    """
    # Validate if job_input is provided
    if job_input is None:
        return None, "Please provide input"

    # Check if input is a string and try to parse it as JSON
    if isinstance(job_input, str):
        try:
            job_input = json.loads(job_input)
        except json.JSONDecodeError:
            return None, "Invalid JSON format in input"

    # Validate 'workflow' in input
    workflow = job_input.get("workflow")
    if workflow is None:
        return None, "Missing 'workflow' parameter"

    # Validate 'images' in input, if provided
    images = job_input.get("images")
    if images is not None:
        if not isinstance(images, list) or not all(
            "name" in image and "image" in image for image in images
        ):
            return (
                None,
                "'images' must be a list of objects with 'name' and 'image' keys",
            )

    # Return validated data and no error
    return {"workflow": workflow, "images": images, "callback": job_input.get("callback", None)}, None


def check_server(url, retries=500, delay=50):
    """
    Check if a server is reachable via HTTP GET request

    Args:
    - url (str): The URL to check
    - retries (int, optional): The number of times to attempt connecting to the server. Default is 50
    - delay (int, optional): The time in milliseconds to wait between retries. Default is 500

    Returns:
    bool: True if the server is reachable within the given number of retries, otherwise False
    """
    
    for i in range(retries):
        try:
            response = requests.get(url)
    
            # If the response status code is 200, the server is up and running
            if response.status_code == 200:
                print(f"runpod-worker-comfy - API is reachable after {(i + 1) * delay} ms.")
                return True
        except requests.RequestException as e:
            # If an exception occurs, the server may not be ready
            pass
    
        # Log message every 5 seconds
        if (i + 1) % (5000 // delay) == 0:
            print("Still waiting on the server to come up...")
    
        # Wait for the specified delay before retrying
        time.sleep(delay / 1000)

    print(
        f"runpod-worker-comfy - Failed to connect to server at {url} after {retries} attempts."
    )
    return False


def upload_images(images):
    """
    Upload a list of base64 encoded images to the ComfyUI server using the /upload/image endpoint.

    Args:
        images (list): A list of dictionaries, each containing the 'name' of the image and the 'image' as a base64 encoded string.
        server_address (str): The address of the ComfyUI server.

    Returns:
        list: A list of responses from the server for each image upload.
    """
    if not images:
        return {"status": "success", "message": "No images to upload", "details": []}

    responses = []
    upload_errors = []

    print(f"runpod-worker-comfy - image(s) upload")

    for image in images:
        name = image["name"]
        image_data = image["image"]
        blob = base64.b64decode(image_data)

        # Prepare the form data
        files = {
            "image": (name, BytesIO(blob), "image/png"),
            "overwrite": (None, "true"),
        }

        # POST request to upload the image
        response = requests.post(f"http://{COMFY_HOST}/upload/image", files=files)
        if response.status_code != 200:
            upload_errors.append(f"Error uploading {name}: {response.text}")
        else:
            responses.append(f"Successfully uploaded {name}")

    if upload_errors:
        print(f"runpod-worker-comfy - image(s) upload with errors")
        return {
            "status": "error",
            "message": "Some images failed to upload",
            "details": upload_errors,
        }

    print(f"runpod-worker-comfy - image(s) upload complete")
    return {
        "status": "success",
        "message": "All images uploaded successfully",
        "details": responses,
    }


def queue_workflow(workflow):
    """
    Queue a workflow to be processed by ComfyUI

    Args:
        workflow (dict): A dictionary containing the workflow to be processed

    Returns:
        dict: The JSON response from ComfyUI after processing the workflow
    """

    # The top level element "prompt" is required by ComfyUI
    data = json.dumps({"prompt": workflow}).encode("utf-8")

    req = urllib.request.Request(f"http://{COMFY_HOST}/prompt", data=data)
    return json.loads(urllib.request.urlopen(req).read())


def get_history(prompt_id):
    """
    Retrieve the history of a given prompt using its ID

    Args:
        prompt_id (str): The ID of the prompt whose history is to be retrieved

    Returns:
        dict: The history of the prompt, containing all the processing steps and results
    """
    with urllib.request.urlopen(f"http://{COMFY_HOST}/history/{prompt_id}") as response:
        return json.loads(response.read())


def base64_encode(img_path):
    """
    Returns base64 encoded image.

    Args:
        img_path (str): The path to the image

    Returns:
        str: The base64 encoded image
    """
    with open(img_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
        return f"{encoded_string}"


def process_output_images(comfy, output_images, job_id):
    """
    This function takes the "outputs" from image generation and the job ID,
    then determines the correct way to return the image, either as a direct URL
    to an AWS S3 bucket or as a base64 encoded string, depending on the
    environment configuration.

    Args:
        outputs (array): A list of file names for output images.
        job_id (str): The unique identifier for the job.

    Returns:
        dict: A dictionary with the status ('success' or 'error') and the message,
              which is either the URL to the image in the AWS S3 bucket or a base64
              encoded string of the image. In case of error, the message details the issue.

    The function works as follows:
    - It first determines the output path for the images from an environment variable,
      defaulting to "/comfyui/output" if not set.
    - It then iterates through the outputs to find the filenames of the generated images.
    - After confirming the existence of the image in the output folder, it checks if the
      AWS S3 bucket is configured via the BUCKET_ENDPOINT_URL environment variable.
    - If AWS S3 is configured, it uploads the image to the bucket and returns the URL.
    - If AWS S3 is not configured, it encodes the image in base64 and returns the string.
    - If the image file does not exist in the output folder, it returns an error status
      with a message indicating the missing image file.
    """

    # The path where ComfyUI stores the generated images
    COMFY_OUTPUT_PATH = os.environ.get("COMFY_OUTPUT_PATH", "/comfyui/output")

    print(f"runpod-worker-comfy - image generation is done")

    encoded_images = []
    for output in comfy.outputs:
        print(f"runpod-worker-comfy - output: {output}")
        if output is None:
            continue
        for image in output['images']:
            if image is None:
                continue
            # if image type is temp then skip
            if image['type'] == 'temp':
                continue
            if os.environ.get("BUCKET_ENDPOINT_URL", False):
                endpoint = os.environ.get("BUCKET_ENDPOINT_URL")
                print(f"runpod-worker-comfy - uploading image: {image['filename']} to {endpoint}")
                output_image = os.path.join(image["subfolder"], image["filename"])
                local_image_path = f"{COMFY_OUTPUT_PATH}/{output_image}"
                # If the file doesn't exist, download it from comfy.get_image(image)
                if not os.path.exists(local_image_path):
                    image_data = comfy.get_image(image)
                    with open(local_image_path, "wb") as f:
                        f.write(image_data)
                # URL to image in AWS S3
                url = rp_upload.upload_image(job_id, local_image_path)
                encoded_images.append({
                    "filename": image['filename'],
                    "url": url,
                    "type": image['type'],
                    "subfolder": image['subfolder']
                })
                print(
                    "runpod-worker-comfy - the image was generated and uploaded to AWS S3 at %s" % url
                )
            else:
                print("runpod-worker-comfy - encoding image: ", image['filename'])
                # Get path by combining output path and the image filename
                output_image = os.path.join(image["subfolder"], image["filename"])
                file_path = f"{COMFY_OUTPUT_PATH}/{output_image}"
                print(f"runpod-worker-comfy - file path: {file_path}")
                # if the file path exists use it
                if os.path.exists(file_path):
                    image_data = open(file_path, "rb").read()
                else:
                    # otherwise, load it from comfy.get_image(image)
                    image_data = comfy.get_image(image)
                
                encoded_images.append(base64.b64encode(image_data).decode("utf-8"))
        
        
    # The image is in the output folder
    
    if encoded_images and len(encoded_images) > 0:
        return {
            "status": "success",
            "message": "Image generated successfully",
            "images": encoded_images,
        }
    else:
        return {
            "status": "success",
            "message": "No images saved."
        }
    
def send_status(validated_data, status):
    if 'status_callback' in validated_data and validated_data["status_callback"] is not None:
        # Send the result to the callback URL
        callback_url = validated_data["status_callback"]
        response = requests.post(callback_url, json=status)
        print(f"runpod-worker-comfy - Callback response: {response.text}")

def send_result_callback(validated_data, result):
    print("runpod-worker-comfy - job completed")
    if 'callback' in validated_data and validated_data["callback"] is not None:
        print(f"runpod-worker-comfy - Sending result to callback URL: {validated_data['callback']}")
        # Send the result to the callback URL
        callback_url = validated_data["callback"]
        response = requests.post(callback_url, json=result)
        print(f"runpod-worker-comfy - Callback response: {response.text}")

def handler(job):
    """
    The main function that handles a job of generating an image.

    This function validates the input, sends a prompt to ComfyUI for processing,
    polls ComfyUI for result, and retrieves generated images.

    Args:
        job (dict): A dictionary containing job details and input parameters.

    Returns:
        dict: A dictionary containing either an error message or a success status with generated images.
    """
    job_input = job["input"]

    # Make sure that the input is valid
    validated_data, error_message = validate_input(job_input)
    if error_message:
        print(f"runpod-worker-comfy - error: {error_message}")
        return {"error": error_message}

    # Extract validated data
    workflow = validated_data["workflow"]
    images = validated_data.get("images")

    # Make sure that the ComfyUI API is available
    check_server(
        f"http://{COMFY_HOST}",
        COMFY_API_AVAILABLE_MAX_RETRIES,
        COMFY_API_AVAILABLE_INTERVAL_MS,
    )

    # Upload images if they exist
    upload_result = upload_images(images)

    if upload_result["status"] == "error":
        return upload_result

    job_id = job["id"];
    client = comfyclient.ComfyClient(COMFY_HOST)
    client.status_change_callback = lambda status: print(f"runpod-worker-comfy - Status Changed => {status}")

    print("runpod-worker-comfy - sending prompt to ComfyUI")
    print(f"runpod-worker-comfy - workflow: {workflow}")

    client.submit(workflow, job_id)
    print ("runpod-worker-comfy - waiting for the job to finish")
    status = client.waitForStatus()
    lastStatus = json.dumps(status)
    while True:
        if client.is_finished():
            break
        strStatus = json.dumps(status)
        if(status != lastStatus):
            print(f"runpod-worker-comfy - Status => {status}")
            send_status(validated_data, status)

        lastStatus = strStatus
            
        time.sleep(0.5)
    
    print(f"runpod-worker-comfy - Finished => {status}")
    
    # if there was an error return  an error result
    if status["status"] == "error":
        send_status(validated_data, status)
        result = {
            "status": "error",
            "message": status['data']['error']['message'],
            "details": status['data']['error']['details']
        }
        send_result_callback(validated_data, result)
        return result

    # Get the generated image and return it as URL in an AWS bucket or as base64
    images_result = process_output_images(client, images, job_id)

    result = {**images_result, "refresh_worker": REFRESH_WORKER}

    send_result_callback(validated_data, result)

    return result


# Start the handler only if this script is run directly
if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
