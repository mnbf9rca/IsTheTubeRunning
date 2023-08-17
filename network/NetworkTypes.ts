export interface StopPoint {
  type: string;
  id: string;
  name: string;
  naptanId: string;
  lat: number | string;
  lon: number | string;
  modes: string[];
  lines: string[];
}

