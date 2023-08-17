import LineSegment from "../LineSegment";
import Line from "../Line";
import Mode from "../Mode";
import Stoppoint from "../Stoppoint";


const modeTube = new Mode('tube');
const victoriaLine = new Line('victoria', modeTube);
const picadillyLine = new Line('piccadilly', modeTube);

const stoppoint1 = new Stoppoint(
  '940GZZLULVT',
  'Liverpool Street',
  '940GZZLULVT',
  51.5178,
  -0.0817,
  [modeTube],
  [victoriaLine, picadillyLine]
);

const stoppoint2 = new Stoppoint(
  '940GZZLUKSX',
  'Kings Cross St Pancras',
  '940GZZLUKSX',
  51.5301,
  -0.1224,
  [modeTube],
  [victoriaLine, picadillyLine]
);


describe('LineSegment', () => {
  describe('test constructor', () => {
    test('return a LineSegment object when called with Line, Mode and Stoppoints', () => {
      const actual_result = new LineSegment(picadillyLine, modeTube, stoppoint1, stoppoint2, 1, 'inbound');
      expect(actual_result).toBeInstanceOf(LineSegment);
      expect(actual_result.line).toBe(picadillyLine);
      expect(actual_result.mode).toBe(modeTube);
      expect(actual_result.from).toBe(stoppoint1);
      expect(actual_result.to).toBe(stoppoint2);
      expect(actual_result.branchId).toBe(1);
      expect(actual_result.direction).toBe('inbound');
    });
    test('return a LineSegment object when called with Stoppoints but string for Line and Mode', () => {
      const actual_result = new LineSegment('piccadilly', 'tube', stoppoint1, stoppoint2, 1, 'inbound');
      expect(actual_result).toBeInstanceOf(LineSegment);
      expect(actual_result.line).toStrictEqual(picadillyLine);
      expect(actual_result.mode).toStrictEqual(modeTube);
      expect(actual_result.from).toBe(stoppoint1);
      expect(actual_result.to).toBe(stoppoint2);
      expect(actual_result.branchId).toBe(1);
      expect(actual_result.direction).toBe('inbound');
    });
    test('return a LineSegment object when called with Stoppoints and Mode but string for Line', () => {
      const actual_result = new LineSegment('piccadilly', modeTube, stoppoint1, stoppoint2, 1, 'inbound');
      expect(actual_result).toBeInstanceOf(LineSegment);
      expect(actual_result.line).toStrictEqual(picadillyLine);
      expect(actual_result.mode).toBe(modeTube);
      expect(actual_result.from).toBe(stoppoint1);
      expect(actual_result.to).toBe(stoppoint2);
      expect(actual_result.branchId).toBe(1);
      expect(actual_result.direction).toBe('inbound');
    });
    test('accept outbound as direction', () => {
      const actual_result = new LineSegment(picadillyLine, modeTube, stoppoint1, stoppoint2, 1, 'outbound');
      expect(actual_result).toBeInstanceOf(LineSegment);
      expect(actual_result.line).toBe(picadillyLine);
      expect(actual_result.mode).toBe(modeTube);
      expect(actual_result.from).toBe(stoppoint1);
      expect(actual_result.to).toBe(stoppoint2);
      expect(actual_result.branchId).toBe(1);
      expect(actual_result.direction).toBe('outbound');
    });
    test('throw an error if direction is not inbound or outbound', () => {
      expect(() => new LineSegment(picadillyLine, modeTube, stoppoint1, stoppoint2, 1, 'northbound' as 'inbound')).toThrow('Direction must be inbound or outbound, not northbound');
    });
  });
  describe('test class methods', () => {
    test('toObject returns an object with the correct properties', () => {
      const expected_result = {
        type: 'LineSegment',
        id: 'piccadilly-1-inbound-940GZZLULVT-940GZZLUKSX',
        lineName: picadillyLine.lineName,
        displayName: picadillyLine.displayName,
        mode: modeTube.toString(),
        from: stoppoint1.getObject(),
        to: stoppoint2.getObject(),
        branchId: 1,
        direction: 'inbound'
      }
      const lineSegment = new LineSegment(picadillyLine, modeTube, stoppoint1, stoppoint2, 1, 'inbound');
      const actual_result = lineSegment.toObject();
      expect(actual_result).toStrictEqual(expected_result);
    });
    test('toString returns a string with the correct properties', () => {
      const expected_result = 'LineSegment: piccadilly-1-inbound-940GZZLULVT-940GZZLUKSX';
      const lineSegment = new LineSegment(picadillyLine, modeTube, stoppoint1, stoppoint2, 1, 'inbound');
      const actual_result = lineSegment.toString();
      expect(actual_result).toBe(expected_result);
    });
    test('[Symbol.toStringTag] returns a string with the correct properties', () => {
      const expected_result = 'LineSegment: piccadilly-1-inbound-940GZZLULVT-940GZZLUKSX';
      const lineSegment = new LineSegment(picadillyLine, modeTube, stoppoint1, stoppoint2, 1, 'inbound');
      const actual_result = lineSegment[Symbol.toStringTag];
      expect(actual_result).toBe(expected_result);
    });
    test('return "[object LineSegment: piccadilly-1-inbound-940GZZLULVT-940GZZLUKSX]" when Object.prototype.toString() is called', () => {
      const expected_result = '[object LineSegment: piccadilly-1-inbound-940GZZLULVT-940GZZLUKSX]';
      const lineSegment = new LineSegment(picadillyLine, modeTube, stoppoint1, stoppoint2, 1, 'inbound');
      const actual_result = Object.prototype.toString.call(lineSegment);
      expect(actual_result).toBe(expected_result);
    });
  })
  describe('test object properties', () => {
    test('id is "piccadilly-1-inbound-940GZZLULVT-940GZZLUKSX"', () => {
      const lineSegment = new LineSegment(picadillyLine, modeTube, stoppoint1, stoppoint2, 1, 'inbound');
      expect(lineSegment.id).toBe('piccadilly-1-inbound-940GZZLULVT-940GZZLUKSX');
    });
    test('lineName is "piccadilly"', () => {
      const lineSegment = new LineSegment(picadillyLine, modeTube, stoppoint1, stoppoint2, 1, 'inbound');
      expect(lineSegment.lineName).toBe('piccadilly');
    });
    test('displayName is "Piccadilly Line"', () => {
      const lineSegment = new LineSegment(picadillyLine, modeTube, stoppoint1, stoppoint2, 1, 'inbound');
      expect(lineSegment.displayName).toBe('Piccadilly Line');
    });
    test('mode is "tube"', () => {
      const lineSegment = new LineSegment(picadillyLine, modeTube, stoppoint1, stoppoint2, 1, 'inbound');
      expect(lineSegment.mode).toBe(modeTube);
    });
    test('from is stoppoint1', () => {
      const lineSegment = new LineSegment(picadillyLine, modeTube, stoppoint1, stoppoint2, 1, 'inbound');
      expect(lineSegment.from).toBe(stoppoint1);
    });
    test('to is stoppoint2', () => {
      const lineSegment = new LineSegment(picadillyLine, modeTube, stoppoint1, stoppoint2, 1, 'inbound');
      expect(lineSegment.to).toBe(stoppoint2);
    });
    test('branchId is 1', () => {
      const lineSegment = new LineSegment(picadillyLine, modeTube, stoppoint1, stoppoint2, 1, 'inbound');
      expect(lineSegment.branchId).toBe(1);
    });
    test('direction is "inbound"', () => {
      const lineSegment = new LineSegment(picadillyLine, modeTube, stoppoint1, stoppoint2, 1, 'inbound');
      expect(lineSegment.direction).toBe('inbound');
    });
    test('line is picadillyLine', () => {
      const lineSegment = new LineSegment(picadillyLine, modeTube, stoppoint1, stoppoint2, 1, 'inbound');
      expect(lineSegment.line).toBe(picadillyLine);
    }    );
    test('lineName is "piccadilly"', () => {
      const lineSegment = new LineSegment(picadillyLine, modeTube, stoppoint1, stoppoint2, 1, 'inbound');
      expect(lineSegment.lineName).toBe('piccadilly');
    });
  });

})