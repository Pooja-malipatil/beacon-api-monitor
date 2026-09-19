import axios from "axios";

const API_BASE = "https://beacon-api-monitor.onrender.com";

export function createApiClient(token) {
  return axios.create({
    baseURL: API_BASE,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
}

export const API_BASE_URL = API_BASE;