enum tfl_lines  {
  bakerloo = 'Bakerloo',
  central = 'Central',
  circle = 'Circle',
  district = 'district',
  dlr = 'dlr',
  elizabethline = 'elizabeth-line',
  hammersmithcity = 'hammersmith-city',
  jubilee = 'jubilee',
  metropolitan = 'metropolitan',
  northern = 'northern',
  overground = 'overground',
  piccadilly = 'piccadilly',
  victoria = 'victoria',
  waterloocity = 'waterloo-city',
  tube = 'tube',
}

type tfl_line = keyof typeof tfl_lines;

export default class Line {
  private _name: tfl_line;

  constructor(lineName: tfl_line) {
    this._name = lineName;
  }
  get name(): string {
    return String(this._name);
  }

} 