document.addEventListener("DOMContentLoaded", () => {
    const avatarInput = document.getElementById("profile-avatar-input");
    const removeInput = document.getElementById("remove-avatar-input");
    const preview = document.querySelector(".avatar-preview");
    const previewImage = document.getElementById("avatar-preview-image");
    const fallback = document.getElementById("avatar-preview-fallback");
    const removeButton = document.getElementById("remove-avatar-button");
    const status = document.getElementById("avatar-change-status");

    if (!avatarInput || !removeInput || !preview || !previewImage || !fallback || !status) {
        return;
    }

    let selectedImageUrl = null;
    const hasCurrentPhoto = preview.dataset.hasPhoto === "true";

    const showFallback = () => {
        previewImage.hidden = true;
        fallback.hidden = false;
    };

    const showCurrentPhoto = () => {
        if (hasCurrentPhoto) {
            previewImage.hidden = false;
        } else {
            showFallback();
        }
    };

    const releaseSelectedImage = () => {
        if (selectedImageUrl) {
            URL.revokeObjectURL(selectedImageUrl);
            selectedImageUrl = null;
        }
    };

    if (removeButton) {
        removeButton.addEventListener("click", () => {
            const removalPending = removeInput.checked;
            removeInput.checked = !removalPending;
            removeButton.setAttribute("aria-pressed", String(!removalPending));

            if (removalPending) {
                removeButton.textContent = "Remove photo";
                status.textContent = "";
                showCurrentPhoto();
                return;
            }

            avatarInput.value = "";
            releaseSelectedImage();
            removeButton.textContent = "Undo removal";
            status.textContent = "Photo removal is pending until you save changes.";
            showFallback();
        });
    }

    avatarInput.addEventListener("change", () => {
        const selectedFile = avatarInput.files && avatarInput.files[0];
        if (!selectedFile) {
            return;
        }

        if (!selectedFile.type.startsWith("image/")) {
            status.textContent = "That file is not an image. Choose an image file.";
            return;
        }

        removeInput.checked = false;
        if (removeButton) {
            removeButton.textContent = "Remove photo";
            removeButton.setAttribute("aria-pressed", "false");
        }

        releaseSelectedImage();
        selectedImageUrl = URL.createObjectURL(selectedFile);
        previewImage.src = selectedImageUrl;
        previewImage.alt = "Selected profile photo preview";
        previewImage.hidden = false;
        fallback.hidden = true;
        status.textContent = "New photo selected. Save changes to apply it.";
    });

    if (removeInput.checked) {
        showFallback();
    } else if (!hasCurrentPhoto) {
        showFallback();
    }

    window.addEventListener("pagehide", releaseSelectedImage, { once: true });
});
