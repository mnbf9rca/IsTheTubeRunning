import Line from './Line';
/*const Mode = {
  bus: Symbol('bus'),
  dlr: Symbol('dlr'),
  'elizabeth-line': Symbol('elizabeth-line'),
  overground: Symbol('overground'),
  tube: Symbol('tube'),
}
*/
enum Modes {
  bus = 'bus',
  dlr = 'dlr',
  elizabethline = 'elizabeth-line',
  overground = 'overground',
  tube = 'tube',
}

type Mode = keyof typeof Modes;

export default class Stoppoint {
  private _name: string;
  private _naptanId: string;
  private _lat: number;
  private _lon: number;
  private _modes: Mode[];
  private _lines: Line[];

  constructor(name: string, naptanId: string, lat: number, lon: number, modes: Mode[], lines: Line[]) {
    this._name = name;
    this._naptanId = naptanId;
    this._lat = lat;
    this._lon = lon;
    this._modes = modes;
    this._lines = lines;
  }

  get name(): string {
    return this._name;
  }

  get naptanId(): string {
    return this._naptanId;
  }

  get latlon(): number[] {
    return [this._lat, this._lon];
  }

  get modes(): Mode[] {
    return this._modes;
  }

  get lines(): Line[] {
    return this._lines;
  }

  getLineNames(): string[] {
    return this._lines.map((line) => line.name);
  }

  getModeNames(): string[] {
    return this._modes.map((mode) => String(mode));
  }

  

}
