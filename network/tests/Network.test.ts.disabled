import * as Network from '../Network';
import * as Mode from '../ModeFunctional';
import * as Line from '../LineFunctional';

describe('arraysContainSameModesOrLines', () => {
  test('arraysContainSameModesOrLines([], []) should return true', () => {
    const arr1: any[] = [];
    const arr2: any[] = [];
    expect(Network.arraysContainSameModesOrLines(arr1, arr2)).toBe(true);
  })
  test('Shoudl return true if array contains a single item', () => {
    const arr1: any[] = [Mode.getMode('tube')];
    const arr2: any[] = [Mode.getMode('tube')];
    expect(Network.arraysContainSameModesOrLines(arr1, arr2)).toBe(true);
  })
  test('Should return true if array contains same object in both arrays', () => {
    const arr1: (Mode.Mode | Line.Line)[] = [Mode.getMode('tube'), Mode.getMode('elizabeth-line')];
    const arr2: (Mode.Mode | Line.Line)[] = arr1
    expect(Network.arraysContainSameModesOrLines(arr1, arr2)).toBe(true);
  })
  test('Should return false if one item in the array differs', () => {
    const arr1: (Mode.Mode | Line.Line)[] = [Mode.getMode('tube'), Mode.getMode('elizabeth-line')];
    const arr2: (Mode.Mode | Line.Line)[] = [Mode.getMode('tube'), Mode.getMode('bus')];
    expect(Network.arraysContainSameModesOrLines(arr1, arr2)).toBe(false);
  })
  test('Should return false if second array is clone of first (i.e. deep copy)', () => {
    const arr1: (Mode.Mode | Line.Line)[] = [Mode.getMode('tube'), Mode.getMode('elizabeth-line')];
    const arr2: (Mode.Mode | Line.Line)[] = JSON.parse(JSON.stringify(arr1));
    expect(Network.arraysContainSameModesOrLines(arr1, arr2)).toBe(false);
  })
  test('Should return false if array contains different object in both arrays', () => {
    const arr1: (Mode.Mode | Line.Line)[] = [Mode.getMode('tube'), Mode.getMode('elizabeth-line')];
    const arr2: (Mode.Mode | Line.Line)[] = [Mode.getMode('bus'), Mode.getMode('dlr')];
    expect(Network.arraysContainSameModesOrLines(arr1, arr2)).toBe(false);
  })
  test('Should return true if the order is different', () => {
    const arr1: (Mode.Mode | Line.Line)[] = [Mode.getMode('tube'), Mode.getMode('elizabeth-line')];
    const arr2: (Mode.Mode | Line.Line)[] = [Mode.getMode('elizabeth-line'), Mode.getMode('tube')];
    expect(Network.arraysContainSameModesOrLines(arr1, arr2)).toBe(true);
  })
})