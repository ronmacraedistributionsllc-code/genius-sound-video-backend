// Replace BACKEND_URL with your DigitalOcean Live App URL.
const BACKEND_URL = "https://YOUR-DIGITALOCEAN-LIVE-APP-URL";

async function createVideo(imageFile, audioFile, quality = "1080p") {
  const formData = new FormData();
  formData.append("image", imageFile);
  formData.append("audio", audioFile);
  formData.append("quality", quality);

  const response = await fetch(`${BACKEND_URL}/create-video`, {
    method: "POST",
    body: formData
  });

  const data = await response.json();

  if (!response.ok || !data.ok) {
    throw new Error(data?.detail?.message || data?.detail || "Video creation failed");
  }

  const downloadUrl = `${BACKEND_URL}${data.download_url}`;
  return downloadUrl;
}
