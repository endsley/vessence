import sys
import os
import time

# Use the OmniParser venv for this test
# This script should be run with: /home/chieh/vessence/omniparser_venv/bin/python
sys.path.append('/home/chieh/vessence')
from agent_skills.omniparser_skill import OmniParserService
from PIL import ImageGrab

def test_omni():
    print("Capturing screenshot...")
    screenshot = ImageGrab.grab()
    screenshot_path = "/home/chieh/ambient/logs/System_log/omni_test_input.png"
    screenshot.save(screenshot_path)
    
    print("Initializing OmniParser Service...")
    start_time = time.time()
    service = OmniParserService()
    init_time = time.time() - start_time
    print(f"Service initialized in {init_time:.2f}s")
    
    print("Parsing screenshot...")
    start_time = time.time()
    result = service.parse_screenshot(screenshot_path)
    parse_time = time.time() - start_time
    print(f"Screenshot parsed in {parse_time:.2f}s")
    
    print("\nDetected Elements (First 5):")
    lines = result['parsed_content'].split('\n')
    for line in lines[:5]:
        print(line)
        
    labeled_img_path = "/home/chieh/ambient/logs/System_log/omni_test_output.png"
    import base64
    from PIL import Image
    import io
    
    img_data = base64.b64decode(result['labeled_image'])
    labeled_img = Image.open(io.BytesIO(img_data))
    labeled_img.save(labeled_img_path)
    print(f"\nLabeled image saved to: {labeled_img_path}")
    print("Test Complete.")

if __name__ == "__main__":
    test_omni()
