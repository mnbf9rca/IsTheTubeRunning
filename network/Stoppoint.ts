import Line from './Line';
import Mode from './Mode';

import * as NetworkTypes from './NetworkTypes';

export default class Stoppoint implements NetworkTypes.StopPointClass {
  private _id: string;
  private _name: string;
  private _naptanId: string;
  private _lat: number;
  private _lon: number;
  private _modes: String[];
  private _lines: String[];

  constructor(
    id: string,
    name: string,
    naptanId: string,
    lat: number | string,
    lon: number | string,
    modes: String[],
    lines: String[]
  ) {
    if (isNaN(lat as number) || isNaN(lon as number)) {
      throw new Error(`Invalid lat/lon for stoppoint ${id}`);
    }
    if (id === '') {
      throw new Error(`Empty id for stoppoint ${name}/${naptanId}`);
    }
    if (name === '') {
      throw new Error(`Empty name for stoppoint ${id}/${naptanId}`);
    }
    if (naptanId === '') {
      throw new Error(`Empty naptanId for stoppoint ${id}/${name}`);
    }


    this._id = id;
    this._name = name;
    this._naptanId = naptanId;
    this._lat = Number(lat);
    this._lon = Number(lon);
    this._modes = modes;
    this._lines = lines;
  }


  get id() {
    return this._id;
  }

  get name() {
    return this._name;
  }

  get naptanId() {
    return this._naptanId;
  }

  get latlon() {
    return [this._lat, this._lon];
  }

  get lat() {
    return this._lat;
  }

  get lon() {
    return this._lon;
  }

  get modes() {
    return this._modes;
  }

  get lines() {
    return this._lines;
  }

  get type() {
    return 'stoppoint';
  }

  getLineNames() {
    return this._lines.map((line) => line.toString());
  }

  getModeNames() {
    return this._modes.map((mode) => mode.toString());
  }

  getObject(): NetworkTypes.StopPoint {
    return {
      type: 'stoppoint',
      id: this._id,
      name: this._name,
      naptanId: this._naptanId,
      lat: this._lat,
      lon: this._lon,
      modes: this.getModeNames(),
      lines: this.getLineNames(),
    };
  }

  public get [Symbol.toStringTag](): string {
    return `Stoppoint: ${this._id}`;
  }

}
