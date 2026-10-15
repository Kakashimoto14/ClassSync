export type UserRole = 'administrator' | 'teacher' | 'student';
export interface ApiError { error: { code: string; message: string; requestId: string }; }
