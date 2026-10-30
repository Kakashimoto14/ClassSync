import { env } from '../lib/env';
import { liveFetch } from '../config/runtime-config';
export class ApiError extends Error { constructor(public readonly status: number, message: string) { super(message); } }
export async function apiGet<T>(path: string, token?: string): Promise<T> { const response = await liveFetch(`${env.apiBaseUrl}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} }); if (!response.ok) throw new ApiError(response.status, 'Request failed'); return response.json() as Promise<T>; }
