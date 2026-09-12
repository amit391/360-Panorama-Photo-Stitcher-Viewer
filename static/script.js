const dropZone = document.getElementById('drop-zone');
        const fileInput = document.getElementById('image-input');
        const previewGallery = document.getElementById('preview-gallery');
        const uploadForm = document.getElementById('upload-form');
        const errorMsg = document.getElementById('error-msg');
        const loadingMsg = document.getElementById('loading-msg');
        const viewerContainer = document.getElementById('viewer-container');
        const downloadLink = document.getElementById('download-link');
        const submitBtn = document.getElementById('submit-btn');
        const clearBtn = document.getElementById('clear-btn');

        // Global variables tracking live objects and viewer instances
        let pViewer = null;
        
        /* 
           Store assets structured as an array of objects to maintain absolute mapping control:
           { id: cryptoGeneratedId, file: FileObject, currentOrder: numericIndex }
        */
        let selectedFiles = [];

        // Let clicking anywhere on the zone trigger the hidden file element picker
        dropZone.addEventListener('click', (e) => {
            if (e.target.tagName !== 'BUTTON' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'SELECT') {
                fileInput.click();
            }
        });

        // Handle styling changes for visual drag indicators
        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                dropZone.classList.add('dragover');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                dropZone.classList.remove('dragover');
            }, false);
        });

        // Handle files dropped directly into the zone
        dropZone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            if(files.length > 0) {
                appendFilesToState(files);
            }
        });

        // Handle standard system selection via browse click
        fileInput.addEventListener('change', (e) => {
            appendFilesToState(e.target.files);
        });

        // Ingests raw files, converts them to structurally tracked objects, and appends them
        function appendFilesToState(fileList) {
            const validFiles = Array.from(fileList).filter(file => file.type.startsWith('image/'));
            
            validFiles.forEach(file => {
                const uniqueId = self.crypto.randomUUID ? self.crypto.randomUUID() : Math.random().toString(36).substring(2, 11);
                selectedFiles.push({
                    id: uniqueId,
                    file: file,
                    currentOrder: selectedFiles.length // Default assignment matches arriving index loop execution
                });
            });

            renderInterfaceGallery();
        }

        // Complete UI Render engine managing individual structural assets 
        function renderInterfaceGallery() {
            previewGallery.innerHTML = ''; 
            errorMsg.textContent = '';
            
            if(selectedFiles.length < 2) {
                errorMsg.textContent = "Please pick at least 2 overlapping images to stitch.";
                // Clear input form mirror states if user strips items below two
                if (selectedFiles.length === 0) {
                    fileInput.value = '';
                }
                return;
            }

            // Always organize UI representation using current user configuration settings
            selectedFiles.sort((a, b) => a.currentOrder - b.currentOrder);

            selectedFiles.forEach((fileWrapper, idx) => {
                const reader = new FileReader();
                reader.onload = function(e) {
                    const item = document.createElement('div');
                    item.classList.add('preview-item');
                    item.setAttribute('data-id', fileWrapper.id);
                    
                    // 1. Setup cross icon button for real time single deletion
                    const removeBtn = document.createElement('button');
                    removeBtn.type = 'button';
                    removeBtn.classList.add('remove-btn');
                    removeBtn.innerHTML = '&times;';
                    removeBtn.title = 'Remove image';
                    
                    removeBtn.addEventListener('click', (evt) => {
                        evt.stopPropagation(); // Block drop zone input triggering loops
                        removeIndividualImage(fileWrapper.id);
                    });
                    item.appendChild(removeBtn);

                    // 2. Setup image source matrix
                    const img = document.createElement('img');
                    img.src = e.target.result;
                    item.appendChild(img);

                    // 3. Add dropdown select area component matching current count size boundaries
                    const selectorContainer = document.createElement('div');
                    selectorContainer.classList.add('order-selector-container');

                    const select = document.createElement('select');
                    select.classList.add('order-select');

                    for (let i = 0; i < selectedFiles.length; i++) {
                        const opt = document.createElement('option');
                        opt.value = i;
                        opt.textContent = `Position ${i + 1}`;
                        if (i === idx) opt.selected = true;
                        select.appendChild(opt);
                    }

                    // Watch dropdown changes to handle real-time position updates
                    select.addEventListener('change', (evt) => {
                        const targetedPosition = parseInt(evt.target.value, 10);
                        updateImageSequenceIndex(fileWrapper.id, targetedPosition);
                    });

                    selectorContainer.appendChild(select);
                    item.appendChild(selectorContainer);
                    previewGallery.appendChild(item);
                }
                reader.readAsDataURL(fileWrapper.file);
            });
        }

        // Drops target asset out of global tracking matrix and re-normalizes structural sequential indices
        function removeIndividualImage(targetId) {
            const indexToRemove = selectedFiles.findIndex(item => item.id === targetId);
            if (indexToRemove === -1) return;

            const removedOrder = selectedFiles[indexToRemove].currentOrder;

            // Remove target element completely
            selectedFiles.splice(indexToRemove, 1);

            // Close sequence loops so indexes decrease cleanly above deleted value bounds
            selectedFiles.forEach(item => {
                if (item.currentOrder > removedOrder) {
                    item.currentOrder--;
                }
            });

            // Update DOM representation matrix layout states dynamically
            renderInterfaceGallery();
        }

        // Sequence swapping logic shifts elements correctly inside our tracking arrays
        function updateImageSequenceIndex(targetId, newPosition) {
            const targetItem = selectedFiles.find(item => item.id === targetId);
            if (!targetItem) return;

            const oldPosition = targetItem.currentOrder;
            if (oldPosition === newPosition) return;

            // Shift other elements cleanly based on the move direction
            selectedFiles.forEach(item => {
                if (item.id !== targetId) {
                    if (oldPosition < newPosition) {
                        if (item.currentOrder > oldPosition && item.currentOrder <= newPosition) {
                            item.currentOrder--;
                        }
                    } else {
                        if (item.currentOrder >= newPosition && item.currentOrder < oldPosition) {
                            item.currentOrder++;
                        }
                    }
                }
            });

            targetItem.currentOrder = newPosition;
            renderInterfaceGallery(); 
        }

        // Dedicated Clear and Reset interface workflow routine
        function resetInterface() {
            selectedFiles = [];
            fileInput.value = '';
            previewGallery.innerHTML = '';
            errorMsg.textContent = '';
            loadingMsg.style.display = 'none';
            viewerContainer.style.display = 'none';
            submitBtn.disabled = false;
            
            if (pViewer) {
                pViewer.destroy();
                pViewer = null;
            }
        }

        clearBtn.addEventListener('click', resetInterface);

        // Form Submission and Server Fetch Orchestration
        uploadForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            errorMsg.textContent = '';
            
            if (selectedFiles.length < 2) {
                errorMsg.textContent = "Please select at least 2 images before submitting.";
                return;
            }

            loadingMsg.style.display = 'block';
            viewerContainer.style.display = 'none';
            submitBtn.disabled = true;

            // Enforce explicit structural sorting index matches before payload packaging
            selectedFiles.sort((a, b) => a.currentOrder - b.currentOrder);

            const formData = new FormData();
            selectedFiles.forEach(item => {
                formData.append('images', item.file);
            });

            try {
                const response = await fetch('/stitch', {
                    method: 'POST',
                    body: formData
                });
                
                const responseText = await response.text();
                let result;

                try {
                    result = JSON.parse(responseText);
                } catch (jsonErr) {
                    // If the server sent back an HTML crash stack trace, extract it or log it
                    console.error("Server crashed and returned HTML instead of JSON:", responseText);
                    throw new Error("Server processing error. Please check Render dashboard logs for detail.");
                }
                //const result = await response.json();
                if (!response.ok || !result.success) {
                    throw new Error(result.error || 'An unexpected stitching error occurred.');
                }
                downloadLink.href = result.image_url;
                viewerContainer.style.display = 'block';

                if (pViewer) {
                    pViewer.destroy();
                }
                pViewer = pannellum.viewer('panorama-viewer', {
                    type: 'equirectangular',
                    panorama: result.image_url,
                    autoLoad: true,
                    compass: false
                });
                } catch (err) {
                    errorMsg.textContent = err.message;
                    } finally {
                        loadingMsg.style.display = 'none';
                        submitBtn.disabled = false;
                    }
                });
