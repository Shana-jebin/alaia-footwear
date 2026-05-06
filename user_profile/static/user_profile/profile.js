
// Edit Mode Toggle


function enterEditMode() {
    const display = document.getElementById("displayMode");
    const edit = document.getElementById("editMode");

    if (display && edit) {
        display.style.display = "none";
        edit.style.display = "block";
    }
}

function cancelEditMode() {
    const display = document.getElementById("displayMode");
    const edit = document.getElementById("editMode");

    if (display && edit) {
        display.style.display = "block";
        edit.style.display = "none";
    }
}


// Profile Image Preview (Frontend Only)


function triggerImageUpload() {
    const input = document.getElementById("imageUpload");
    if (input) {
        input.click();
    }
}

function handleImageUpload(event) {
    const file = event.target.files[0];

    if (file) {
        const reader = new FileReader();

        reader.onload = function (e) {
            const img = document.getElementById("profileImg");
            if (img) {
                img.src = e.target.result;
            }
        };

        reader.readAsDataURL(file);
        
        // Auto-submit the form to save the image immediately
        setTimeout(() => {
            const form = document.getElementById("profileForm");
            if (form) {
                form.submit();
            }
        }, 100);
    }
}

// Notification System 

function showNotification(message, type = "success") {
    const notification = document.getElementById("notification");
    const notificationText = document.getElementById("notificationText");

    if (notification && notificationText) {
        notificationText.textContent = message;
        notification.className = `notification show ${type}`;

        setTimeout(() => {
            notification.classList.remove("show");
        }, 3000);
    }
}


// Safe Image Fallback


document.addEventListener("DOMContentLoaded", function () {
    const profileImg = document.getElementById("profileImg");

    if (profileImg) {
        profileImg.onerror = function () {
            this.src =
                "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='400'%3E%3Crect fill='%23e5e5e5' width='400' height='400'/%3E%3Ctext fill='%23404040' font-size='120' x='50%25' y='50%25' text-anchor='middle' dy='.3em'%3EUser%3C/text%3E%3C/svg%3E";
        };
    }
    
    // Form Validation
    const profileForm = document.getElementById("profileForm");
    if (profileForm) {
        profileForm.addEventListener("submit", function(e) {
            const firstName = document.getElementById("firstNameInput")?.value.trim();
            const lastName = document.getElementById("lastNameInput")?.value.trim();
            const email = document.getElementById("emailInput")?.value.trim();
            const phone = document.getElementById("phoneInput")?.value.trim();
            
            // Helper functions for inline errors
            const clearErrors = () => {
                ['firstName', 'lastName', 'email', 'phone'].forEach(prefix => {
                    const errorEl = document.getElementById(prefix + 'Error');
                    const inputEl = document.getElementById(prefix + 'Input');
                    if (errorEl) { errorEl.style.display = 'none'; errorEl.textContent = ''; }
                    if (inputEl) { inputEl.style.borderColor = ''; }
                });
            };
            const showError = (prefix, msg) => {
                const errorEl = document.getElementById(prefix + 'Error');
                const inputEl = document.getElementById(prefix + 'Input');
                if (errorEl) { errorEl.style.display = 'block'; errorEl.textContent = msg; }
                if (inputEl) { inputEl.style.borderColor = 'var(--red)'; }
            };
            
            clearErrors();
            let hasError = false;
            
            const nameRegex = /^[A-Za-z\s]+$/;
            
            if (!firstName) {
                showError('firstName', "First name is required.");
                hasError = true;
            } else if (firstName.length < 2) {
                showError('firstName', "First name must be at least 2 characters.");
                hasError = true;
            } else if (!nameRegex.test(firstName)) {
                showError('firstName', "First name can only contain letters.");
                hasError = true;
            }
            
            if (!lastName) {
                showError('lastName', "Last name is required.");
                hasError = true;
            } else if (!nameRegex.test(lastName)) {
                showError('lastName', "Last name can only contain letters.");
                hasError = true;
            }
            
            if (!email) {
                showError('email', "Email address is required.");
                hasError = true;
            } else {
                const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                if (!emailRegex.test(email)) {
                    showError('email', "Please enter a valid email address.");
                    hasError = true;
                }
            }
            
            if (phone && phone !== "") {
                const phoneRegex = /^[0-9]{10}$/;
                if (!phoneRegex.test(phone)) {
                    showError('phone', "Phone number must be exactly 10 digits.");
                    hasError = true;
                }
            }
            
            if (hasError) {
                e.preventDefault();
            }
        });
    }
});

