import Stoppoint from '../Stoppoint';
import Line from '../Line';
import Mode from '../Mode';

const modeTube = new Mode('tube');
const victoriaLine = new Line('victoria', modeTube);
const picadillyLine = new Line('piccadilly', modeTube);

describe('Stoppoint', () => {
  describe('constructor', () => {
    test('should return a Stoppoint object', () => {
      const actual_result = new Stoppoint(
        '940GZZLULVT',
        'Liverpool Street',
        '940GZZLULVT',
        51.5178,
        -0.0817,
        [modeTube],
        [victoriaLine, picadillyLine]
      );
      expect(actual_result).toBeInstanceOf(Stoppoint);
      expect(actual_result.name).toBe('Liverpool Street');
      expect(actual_result.id).toBe('940GZZLULVT');
      expect(actual_result.naptanId).toBe('940GZZLULVT');
      expect(actual_result.lat).toBe(51.5178);
      expect(actual_result.lon).toBe(-0.0817);
      expect(actual_result.modes).toEqual([modeTube]);
      expect(actual_result.lines).toEqual([victoriaLine, picadillyLine]);
    });
    test('accepts empty lines', () => {
      const actual_result = new Stoppoint(
        '940GZZLULVT',
        'Liverpool Street',
        '940GZZLULVT',
        51.5178,
        -0.0817,
        [modeTube],
        []
      );
      expect(actual_result).toBeInstanceOf(Stoppoint);
      expect(actual_result.name).toBe('Liverpool Street');
      expect(actual_result.id).toBe('940GZZLULVT');
      expect(actual_result.naptanId).toBe('940GZZLULVT');
      expect(actual_result.lat).toBe(51.5178);
      expect(actual_result.lon).toBe(-0.0817);
      expect(actual_result.modes).toEqual([modeTube]);
      expect(actual_result.lines).toEqual([]);
    });
    test('accepts empty modes', () => {
      const actual_result = new Stoppoint(
        '940GZZLULVT',
        'Liverpool Street',
        '940GZZLULVT',
        51.5178,
        -0.0817,
        [],
        [victoriaLine, picadillyLine]
      );
      expect(actual_result).toBeInstanceOf(Stoppoint);
      expect(actual_result.name).toBe('Liverpool Street');
      expect(actual_result.id).toBe('940GZZLULVT');
      expect(actual_result.naptanId).toBe('940GZZLULVT');
      expect(actual_result.lat).toBe(51.5178);
      expect(actual_result.lon).toBe(-0.0817);
      expect(actual_result.modes).toEqual([]);
      expect(actual_result.lines).toEqual([victoriaLine, picadillyLine]);
    });
    test('accepts lat/lon as strings', () => {
      const actual_result = new Stoppoint(
        '940GZZLULVT',
        'Liverpool Street',
        '940GZZLULVT',
        '51.5178',
        '-0.0817',
        [modeTube],
        [victoriaLine, picadillyLine]
      );
      expect(actual_result).toBeInstanceOf(Stoppoint);
      expect(actual_result.name).toBe('Liverpool Street');
      expect(actual_result.id).toBe('940GZZLULVT');
      expect(actual_result.naptanId).toBe('940GZZLULVT');
      expect(actual_result.lat).toBe(51.5178);
      expect(actual_result.lon).toBe(-0.0817);
      expect(actual_result.modes).toEqual([modeTube]);
      expect(actual_result.lines).toEqual([victoriaLine, picadillyLine]);
    })
    test('throws error if lon is not parsable as a number', () => {
      expect(() => {
        new Stoppoint(
          '940GZZLULVT',
          'Liverpool Street',
          '940GZZLULVT',
          '51.5178',
          'not a number',
          [modeTube],
          [victoriaLine, picadillyLine]
        );
      }).toThrowError('Invalid lat/lon for stoppoint 940GZZLULVT');
    });
    test('throws error if lat is not parsable as a number', () => {
      expect(() => {
        new Stoppoint(
          '940GZZLULVT',
          'Liverpool Street',
          '940GZZLULVT',
          'not a number',
          '-0.0817',
          [modeTube],
          [victoriaLine, picadillyLine]
        );
      }).toThrowError('Invalid lat/lon for stoppoint 940GZZLULVT');
    });
    test('throws error if name is empty', () => {
      expect(() => {
        new Stoppoint(
          '940GZZLULVT',
          '',
          '940GZZLULVT',
          '51.5178',
          '-0.0817',
          [modeTube],
          [victoriaLine, picadillyLine]
        );
      }).toThrowError('Empty name for stoppoint 940GZZLULVT/940GZZLULVT');
    });
    test('throws error if id is empty', () => {
      expect(() => {
        new Stoppoint(
          '',
          'Liverpool Street',
          '940GZZLULVT',
          '51.5178',
          '-0.0817',
          [modeTube],
          [victoriaLine, picadillyLine]
        );
      }).toThrowError('Empty id for stoppoint Liverpool Street/940GZZLULVT');
    });
    test('throws error if naptanId is empty', () => {
      expect(() => {
        new Stoppoint(
          '940GZZLULVT',
          'Liverpool Street',
          '',
          '51.5178',
          '-0.0817',
          [modeTube],
          [victoriaLine, picadillyLine]
        );
      }).toThrowError('Empty naptanId for stoppoint 940GZZLULVT/Liverpool Street');
    });

  })
  describe('test class methods', () => {
    test('should return [Object Stoppoint: id] when calling toString', () => {
      const actual_result = new Stoppoint(
        '940GZZLULVT',
        'Liverpool Street',
        '940GZZLULVT',
        51.5178,
        -0.0817,
        [modeTube],
        [victoriaLine, picadillyLine]
      );
      expect(actual_result.toString()).toBe('[object Stoppoint: 940GZZLULVT]');
    });
    test('should return Stoppoint: id when calling [Symbol.toStringTag', () => {
      const actual_result = new Stoppoint(
        '940GZZLULVT',
        'Liverpool Street',
        '940GZZLULVT',
        51.5178,
        -0.0817,
        [modeTube],
        [victoriaLine, picadillyLine]
      );
      expect(actual_result[Symbol.toStringTag]).toBe('Stoppoint: 940GZZLULVT');
    });
    test('should return [object Stoppoint: id] when calling Object.toString.call', () => {
      const actual_result = new Stoppoint(
        '940GZZLULVT',
        'Liverpool Street',
        '940GZZLULVT',
        51.5178,
        -0.0817,
        [modeTube],
        [victoriaLine, picadillyLine]
      );
      expect(Object.prototype.toString.call(actual_result)).toBe('[object Stoppoint: 940GZZLULVT]');
    });
    test('should return valid object when calling getObject', () => {
      const expected_result = {
        type: 'stoppoint',
        id: '940GZZLULVT',
        name: 'Liverpool Street',
        naptanId: '940GZZLULVT',
        lat: 51.5178,
        lon: -0.0817,
        modes: [modeTube.id],
        lines: [victoriaLine.lineName, picadillyLine.lineName]
      }
      const actual_result = new Stoppoint(
        '940GZZLULVT',
        'Liverpool Street',
        '940GZZLULVT',
        51.5178,
        -0.0817,
        [modeTube],
        [victoriaLine, picadillyLine]
      );
      expect(actual_result.getObject()).toEqual(expected_result)
    });
  });
})
