import Stoppoint from "./Stoppoint";
import Mode from "./Mode";
import Line from "./Line";

interface IRoute {
  id: string;
  start: Stoppoint;
  end: Stoppoint;
  routeSteps: (IRouteSegment | IInterchange)[];
}

interface IRouteSegment {
  id: string;
  start: Stoppoint;
  end: Stoppoint;
  mode: Mode;
  line: Line;
}

interface IInterchange {
  id: string;
  at: Stoppoint;
  from: Line
  to: Line
}

export default class Route implements IRoute {
  private _id: string;
  private _start: Stoppoint;
  private _end: Stoppoint;
  private _routeSteps: (IRouteSegment | IInterchange)[];

  public constructor(
    id: string,
    start: Stoppoint,
    end: Stoppoint,
    routeSteps: (IRouteSegment | IInterchange)[]
  ) {
    this._id = id;
    this._start = start;
    this._end = end;
    this._routeSteps = routeSteps;
  }

  public get id(): string {
    return this._id;
  }

  public get start(): Stoppoint {
    return this._start;
  }

  public get end(): Stoppoint {
    return this._end;
  }

  public get routeSteps(): (IRouteSegment | IInterchange)[] {
    return this._routeSteps;
  }
}