import * as Line from './LineFunctional';
import * as Mode from './ModeFunctional';
import * as Network from './Network';

export interface Stoppoint {
  id: string;
  name: string;
  naptanId: string;
  lat: number;
  lon: number;
  modes: Mode.Mode[];
  lines: Line.Line[];
  toString: () => string;
  getLineNames: () => string[];
  getModeNames: () => string[];
}

export function validate(stoppointToCheck: any): boolean {
  /* validates that the stoppoint object is a valid stoppoint object
  * i.e. has all the required properties
  * returns true if the stoppoint is valid
  * returns false if the stoppoint is not valid
  * */
  return stoppointToCheck !== undefined && stoppointToCheck !== null && typeof stoppointToCheck === 'object' &&
    Object.prototype.hasOwnProperty.call(stoppointToCheck, 'id') && typeof stoppointToCheck.id === 'string' &&
    Object.prototype.hasOwnProperty.call(stoppointToCheck, 'name') && typeof stoppointToCheck.name === 'string' &&
    Object.prototype.hasOwnProperty.call(stoppointToCheck, 'naptanId') && typeof stoppointToCheck.naptanId === 'string' &&
    Object.prototype.hasOwnProperty.call(stoppointToCheck, 'lat') && typeof stoppointToCheck.lat === 'number' &&
    Object.prototype.hasOwnProperty.call(stoppointToCheck, 'lon') && typeof stoppointToCheck.lon === 'number' &&
    Object.prototype.hasOwnProperty.call(stoppointToCheck, 'modes') && typeof stoppointToCheck.modes === 'object' &&
    Object.prototype.hasOwnProperty.call(stoppointToCheck, 'lines') && typeof stoppointToCheck.lines === 'object' &&
    Object.prototype.hasOwnProperty.call(stoppointToCheck, 'toString') && typeof stoppointToCheck.toString === 'function' &&
    stoppointToCheck.toString() === String(stoppointToCheck.id)
}


const stoppointInstances: { [key: string]: Stoppoint } = {};

export function getStoppointById(id: string): Stoppoint {
  /* returns the stoppoint object for the given id string 
  *  if the stoppoint does not exist, it returns undefined
  * 
  * @param {string} id - the id string to get the stoppoint object for
  * @returns {IStoppoint} - the stoppoint object for the given id string
  */
  if (!stoppointInstances[id]) {
    throw new Error(`Invalid stoppoint: ${id}`);
  }
  return stoppointInstances[id];
}

export function compareStoppoints(obj1: Stoppoint, obj2: Stoppoint): string[] {
  let diff: string[] = [];
  if (!validate(obj1)) {
    diff.push('obj1 is not a valid stoppoint');
  }
  if (!validate(obj2)) {
    diff.push('obj2 is not a valid stoppoint');
  }
  if (diff.length === 0) {
    diff = diff.concat(compareProperties(obj1, obj2, 'id'));
    diff = diff.concat(compareProperties(obj1, obj2, 'name'));
    diff = diff.concat(compareProperties(obj1, obj2, 'naptanId'));
    diff = diff.concat(compareProperties(obj1, obj2, 'lat'));
    diff = diff.concat(compareProperties(obj1, obj2, 'lon'));
    if (!Network.arraysContainSameModesOrLines(obj1.modes, obj2.modes)) {
      diff.push(`modes differ across objects: ${obj1.modes} != ${obj2.modes}`);
    }
    if (!Network.arraysContainSameModesOrLines(obj1.lines, obj2.lines)) {
      diff.push(`lines differ across objects: ${obj1.lines} != ${obj2.lines}`);
    }    ;
  }
  return diff
}


function compareProperties<T>(obj1: T, obj2: T, property: string): string[] {
  const diff: string[] = [];
  if (!Object.prototype.hasOwnProperty.call(obj1, property)) {
    diff.push(`${property} missing from obj1`);
  }
  if (!Object.prototype.hasOwnProperty.call(obj2, property)) {
    diff.push(`${property} missing from obj2`);
  }
  if (diff.length === 0 && obj1[property as keyof T] !== obj2[property as keyof T]) {
    diff.push(`${property} mismatch: ${obj1[property as keyof T]} != ${obj2[property as keyof T]}`);
  }

  return diff;
}

export function addStoppoint(id: string, name: string, naptanId: string, lat: number, lon: number, modes: Mode.Mode[], lines: Line.Line[]): Stoppoint {
  /* creates a new stoppoint object and returns it
  * 
  * @param {string} id - the id string of the new stoppoint
  * @param {string} name - the name of the new stoppoint
  * @param {string} naptanId - the naptan id of the new stoppoint
  * @param {number} lat - the latitude of the new stoppoint
  * @param {number} lon - the longitude of the new stoppoint
  * @param {Mode.Mode[]} modes - the modes of the new stoppoint
  * @param {Line.Line[]} lines - the lines of the new stoppoint
  * @returns {IStoppoint} - the new stoppoint object
  */

  // check that the modes and lines are valid
  if (!(Array.isArray(modes) && modes.every(m => Mode.validate(m)))) {
    throw new Error(`Invalid modes in modes or not array: ${modes}`);
  }
  if (!(Array.isArray(lines) && lines.every(l => Line.validate(l)))) {
    throw new Error(`Invalid lines in lines or not array: ${lines}`);
  }
  // check if properties is missing
  if (!id || typeof id !== 'string') {
    throw new Error(`Invalid id: ${id}`);
  }
  if (!name || typeof name !== 'string') {
    throw new Error(`Invalid name: ${name}`);
  }
  if (!naptanId || typeof naptanId !== 'string') {
    throw new Error(`Invalid naptanId: ${naptanId}`);
  }
  if (!lat || typeof lat !== 'number') {
    throw new Error(`Invalid lat: ${lat}`);
  }
  if (!lon || typeof lon !== 'number') {
    throw new Error(`Invalid lon: ${lon}`);
  }
  if (!(Array.isArray(modes) && modes.every(m => Mode.validate(m)))) {
    throw new Error(`Invalid modes in modes: ${modes}`);
  }
  if (!(Array.isArray(lines) && lines.every(l => Line.validate(l)))) {
    throw new Error(`Invalid lines in lines: ${lines}`);
  }
  const newStoppoint: Stoppoint = {
    id: id,
    name: name,
    naptanId: naptanId,
    lat: lat,
    lon: lon,
    modes: modes,
    lines: lines,
    toString: () => String(id),
    getLineNames: () => lines.map(line => line.lineName),
    getModeNames: () => modes.map(m => m.id)
  }
  // validate that this would be a valid stoppoint
  if (!validate(newStoppoint)) {
    throw new Error(`Invalid stoppoint: ${newStoppoint}`);
  }

  //  check if this stoppoint exists. If it does, and the properties match, return that. If not, create a new stoppoint object and return it
  if (stoppointInstances[id]) {
    const objDiff = compareStoppoints(stoppointInstances[id], newStoppoint)
    if (objDiff.length > 0) {
      throw new Error(`Stoppoint with id ${id} already exists but has different properties.\n${objDiff.join('\n')}`);
    }
  } else {
    stoppointInstances[id] = newStoppoint;
  }


  return stoppointInstances[id]
}