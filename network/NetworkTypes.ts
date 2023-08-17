export interface StopPoint {
  type: string;
  id: string;
  name: string;
  naptanId: string;
  lat: number | string;
  lon: number | string;
  modes: Mode[];
  lines: string[];
}

export interface Line {
  type: string;
  lineName: string;
  displayName: string;
  mode?: Mode;
}

export interface LineSegment {
  type: string;
  line: string;
  from: string;
  to: string;
}

export enum Mode {
  bus = 'bus',
  dlr = 'dlr',
  elizabethline = 'elizabeth-line', // Changed key from elizabeth-line
  overground = 'overground',
  tube = 'tube',
}
