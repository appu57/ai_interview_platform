import axios from 'axios';

// 1. CREATE CUSTOM AXIOS INSTANCE
// We point this to your local or production FastAPI backend address
const api = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
  // CRITICAL: This forces the browser to automatically attach and receive
  // your HttpOnly secure session cookies (access_token & refresh_token)
  withCredentials: true,
});

// 2. RESPONSE INTERCEPTOR (The Session Guard)
api.interceptors.response.use(
  (response) => {
    return response;
  },
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        console.log("Access session expired. Initiating background handshake rotation...");

        await axios.post(
          `${api.defaults.baseURL}/api/auth/refresh`,
          {},
          { withCredentials: true }
        );

        console.log("Tokens rotated successfully. Re-executing original task...");
        

        return api(originalRequest);
      } catch (refreshError) {
        console.error("User session completely expired. Directing to login context...");

        window.location.href = '/signin';
        
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

export default api;