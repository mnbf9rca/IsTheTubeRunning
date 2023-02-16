const Modes: { [key: string]: string } = {
  bus: 'Bus',
  dlr: 'DLR',
  'elizabeth-line': 'Elizabeth Line',
  overground: 'Overground',
  tube: 'Tube'
}

export interface Mode {
  type: string;
  id: string;
  name: string;
  toString: () => string;
}

const modeInstances: { [key: string]: Mode } = {};

export function validate(modeToCheck: any): boolean {
  /* validates that the mode object is a valid mode object
  * i.e. has all the required properties
  * returns true if the mode is valid
  * returns false if the mode is not valid
  * */
  return modeToCheck !== undefined && modeToCheck !== null && typeof modeToCheck === 'object' &&
    Object.prototype.hasOwnProperty.call(modeToCheck, 'type') && modeToCheck.type === 'mode' &&
    Object.prototype.hasOwnProperty.call(modeToCheck, 'id') && typeof modeToCheck.id === 'string' &&
    Object.prototype.hasOwnProperty.call(modeToCheck, 'name') && typeof modeToCheck.name === 'string' &&
    Object.prototype.hasOwnProperty.call(modeToCheck, 'toString') && typeof modeToCheck.toString === 'function' && modeToCheck.toString() === String(modeToCheck.id)
}

export function getMode(mode: string): Mode {
  /* returns the mode object for the given mode string 
  *  if the mode is not valid, throws an error
  *  if the mode is valid, returns the mode object
  * 
  * @param {string} mode - the mode string to get the mode object for
  * @returns {Mode} - the mode object for the given mode string
  */
  if (!Modes[mode]) {
    throw new Error(`Invalid mode: ${mode}`);
  }

  if (!modeInstances[mode]) {
    modeInstances[mode] = {
      type: 'mode',
      id: mode,
      name: Modes[mode],
      toString() {
        return String(mode);
      }
    };
  }
  return modeInstances[mode];
}

