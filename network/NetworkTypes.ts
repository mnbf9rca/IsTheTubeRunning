export interface StopPointClass extends StopPoint {
  getObject: () => StopPoint;
  toString: () => string;
  getLineNames: () => string[];
  getModeNames: () => string[];
  [Symbol.toStringTag]: string;
}

export interface StopPoint {
  type: string;
  id: string;
  name: string;
  naptanId: string;
  lat: number | string;
  lon: number | string;
  modes: String[];
  lines: String[];
}

