import Line from './Line';
import {Mode, Modes} from './Mode';

interface IStoppoint {
  label?: string;
  type: 'stoppoint' | 'vertex';
  id: string;
  name: string;
  naptanId: string;
  lat: number | string;
  lon: number | string;
  modes: Mode[];
  lines: Line[];
  getObject: () => IStoppoint_Object;
}

interface IStoppoint_Object  {
  label?: string;
  type: 'stoppoint' | 'vertex';
  id: string;
  name: string;
  naptanId: string;
  lat: number | string;
  lon: number | string;
  modes: String[];
  lines: String[];
}



export default class Stoppoint implements IStoppoint{
  private _type: "stoppoint" | "vertex";
  private _id: string;
  private _name: string;
  private _naptanId: string;
  private _lat: number;
  private _lon: number;
  private _modes: Mode[];
  private _lines: Line[];

  constructor(
    type: "stoppoint" | "vertex",
    id: string,
    name: string,
    naptanId: string,
    lat: number | string,
    lon: number | string,
    modes: Mode[],
    lines: Line[]
  ) {

    this._type = type;
    this._id = id;
    this._name = name;
    this._naptanId = naptanId;
    this._lat = Number(lat);
    this._lon = Number(lon);
    this._modes = modes;
    this._lines = lines;
  }

  static fromObject(obj: any): Stoppoint {
    // check of obj.modes contain valid modes
    const modes: Mode[] = [];
    for (const mode of obj.modes) {
      if (Object.values(Modes).includes(mode as Modes)) {
        modes.push(mode as Mode);
      } else {
        throw new TypeError(`Invalid mode: ${mode}, must be one of ${Object.values(Modes)}`)
      }
    }

    return new Stoppoint(
      obj.type,
      obj.id,
      obj.name,
      obj.naptanId,
      obj.lat,
      obj.lon,
      modes,
      obj.lines,
    );
  }


  get id(){
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
    return this._type;
  }


  getLineNames() {
    return this._lines.map((line) => line.toString());
  }

  getModeNames() {
    return this._modes.map((mode) => String(Modes[mode]))// as Modes[];
  }

  getObject() {
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
