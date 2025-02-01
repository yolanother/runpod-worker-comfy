import websocket
import uuid
import json
import urllib.request
import urllib.parse
import threading

class ComfyClient:
    def __init__(self, server_address="127.0.0.1:8188", timeout=600):
        self.server_address = server_address
        self.ws = None
        self.status_event = threading.Event()
        self.current_status = {"status": "pending", "data": None}
        self.prompt_id = None
        self.client_id = None
        self.lock = threading.Lock()
        self.timeout = timeout
        self.last_event_time = None
        self.outputs = []

    def _on_message(self, ws, message):
        msg = json.loads(message)
        with self.lock:
            self.last_event_time = threading.Event()
        # if msg['type'] is not status, executing, progress, or executed then ignore
        if msg['type'] not in ['status', 'executing', 'progress', 'executed']:
            return
        if msg['type'] == 'executing' and msg['data']['node'] is None:
            queue_remaining = msg['data'].get('status', {}).get('exec_info', {}).get('queue_remaining', 0)
            new_status = "queued" if queue_remaining > 0 else "completed"
            with self.lock:
                self.current_status = {"status": new_status, "data": msg}
                # if completed, add outputs to the self.current_status
                if new_status == "completed":
                    self.current_status["outputs"] = self.outputs
                self.status_event.set()
                if new_status == "completed":
                    self._close_ws()
        elif msg['type'] == 'status' and msg['data'].get('sid') == self.client_id:
            queue_remaining = msg['data'].get('status', {}).get('exec_info', {}).get('queue_remaining', 0)
            new_status = "queued" if queue_remaining > 0 else "completed"
            with self.lock:
                self.current_status = {"status": new_status, "data": msg}
                self.status_event.set()
        else:
            with self.lock:
                if msg['type'] == 'executed':
                    self.outputs.append(msg['data']['output'])
                self.current_status = {"status": "processing", "data": msg}
                self.status_event.set()

    def _on_error(self, ws, error):
        print(f"WebSocket error: {error}")
        with self.lock:
            self.current_status = {"status": "error", "data": str(error)}
            self.status_event.set()
            self._close_ws()

    def _on_close(self, ws, close_status_code, close_msg):
        print("WebSocket closed")

    def _on_open(self, ws):
        print("WebSocket connection opened")

    def _close_ws(self):
        if self.ws:
            self.ws.close()
            self.ws = None

    def submit(self, prompt, client_id=None):
        self.outputs = []
        if client_id is None:
            self.client_id = str(uuid.uuid4())
        else:
            self.client_id = client_id
        
        prompt_payload = {"prompt": prompt, "client_id": self.client_id}
        data = json.dumps(prompt_payload).encode('utf-8')
        req = urllib.request.Request(f"http://{self.server_address}/prompt", data=data)
        try:
            response = json.loads(urllib.request.urlopen(req).read())
            self.prompt_id = response["prompt_id"]
            with self.lock:
                self.last_event_time = threading.Event()
            
            self.ws = websocket.WebSocketApp(
                f"ws://{self.server_address}/ws?clientId={self.client_id}",
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open
            )
            ws_thread = threading.Thread(target=self.ws.run_forever, daemon=True)
            ws_thread.start()
            
            return self.prompt_id
        except Exception as e:
            with self.lock:
                # get the message body from the error
                try:
                    # Read the message as json
                    message = json.loads(e.read())
                except:
                    message = str(e)
                self.current_status = {"status": "fail", "data": message}
                self.status_event.set()
            return None

    def waitForStatus(self):
        if self.is_finished():
            return self.current_status
        self.status_event.clear()
        start_time = threading.Event()
        while True:
            if self.is_finished():
                return self.current_status
            if self.status_event.wait(timeout=1):
                return self.current_status
            if start_time.wait(self.timeout):
                self.current_status = {"status": "timed out", "data": None}
                self._close_ws()
                return self.current_status
    
    def is_finished(self):
        return self.current_status["status"] in ["completed", "error", "fail", "timed out"]

if __name__ == "__main__":
    import random
    client = ComfyClient()
    sample_prompt = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "cfg": 8,
                "denoise": 1,
                "latent_image": ["5", 0],
                "model": ["4", 0],
                "negative": ["7", 0],
                "positive": ["6", 0],
                "sampler_name": "euler",
                "scheduler": "normal",
                "seed": random.randint(0, 1000000),
                "steps": 20
            }
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": 'SD1.5\\Deliberate_v6.safetensors'}
        },
        "5": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 1, "height": 512, "width": 512}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": "masterpiece best quality girl"}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": "bad hands"}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "ComfyUI", "images": ["8", 0]}}
    }

    prompt_id = client.submit(sample_prompt)
    while True:
        status = client.waitForStatus()
        if client.is_finished():
            break
        print(f"Current Status: {status}")
    
    print(f"Finished: {status}")
