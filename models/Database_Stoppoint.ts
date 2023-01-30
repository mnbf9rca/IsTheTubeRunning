import Stoppoint from "./Stoppoint";
import Mode from "./Mode";
import Line from "./Line";

export default class Database_Stoppoint extends Stoppoint {
  constructor (type: string, id: string, name: string, naptanId: string, lat: number | string, lon: number | string, modes: Mode[], lines: Line[]) {
    super(type, id, name, naptanId, lat, lon, modes, lines);
  }
}