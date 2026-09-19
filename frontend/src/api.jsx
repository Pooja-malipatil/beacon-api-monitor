import axios from "axios";

const API_BASE = "http://127.0.0.1:8000";

export function createApiClient(token) {
  return axios.create({
    baseURL: API_BASE,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
}

export const API_BASE_URL = API_BASE;