const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;
export const env = { apiBaseUrl: apiBaseUrl ?? 'http://127.0.0.1:8000/api/v1' } as const;
