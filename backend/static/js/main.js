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
        translatingFileName.textContent = uploadedFileName.textContent;
  
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
                // Simulate translation process
                simulateTranslationProgress(data);
            } else {
                alert('Failed to start translation');
            }
        })
        .catch(error => console.error('Error:', error));
    }
  
    function simulateTranslationProgress(data) {
        let currentPage = 0;
        let totalPages = data.total_pages;
        let progressPercentage = 35; // Start at 35%
        const progressStep = (65 / totalPages); // Remaining 65% distributed across total pages
  
        // Set the initial width of the progress bar to 35%
        progressBar.style.width = `${progressPercentage}%`;
  
        // Simulate translation progress
        translationInterval = setInterval(() => {
            currentPage += 1;
            translatedPages.textContent = `${currentPage}/${totalPages} страниц`;
  
            // Increase the progress bar width based on progress step
            progressPercentage += progressStep;
            progressBar.style.width = `${progressPercentage}%`;
  
            if (currentPage === totalPages) {
                clearInterval(translationInterval);
                // Simulate translation complete
                setTimeout(() => {
                    showTranslationComplete(data.translated_file_url);
                }, 1000);
            }
        }, 500); // Simulate page translation every 0.5 seconds
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
