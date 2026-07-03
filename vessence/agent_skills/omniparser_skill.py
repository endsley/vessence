import os
import sys
import subprocess
import base64
import io
from PIL import Image
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jane.config import VAULT_DIR, VESSENCE_HOME
from agent_skills.omniparser_output import (
    parsed_result_from_output as _parsed_result_from_output,
)

class OmniParserService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OmniParserService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self.venv_python = os.path.join(VESSENCE_HOME, "omniparser_venv", "bin", "python")
        self.api_script = os.path.join(VESSENCE_HOME, 'omniparser', 'parse_screen_api.py')
        self._initialized = True

    def parse_screenshot(self, image_path_or_bytes):
        """
        Parses a screenshot by calling the OmniParser API script in its dedicated venv.
        Returns:
        - labeled_image: Base64 string of the image with labels
        - parsed_content: A string representation of detected elements
        - elements: Raw list of detected elements
        """
        temp_image = None
        if isinstance(image_path_or_bytes, str):
            image_path = image_path_or_bytes
        else:
            # Save bytes to a temporary file
            image_path = os.path.join(VAULT_DIR, 'tmp_screenshot.png')
            image = Image.open(io.BytesIO(image_path_or_bytes))
            image.save(image_path)
            temp_image = image_path
            
        try:
            # Call the subprocess
            # We use the absolute path to the venv python and the script
            result = subprocess.run(
                [self.venv_python, self.api_script, image_path],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Find the JSON part of the output (skip warnings/logs)
            output_str = result.stdout
            return _parsed_result_from_output(output_str)
                
        except subprocess.CalledProcessError as e:
            raise Exception(f"OmniParser subprocess failed: {e.stderr}")
        finally:
            # Optional: clean up temp image
            # if temp_image and os.path.exists(temp_image):
            #     os.remove(temp_image)
            pass

if __name__ == "__main__":
    # Quick test
    service = OmniParserService()
    test_img = os.path.join(os.path.expanduser("~"), "Downloads", "amber.png")
    if os.path.exists(test_img):
        print(f"Testing OmniParserService with {test_img}...")
        try:
            results = service.parse_screenshot(test_img)
            print(f"Detected {len(results['elements'])} elements.")
            print("Successfully parsed screenshot.")
        except Exception as e:
            print(f"Error during test: {e}")
    else:
        print("Test image not found.")
