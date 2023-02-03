import Stoppoint from './Stoppoint';

enum tfl_line  {
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

interface ILine {
  toString: () => string;
  lineName: tfl_line;
  [Symbol.toStringTag]?: string;
}

interface ILineSegment extends ILine {
  id: string;
  type: "line-segment";
  from?: Stoppoint;
  fromId: string;
  to?: Stoppoint;
  toId: string;
  branchId: number;
  direction: "inbound" | "outbound";
  label?: string;
  fromObject?: (obj: any) => ILineSegment;
}
class Line implements ILine{
  private _name: tfl_line;

  constructor(lineName: string) {
    this._name = lineName as tfl_line;
  }
  toString(): string {
    return String(this._name);
  }
  get lineName(): tfl_line {
    return this._name;
  }

  get [Symbol.toStringTag](): string {
    return `Line: ${this._name}`;
  }

} 

class LineSegment extends Line implements ILineSegment {
  private _id: string;
  private _type: "line-segment";
  private _from?: Stoppoint;
  private _fromId: string;
  private _to?: Stoppoint;
  private _toId: string;
  private _branchId: number;
  private _direction: "inbound" | "outbound";
  private _label?: string;
  constructor (
    lineName: string,
    id: string,
    branchId: number,
    direction: "inbound" | "outbound",
    fromId?: string,
    toId?: string,    
    from?: Stoppoint,
    to?: Stoppoint,
    label?: string,
  ) {
    if (fromId === undefined && from === undefined) {
      throw new Error("If fromId is undefined, from must be defined");
    } else {
      fromId = fromId || from!.id;
    }
    if (toId === undefined && to === undefined) {
      throw new Error("If toId is undefined, to must be defined");
    } else {
      toId = toId || to!.id;
    }
    super(lineName),
    this._id = id;
    this._type = "line-segment";
    this._from = from;
    this._fromId = fromId;
    this._to = to;
    this._toId = toId;
    this._branchId = branchId;
    this._direction = direction;
    this._label = label;
  }
  get id(): string {
    return this._id;
  }
  get type(): "line-segment" {
    return this._type;
  }
  get from(): Stoppoint | undefined {
    return this._from;
  }
  get fromId(): string {
    return this._fromId;
  }
  get to(): Stoppoint | undefined {
    return this._to;
  }
  get toId(): string {
    return this._toId;
  }
  get branchId(): number {
    return this._branchId;
  }
  get direction(): "inbound" | "outbound" {
    return this._direction;
  }
  get label(): string | undefined {
    return this._label;
  }
  toString(): string {
    return `${this._id}`
  }
  static fromObject(obj: any): ILineSegment {
    return new LineSegment(
      obj.lineName,
      obj.id,
      obj.branchId,
      obj.direction,
      obj.fromId,
      obj.toId,
      obj.from,
      obj.to,
      obj.label,
    );
  }
  getObject() {
    return {
      lineName: super.lineName.toString(),
      id: this._id,
      type: this._type,
      from: this._from,
      fromId: this._fromId,
      to: this._to,
      toId: this._toId,
      branchId: this._branchId,
      direction: this._direction,
      label: this._label,
    };
  }
}




export { Line, LineSegment };