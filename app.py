import os
import cv2
import uuid
import gc
import numpy as np
from flask import Flask, render_template, request, jsonify, url_for

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FOLDER = os.path.join(BASE_DIR, 'static', 'output')
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app.config['MAX_CONTENT_LENGTH'] = 128 * 1024 * 1024

def decode_image_from_stream(file_stream):
    file_bytes = np.frombuffer(file_stream.read(), np.uint8)
    if len(file_bytes) == 0:
        return None
    return cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

def resize_image_if_large(img, max_width=1000):
    h, w = img.shape[:2]
    if w <= max_width:
        return img
    scale = max_width / float(w)
    new_size = (max_width, int(h * scale))
    return cv2.resize(img, new_size, interpolation=cv2.INTER_AREA)

def crop_black_borders(img):
    """Finds the maximum rectangular region inside the panorama that contains no black borders."""
    # 1. Create a 10-pixel black border around the image to isolate inner contours from edge boundaries
    stitched = cv2.copyMakeBorder(img, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=[0, 0, 0])
    
    # 2. Convert to grayscale and threshold to create a binary mask (white where pixels exist, black otherwise)
    gray = cv2.cvtColor(stitched, cv2.COLOR_BGR2GRAY)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY)[1]
    
    # 3. Find external contours of the stitched image shape
    contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return img # Fallback if no contour found
        
    c = max(contours, key=cv2.contourArea)
    
    # 4. Allocate a mask for the largest bounding box
    mask = np.zeros(thresh.shape, dtype="uint8")
    (x, y, w, h) = cv2.boundingRect(c)
    cv2.rectangle(mask, (x, y), (x + w, y + h), 255, -1)
    
    # 5. Iteratively erode the mask until it fits completely inside the valid panorama region
    min_rect = mask.copy()
    sub = mask.copy()
    
    while cv2.countNonZero(sub) > 0:
        min_rect = cv2.erode(min_rect, None)
        sub = cv2.subtract(min_rect, thresh)
        
    # 6. Extract the final clean bounding box coordinates and crop
    contours, _ = cv2.findContours(min_rect.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return img
        
    c = max(contours, key=cv2.contourArea)
    (x, y, w, h) = cv2.boundingRect(c)
    
    # Crop out the final image, compensating for the original 10px pad
    cropped = stitched[y:y + h, x:x + w]
    return cropped

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/stitch', methods=['POST'])
def stitch_images():
    if 'images' not in request.files:
        return jsonify({'error': 'No images uploaded'}), 400
        
    uploaded_files = request.files.getlist('images')
    if len(uploaded_files) < 2:
        return jsonify({'error': 'Please select at least 2 overlapping images.'}), 400
        
    session_id = uuid.uuid4().hex
    cv_images = []
    
    try:
        for file in uploaded_files:
            if file.filename == '':
                continue
            img = decode_image_from_stream(file)
            if img is not None:
                img_resized = resize_image_if_large(img, max_width=1000)
                cv_images.append(img_resized)
                
        if len(cv_images) < 2:
            return jsonify({'error': 'One or more image files were invalid or unreadable.'}), 400
            
        stitcher = cv2.Stitcher_create(cv2.Stitcher_PANORAMA)
        status, stitched_img = stitcher.stitch(cv_images)
        
        if status == cv2.Stitcher_OK:
            # ---> APPLY THE AUTOMATIC CROPPING HERE <---
            final_img = crop_black_borders(stitched_img)
            
            output_filename = f'panorama_{session_id}.jpg'
            output_path = os.path.join(OUTPUT_FOLDER, output_filename)
            cv2.imwrite(output_path, final_img, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            
            image_url = url_for('static', filename=f'output/{output_filename}')
            return jsonify({'success': True, 'image_url': image_url})
        else:
            error_messages = {
                1: "Need more overlapping images or sharper detail (ERR_NEED_MORE_IMGS).",
                2: "Homography estimation failed. Camera rotation matrix couldn't resolve (ERR_HOMOGRAPHY_EST_FAIL).",
                3: "Camera parameters adjustment failed (ERR_CAMERA_PARAMS_ADJUST_FAIL)."
            }
            msg = error_messages.get(status, "Unknown stitching error.")
            return jsonify({'error': f"Stitching failed: {msg}"}), 400
            
    except Exception as e:
        return jsonify({'error': f"Server exception caught: {str(e)}"}), 500
    finally:
        del cv_images
        gc.collect()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
