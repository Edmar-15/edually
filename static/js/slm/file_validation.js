const MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024;
const ALLOWED_UPLOAD_EXTENSIONS = [".pdf", ".doc", ".docx", ".ppt", ".pptx"];

export function validateUploadFile(file) {
  if (!file) return "Choose a file before uploading.";

  const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!ALLOWED_UPLOAD_EXTENSIONS.includes(extension)) {
    return "Unsupported file type. Please choose a PDF, DOC, DOCX, PPT, or PPTX file.";
  }
  if (file.size > MAX_UPLOAD_SIZE_BYTES) {
    return "File is too large. The maximum allowed size is 10 MB.";
  }
  return null;
}
