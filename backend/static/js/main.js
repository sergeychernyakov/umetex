document.addEventListener('DOMContentLoaded', function() {
    const fileInput = document.getElementById('fileInput');
    const uploadContainer = document.getElementById('uploadContainer');

    fileInput.addEventListener('change', function(event) {
        let file = event.target.files[0];
        
        if (file) {
            uploadContainer.classList.add('selected');
        } else {
            uploadContainer.classList.remove('selected');
        }
    });
});