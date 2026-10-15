import { env } from '../lib/env';
export class ApiError extends Error { constructor(public readonly status: number, message: string) { super(message); } }
export async function apiGet<T>(path: string, token?: string): Promise<T> { const response = await fetch(`${env.apiBaseUrl}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} }); if (!response.ok) throw new ApiError(response.status, 'Request failed'); return response.json() as Promise<T>; }
