import * as Mode from './ModeFunctional'

const tfl_lines: { [key: string]: string } = {
  bakerloo: 'Bakerloo Line',
  central: 'Central Line',
  circle: 'Circle Line',
  district: 'District Line',
  dlr: 'DLR',
  'elizabeth-line': 'Elizabeth Line',
  'hammersmith-city': 'Hammersmith & City Line',
  jubilee: 'Jubilee Line',
  metropolitan: 'Metropolitan Line',
  northern: 'Northern Line',
  piccadilly: 'Piccadilly Line',
  victoria: 'Victoria Line',
  'waterloo-city': 'Waterloo & City Line',
  'london-overground': 'London Overground',
};

export interface Line {
  type: string;
  lineName: string;
  displayName: string;
  mode?: Mode.Mode;
  toString(): string
}


const lineInstances: { [key: string]: Line } = {};

const get_validated_mode = (mode: Mode.Mode | string): Mode.Mode => {
  if (!mode) {
    throw new Error('Mode is required');
  }
  if (typeof mode === 'string') {
    return Mode.getMode(mode);
  }
  if (Mode.validate(mode)) {
    return mode;
  }
  throw new Error(`Invalid mode: ${mode}`);
}

export function validate(lineToCheck: any): Boolean {
  /* validates that the line object is a valid Line object
  * i.e. has all the required properties
  * returns true if the line is valid
  * returns false if the line is not valid
  * */
 if (lineToCheck === null || lineToCheck === undefined || typeof lineToCheck !== 'object') {
  return false
 }
 const type = Object.prototype.hasOwnProperty.call(lineToCheck, 'type') && lineToCheck.type.toLowerCase() === 'line' 
 const lineName = Object.prototype.hasOwnProperty.call(lineToCheck, 'lineName') && typeof lineToCheck.lineName === 'string' 
 const displayName = Object.prototype.hasOwnProperty.call(lineToCheck, 'displayName') && typeof lineToCheck.displayName === 'string' 
 const modes = Object.prototype.hasOwnProperty.call(lineToCheck, 'mode') && lineToCheck.mode !== undefined ? Mode.validate(lineToCheck.mode) : true
 const toString = Object.prototype.hasOwnProperty.call(lineToCheck, 'toString') && typeof lineToCheck.toString === 'function' && lineToCheck.toString() === String(lineToCheck.lineName)
  return type &&     
    lineName &&
    displayName &&
    modes &&
    toString
}

export function isValidLine(lineName: string | undefined): boolean{
  return lineName !== undefined && !Array.isArray(isValidLine) && tfl_lines[lineName] !== undefined;
}

export function getLine(lineName: string, mode?: Mode.Mode | string): Line {
  /* returns the line object for the given line string 
  *  if the line is not valid, throws an error
  *  if the line is valid, returns the line object
  * 
  * @param {string} line - the line string to get the line object for
  * @param {Mode.Mode | string} mode - the mode to get the line object for. If a string is passed, it will be used to retrieve the relevant Mode.Mode object
  * @returns {line} - the line object for the given line string
  */
  if (!isValidLine(lineName)) {
    throw new Error(`Line not found in tfl_lines: ${lineName}`);
  }
  const validated_mode = mode ? get_validated_mode(mode) : undefined
  if (!lineInstances[lineName]) {
    lineInstances[lineName] = {
      type: 'line',
      lineName: lineName,
      displayName: tfl_lines[lineName],
      mode: validated_mode,
      toString() {
        return String(lineName);
      }
    };
  }

  return lineInstances[lineName];
}
