import * as Line from './LineFunctional';
import * as Mode from './ModeFunctional';

export function arraysContainSameModesOrLines(arr1: (Mode.Mode | Line.Line)[], arr2: (Mode.Mode | Line.Line)[]): boolean {
  if (arr1.length !== arr2.length) {
    return false;
  }
  for (const obj1 of arr1) {
    if (!isModeOrLineInArray(obj1, arr2)) {
      return false;
    }
  }
  return true;
}
function isModeOrLineInArray(modeOrLine: (Mode.Mode | Line.Line), arr: (Mode.Mode | Line.Line)[]): boolean {
  for (const arrObj of arr) {
    /// note: JS checks for object equivalence. This works for us because Mode and Line use 
    // a singleton pattern. But this wouldnt work for regular objects - you'd have to compare properties
    if (modeOrLine === arrObj) {
      return true;
    }
  }
  return false;
}