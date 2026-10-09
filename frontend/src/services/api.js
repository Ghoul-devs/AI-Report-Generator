const API_URL = "http://127.0.0.1:8000";
const TOKEN_KEY = "atlas_access_token";

export function getAuthToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function clearAuthToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request(path, options = {}, authenticated = true) {
  const headers = new Headers(options.headers || {});
  if (authenticated && getAuthToken()) {
    headers.set("Authorization", `Bearer ${getAuthToken()}`);
  }
  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (response.status === 401 && authenticated) {
    clearAuthToken();
    window.dispatchEvent(new Event("auth-expired"));
  }
  if (!response.ok) {
    let detail = "Request failed";
    try { detail = (await response.json()).detail || detail; } catch { /* non-JSON error */ }
    throw new Error(Array.isArray(detail) ? detail.map((item) => item.msg).join("; ") : detail);
  }
  return response;
}

async function authenticate(path, credentials) {
  const result = await (await request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(credentials),
  }, false)).json();
  localStorage.setItem(TOKEN_KEY, result.access_token);
  return result.user;
}

export function register(credentials) {
  return authenticate("/auth/register", credentials);
}

export function login(credentials) {
  return authenticate("/auth/login", credentials);
}

export async function getCurrentUser() {
  return (await request("/auth/me")).json();
}

export async function logout() {
  try {
    await request("/auth/logout", { method: "POST" });
  } finally {
    clearAuthToken();
  }
}

export async function requestPasswordReset(email) {
  return (await request("/auth/forgot-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  }, false)).json();
}

export async function resetPassword(token, password) {
  const response = await request("/auth/reset-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, password }),
  }, false);
  clearAuthToken();
  window.dispatchEvent(new Event("auth-expired"));
  return response.json();
}

export async function generateReport(topic, reportType, onProgress = () => {}) {
  const runId = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const headers = { "Content-Type": "application/json", "X-Run-ID": runId };
  if (getAuthToken()) headers.Authorization = `Bearer ${getAuthToken()}`;
  const responsePromise = fetch(`${API_URL}/generate-report`, {
    method: "POST",
    headers,
    body: JSON.stringify({ topic, report_type: reportType }),
  });
  let finished = false;
  const polling = (async () => {
    while (!finished) {
      await new Promise((resolve) => setTimeout(resolve, 400));
      try {
        const statusResponse = await fetch(`${API_URL}/generate-report/status/${runId}`, {
          headers: { Authorization: `Bearer ${getAuthToken()}` },
        });
        if (statusResponse.status === 401) {
          clearAuthToken();
          window.dispatchEvent(new Event("auth-expired"));
          finished = true;
        } else if (statusResponse.ok) {
          onProgress(await statusResponse.json());
        }
      } catch { /* The report request returns the authoritative error. */ }
    }
  })();
  let response;
  try {
    response = await responsePromise;
  } finally {
    finished = true;
    await polling;
  }

  if (response.status === 401) {
    clearAuthToken();
    window.dispatchEvent(new Event("auth-expired"));
  }
  if (!response.ok) {
    let error = {};
    try { error = await response.json(); } catch { /* non-JSON error */ }
    const detail = error.detail || "Report generation failed";
    throw new Error(Array.isArray(detail) ? detail.map((item) => item.msg).join("; ") : detail);
  }
  return response.json();
}

export async function uploadPdf(file) {
  const form = new FormData();
  form.append("file", file);
  return (await request("/documents/upload", { method: "POST", body: form })).json();
}

export async function listReports() {
  return (await request("/reports")).json();
}

export async function readReport(id) {
  return (await request(`/reports/${id}`)).json();
}

export async function deleteReport(id) {
  return request(`/reports/${id}`, { method: "DELETE" });
}

export async function saveReport(id, report) {
  return (await request(`/reports/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ report }),
  })).json();
}

export async function exportReport(id, format) {
  try {
    const response = await request(`/reports/${id}/export/${format}`);
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = `report-${id}.${format === "md" ? "md" : format}`;
    link.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    window.dispatchEvent(new CustomEvent("app-error", { detail: error.message }));
  }
}

export async function submitFeedback(feedback) {
  return (await request("/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(feedback),
  })).json();
}
