/**
 * Health check types - TypeScript equivalents of Python Pydantic models
 * Keep in sync with shared/schemas/health.py
 */

export interface HealthResponse {
  status: string;
}

export interface ReadinessResponse {
  status: string;
}

export interface RootResponse {
  message: string;
  version: string;
}
