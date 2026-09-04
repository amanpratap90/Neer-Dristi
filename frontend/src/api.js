const API_BASE =
  import.meta.env.VITE_API_BASE_URL || "https://neer-dristi.onrender.com";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(
      data?.detail?.message ||
      data?.detail ||
      data?.message ||
      "Neer Drishti backend request failed."
    );
  }

  return data;
}

export async function analyzeLocation(latitude, longitude) {
  return request("/api/v1/intelligence/analyze", {
    method: "POST",
    body: JSON.stringify({
      latitude,
      longitude,
      strict: false,
    }),
  });
}

export async function searchLocation(query) {
  return request(
    `/api/v1/location/search?q=${encodeURIComponent(query)}`
  );
}