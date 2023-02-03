import { ILine, ILineObject } from "./Line";
import Line from "./Line";
import Mode from "./Mode";
import Stoppoint from "./Stoppoint";

export interface ILineSegment extends ILine {
  id: string;
  from: Stoppoint;
  to: Stoppoint;
  branchId: number;
  direction: "inbound" | "outbound";
  toObject: () => ILineSegmentObject
}

export interface ILineSegmentObject extends ILineObject {
  id: string;
  type: string;
  from: object;
  to: object;
  branchId: number;
  direction: string;
}

export default class LineSegment implements ILineSegment {
  private _id: string;
  private _from: Stoppoint;
  private _to: Stoppoint;
  private _branchId: number;
  private _direction: "inbound" | "outbound";
  private _line: Line;
  constructor(lineName: string | Line, mode: string | Mode, from: Stoppoint, to: Stoppoint, branchId: number, direction: "inbound" | "outbound") {
    if (direction !== "inbound" && direction !== "outbound") {
      throw new Error(`Direction must be inbound or outbound, not ${direction}`);
    }

    const get_mode = (mode: string | Mode) => {
      if (typeof mode === "string") {
        let mode_name = mode as "bus" | "dlr" | "elizabeth-line" | "overground" | "tube"
        return new Mode(mode_name);
      } else if (mode instanceof Mode) {
        return mode;
      } else {
        throw new Error(`Invalid mode: ${mode}`);
      }
    }
    const thisMode = get_mode(mode)

    function get_line(lineName: string | Line, thisMode: Mode) {
      if (typeof lineName === "string") {
        return new Line(lineName, thisMode);
      } else if (lineName instanceof Line) {
        return lineName;
      } else {
        throw new Error(`Invalid line: ${lineName}`);
      }
    }

    this._line = get_line(lineName, thisMode);

    this._id = `${lineName}-${branchId}-${direction}-${from.id}-${to.id}`;
    this._from = from;
    this._to = to;
    this._branchId = branchId;
    this._direction = direction;
  }

  public get id(): string {
    return this._id;
  }

  public get from(): Stoppoint {
    return this._from;
  }

  public get to(): Stoppoint {
    return this._to;
  }

  public get branchId(): number {
    return this._branchId;
  }

  public get direction(): "inbound" | "outbound" {
    return this._direction;
  }

  public get line(): Line {
    return this._line;
  }

  public get lineName(): string {
    return this._line.lineName;
  }

  public get displayName(): string {
    return this._line.displayName;
  }

  public get mode(): Mode {
    return this._line.mode;
  }

  public toString(): string {
    return `LineSegment: ${this._id}`;
  }

  public toObject(): ILineSegmentObject {
    return {
      id: this._id,
      type: 'LineSegment',
      from: this._from.getObject(),
      to: this._to.getObject(),
      branchId: this._branchId,
      direction: this._direction,
      lineName: this._line.lineName,
      displayName: this._line.displayName,
      mode: this._line.mode.toString(),
    };
  }

  public get [Symbol.toStringTag](): string {
    return `LineSegment: ${this._id}`;
  }
}
