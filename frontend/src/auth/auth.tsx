import axios from 'axios';

// 1. CREATE CUSTOM AXIOS INSTANCE
// We point this to your local or production FastAPI backend address
const api = axios.create({
  baseURL: 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
  // CRITICAL: This forces the browser to automatically attach and receive
  // your HttpOnly secure session cookies (access_token & refresh_token)
  withCredentials: true,
});
api.interceptors.request.use((config) => {
  if (config.data instanceof FormData) {
    delete config.headers['Content-Type'];
  }
  return config;
});
// 2. RESPONSE INTERCEPTOR (The Session Guard) 
api.interceptors.response.use( //accepts two parameters fulfilled and rejected
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