const Modes: { [key: string]: string } = {
  bus: 'bus',
  dlr: 'DLR',
  'elizabeth-line': 'Elizabeth Line',
  overground: 'Overground',
  tube: 'Tube'
}


interface IMode {
  id: string;
  name: string;
  toObject: () => IModeObject;
  toString: () => string;
  [Symbol.toStringTag]: string;

}

export interface IModeObject {
  type: string;
  id: string;
  name: string;
}

export default class Mode implements IMode {
  private _id: "bus" | "dlr" | "elizabeth-line" | "overground" | "tube";;
  private _name: string;

  public constructor(mode: "bus" | "dlr" | "elizabeth-line" | "overground" | "tube") {
    if (Array.isArray(mode)) {
      throw new Error(`Expected string, got array: ${mode}`);
    }
    if (!Object.keys(Modes).includes(mode)) {
      throw new Error(`Invalid mode: ${mode}`);
    }
    this._id = mode
    this._name = Modes[mode]
  }

  public get id(): string {
    return String(this._id);
  }

  public get name(): string {
    return this._name;
  }

  public toString(): string {
    return String(this._id);
  }

  public toObject(): IModeObject {
    return {
      type: 'mode',
      id: this._id,
      name: this._name,
    };
  }
  
  public get [Symbol.toStringTag](): string {
    return `Mode: ${this._id}`;
  }
}