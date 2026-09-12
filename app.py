import os
import cv2
import uuid
import numpy as np
from flask import Flask, render_template, request, jsonify, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
OUTPUT_FOLDER = os.path.join(BASE_DIR, 'static', 'output')

#UPLOAD_FOLDER = os.path.join('static', 'uploads')
#OUTPUT_FOLDER = os.path.join('static', 'output')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def read_image_with_exif_correction(path):
    """Reads an image file using OpenCV's standard color matrix format."""
    # Note: cv2.imread strips EXIF orientation metadata by default.
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    return img

def resize_image_if_large(img, max_width=1600):
    """Safely reduces image size to prevent OpenCV Out-Of-Memory matrix crashes."""
    h, w = img.shape[:2]
    if w <= max_width:
        return img
    scale = max_width / float(w)
    new_size = (max_width, int(h * scale))
    return cv2.resize(img, new_size, interpolation=cv2.INTER_AREA)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stitch', methods=['POST'])
def stitch_images():
    if 'images' not in request.files:
        return jsonify({'error': 'No images uploaded'}), 400
        
    uploaded_files = request.files.getlist('images')
    if len(uploaded_files) < 2:
        return jsonify({'error': 'Please select at least 2 overlapping images.'}), 400
        
    session_id = uuid.uuid4().hex
    saved_paths = []
    
    try:
        # 1. Save files while explicitly retaining the list input sequence
        for index, file in enumerate(uploaded_files):
            if file.filename == '':
                continue
            safe_name = secure_filename(file.filename)
            # Prepending index first ensures filesystem order naturally follows upload order
            filename = f"{session_id}_{index:03d}_{safe_name}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            saved_paths.append(file_path)

        # 2. Process files into memory matrices sequentially
        cv_images = []
        for path in saved_paths:
            img = read_image_with_exif_correction(path)
            if img is not None:
                img_resized = resize_image_if_large(img, max_width=1600)
                cv_images.append(img_resized)
                
        if len(cv_images) < 2:
            return jsonify({'error': 'One or more image files were invalid or unreadable.'}), 400

        # 3. Initialize and run OpenCV stitching assembly
        stitcher = cv2.Stitcher_create(cv2.Stitcher_PANORAMA)
        status, stitched_img = stitcher.stitch(cv_images)
        
        if status == cv2.Stitcher_OK:
            output_filename = f'panorama_{session_id}.jpg'
            output_path = os.path.join(OUTPUT_FOLDER, output_filename)
            cv2.imwrite(output_path, stitched_img)
            
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
        # 4. Cleanup disk assets immediately after execution completes
        for path in saved_paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass

if __name__ == '__main__':
    # app.run(debug=True)
    # Bind to standard environment ports dynamically assigned by cloud hosting platforms
    port = int(os.environ.get("PORT", 5000))
    # Never run debug=True in production architectures
    app.run(host='0.0.0.0', port=port, debug=False)
