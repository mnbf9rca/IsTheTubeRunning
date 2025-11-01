/**
 * User types - Stub for Phase 3 (Auth0 Integration)
 * Keep in sync with shared/schemas/user.py
 */

export interface UserBase {
  email?: string | null;
}

export interface UserCreate extends UserBase {
  auth0_id: string;
}

export interface UserResponse extends UserBase {
  id: number;
  auth0_id: string;
  created_at: string; // ISO 8601 date string
  updated_at: string; // ISO 8601 date string
}
