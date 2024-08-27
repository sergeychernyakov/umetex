// src/static/js/main.js

document.addEventListener('DOMContentLoaded', function() {
    const fileInput = document.getElementById('fileInput');
    const fileInputButton = document.getElementById('fileInputButton');
    const uploadContainer = document.getElementById('uploadContainer');
    const uploadForm = document.getElementById('translationForm');
    const fileUploadBlock = document.getElementById('fileUploadBlock');
    const fileUploadedBlock = document.getElementById('fileUploadedBlock');
    const translatingBlock = document.getElementById('translatingBlock');
    const fileTranslatedBlock = document.getElementById('fileTranslatedBlock');
    const uploadedFileName = document.getElementById('uploadedFileName');
    const translatingFileName = document.getElementById('translatingFileName');
    const downloadLink = document.getElementById('downloadLink');
    const translatedPages = document.getElementById('translatedPages');
    const progressBar = document.getElementById('progressBar');

    let translationInterval;

    // Utility function to toggle visibility of blocks with animation
    function toggleVisibility(visibleBlock) {
        const blocks = [fileUploadBlock, fileUploadedBlock, translatingBlock, fileTranslatedBlock];
        blocks.forEach(block => {
            if (block === visibleBlock) {
                block.classList.add('active');
            } else {
                block.classList.remove('active');
            }
        });
    }

    // Utility function to truncate long file names
    function truncateFileName(fileName) {
        const maxLength = 15; // Set max length for file name
        const extLength = 7;  // Set length to keep from the end, including the extension
        if (fileName.length > maxLength) {
            const start = fileName.substring(0, maxLength - extLength);
            const end = fileName.substring(fileName.length - extLength);
            return `${start}..${end}`;
        }
        return fileName;
    }

    // Drag-and-drop functionality
    uploadContainer.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadContainer.classList.add('drag-over');
    });

    uploadContainer.addEventListener('dragleave', () => {
        uploadContainer.classList.remove('drag-over');
    });

    uploadContainer.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadContainer.classList.remove('drag-over');

        const files = e.dataTransfer.files;
        if (files.length) {
            fileInput.files = files;
            handleFileSelect(files[0]);
        }
    });

    fileInputButton.addEventListener('click', function(event) {
        fileInput.click();
    });

    // Handle file selection via input or drag-and-drop
    fileInput.addEventListener('change', function(event) {
        let file = event.target.files[0];
        if (file) {
            handleFileSelect(file);
        }
    });

    function handleFileSelect(file) {
        // Update the file name in the UI
        uploadedFileName.textContent = file.name;

        // Hide the file upload block and show the file uploaded block
        toggleVisibility(fileUploadedBlock);
    }

    // Handle form submission when the "Начать перевод" button is clicked
    window.startTranslation = function() {
        const formData = new FormData(uploadForm);

        // Hide the file uploaded block, show translating block
        toggleVisibility(translatingBlock);
        translatingFileName.textContent = truncateFileName(uploadedFileName.textContent);
    
        fetch(uploadForm.action, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': formData.get('csrfmiddlewaretoken'),
            },
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                startRealTranslationProgress(data);
            } else {
                alert('Failed to start translation');
            }
        })
        .catch(error => console.error('Error:', error));
    }

    function startRealTranslationProgress(data) {
        let currentPage = 0;
        let totalPages = 1;
        let documentId = data.document_id;
        translationInterval = setInterval(() => {
            fetch(`/progress/${documentId}/`)
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        console.error(data.error);
                        clearInterval(translationInterval);
                    } else {
                        currentPage = data.current_page;
                        totalPages = data.total_pages;
    
                        translatedPages.textContent = `${currentPage}/${totalPages}`;
                        let progressPercentage = 40 + ((currentPage / totalPages) * 60);
                        progressBar.style.width = `${progressPercentage}%`;
    
                        if (currentPage >= totalPages) {
                            clearInterval(translationInterval);
                            showTranslationComplete(`/media/${documentId}/translations/translated_${documentId}.pdf`);
                        }
                    }
                })
                .catch(error => {
                    console.error('Error fetching progress:', error);
                    clearInterval(translationInterval);
                });
        }, 1000); // Check every second
    }

    function showTranslationComplete(translated_file_url) {
        toggleVisibility(fileTranslatedBlock);
        downloadLink.href = translated_file_url;
        startFileDownload(translated_file_url);
    }

    function startFileDownload(fileUrl) {
        var link = document.createElement('a');
        link.href = fileUrl;
        link.download = '';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    // Cancel translation (reset everything)
    window.cancelTranslation = function() {
        clearInterval(translationInterval);
        resetUpload();
    }

    // Reset the form and blocks
    window.resetUpload = function() {
        toggleVisibility(fileUploadBlock);
        uploadForm.reset();
    }

    // Initialize with the upload block visible
    toggleVisibility(fileUploadBlock);
});
