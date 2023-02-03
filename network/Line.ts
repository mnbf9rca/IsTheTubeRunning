import Mode from './Mode';

const tfl_lines: { [key: string]: string } = {
  bakerloo: 'Bakerloo',
  central: 'Central',
  circle: 'Circle',
  district: 'District',
  dlr: 'DLR',
  'elizabeth-line': 'Elizabeth Line',
  'hammersmith-city': 'Hammersmith & City',
  jubilee: 'Jubilee',
  metropolitan: 'Metropolitan',
  northern: 'Northern',
  piccadilly: 'Piccadilly',
  victoria: 'Victoria',
  'waterloo-city': 'Waterloo & City',
  'london-overground': 'London Overground',
}

export interface ILine {
  toString: () => string;
  toObject: () => ILineObject;
  lineName: string;
  displayName: string;
  mode: Mode;
  [Symbol.toStringTag]: string;
}

export interface ILineObject {
  lineName: string;
  displayName: string;
  mode: string;
  type: string;
}

export default class Line implements ILine {
  private _lineName: string;
  private _displayName: string;
  private _mode: Mode;
  public constructor(lineName: string, mode: Mode) {
    if (!tfl_lines[lineName]) {
      throw new Error(`Line ${lineName} not found in tfl_lines`);
    }
    this._lineName = lineName;
    this._displayName = tfl_lines[lineName];
    this._mode = mode;
  }

  public toString(): string {
    return String(this._lineName);
  }

  public get lineName(): string {
    return this._lineName;
  }
  
  public get displayName(): string {
    return this._displayName;
  }

  public get mode(): Mode {
    return this._mode;
  }

  public toObject(): ILineObject {
    return {
      lineName: this._lineName,
      displayName: this._displayName,
      mode: this._mode.id,
      type: 'line',
    };
  }

  public get [Symbol.toStringTag](): string {
    return `Line: ${this._lineName}`;
  }
}