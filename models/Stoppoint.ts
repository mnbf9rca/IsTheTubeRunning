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
  private _type: string;
  private _id: string;
  private _name: string;
  private _naptanId: string;
  private _lat: number;
  private _lon: number;
  private _modes: Mode[];
  private _lines: Line[];

  constructor(type: string, id: string, name: string, naptanId: string, lat: number | string, lon: number | string, modes: Mode[], lines: Line[]) {
    this._type = type;
    this._id = id;
    this._name = name;
    this._naptanId = naptanId;
    this._lat = Number(lat);
    this._lon = Number(lon);
    this._modes = modes;
    this._lines = lines;
  }

  get id(): string {
    return this._id;
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

  get lat(): number {
    return this._lat;
  }

  get lon(): number {
    return this._lon;
  }
  

  get modes(): Mode[] {
    return this._modes;
  }

  get lines(): Line[] {
    return this._lines;
  }

  get type(): string {
    return this._type;
  }


  getLineNames(): string[] {
    return this._lines.map((line) => line.toString());
  }

  getModeNames(): string[] {
    return this._modes.map((mode) => String(mode));
  }

  getObject(): object {
    return {
      type: this._type,
      id: this._id,
      name: this._name,
      naptanId: this._naptanId,
      lat: this._lat,
      lon: this._lon,

      modes: this.getModeNames(),
      lines: this.getLineNames(),
    };
  }

}
