import Line from "../Line";
import Mode from "../Mode";

describe('Line', () => {
  describe('test name values for valid modes', () => {
    const modeTube = new Mode('tube');
    test('should return "Bakerloo" and "bakerloo" when called', () => {
      const line = new Line('bakerloo', modeTube);
      expect(line.displayName).toBe('Bakerloo Line');
      expect(line.lineName).toBe('bakerloo');
    });
    test('should return "Central" and "central" when called', () => {
      const line = new Line('central', modeTube);
      expect(line.displayName).toBe('Central Line');
      expect(line.lineName).toBe('central');
    });
    test('should return "Circle" "and "circle" when called', () => {
      const line = new Line('circle', modeTube);
      expect(line.displayName).toBe('Circle Line');
      expect(line.lineName).toBe('circle');
    });
    test('should return "District" and "district" when called', () => {
      const line = new Line('district', modeTube);
      expect(line.displayName).toBe('District Line');
      expect(line.lineName).toBe('district');
    });
    test('should return "Hammersmith & City" and "hammersmith-city" when called', () => {
      const line = new Line('hammersmith-city', modeTube);
      expect(line.displayName).toBe('Hammersmith & City');
      expect(line.lineName).toBe('hammersmith-city');
    });
    test('should return "Jubilee" and "jubilee" when called', () => {
      const line = new Line('jubilee', modeTube);
      expect(line.displayName).toBe('Jubilee Line');
      expect(line.lineName).toBe('jubilee');
    });
    test('should return "Metropolitan" and "metropolitan" when called', () => {
      const line = new Line('metropolitan', modeTube);
      expect(line.displayName).toBe('Metropolitan Line');
      expect(line.lineName).toBe('metropolitan');
    });
    test('should return "Northern" and "northern" when called', () => {
      const line = new Line('northern', modeTube);
      expect(line.displayName).toBe('Northern Line');
      expect(line.lineName).toBe('northern');
    });
    test('should return "Piccadilly" and "picadilly" when called', () => {
      const line = new Line('piccadilly', modeTube);
      expect(line.displayName).toBe('Piccadilly Line');
      expect(line.lineName).toBe('piccadilly');
    });
    test('should return "Victoria" and "victoria" when called', () => {
      const line = new Line('victoria', modeTube);
      expect(line.displayName).toBe('Victoria Line');
      expect(line.lineName).toBe('victoria');
    });
    test('should return "Waterloo & City" and "waterloo-city" when called', () => {
      const line = new Line('waterloo-city', modeTube);
      expect(line.displayName).toBe('Waterloo & City Line');
      expect(line.lineName).toBe('waterloo-city');
    });
    test('should return "DLR" and "dlr" when called', () => {
      const line = new Line('dlr', modeTube);
      expect(line.displayName).toBe('DLR');
      expect(line.lineName).toBe('dlr');
    });
    test('should return "London Overground" and "london-overground" when called', () => {
      const line = new Line('london-overground', modeTube);
      expect(line.displayName).toBe('London Overground');
      expect(line.lineName).toBe('london-overground');
    });
  });
  describe('constructor', () => {
    const modeTube = new Mode('tube');
    test('should throw an error when called with an invalid line name', () => {
      expect(() => new Line('invalid', modeTube)).toThrowError('Line not found in tfl_lines: invalid');
    });
    test('should throw an error when called with an empty lineName', () => {
      expect(() => new Line('', modeTube)).toThrowError('Line not found in tfl_lines:');
    });
  });
  describe('test class methods', () => {
    test('should return [Object Line: bakerloo] when [Symbol.toStringTag] called', () => {
      const modeTube = new Mode('tube');
      const line = new Line('bakerloo', modeTube);
      expect(line[Symbol.toStringTag]).toBe('Line: bakerloo');
    });
    test('should return [Object Line: bakerloo] when [Symbol.toStringTag] called', () => {
      const modeTube = new Mode('tube');
      const line = new Line('bakerloo', modeTube);
      expect(Object.prototype.toString.call(line)).toBe('[object Line: bakerloo]');
    });
    test('should return "bakerloo" when toString called', () => {
      const modeTube = new Mode('tube');
      const line = new Line('bakerloo', modeTube);
      expect(line.toString()).toBe('bakerloo');
    });
    test('should return valid object when toObject called', () => {
      const expected_result = {
        displayName: 'Bakerloo Line',
        lineName: 'bakerloo',
        mode: 'tube',
        type: 'line'
      }
      const modeTube = new Mode('tube');
      const line = new Line('bakerloo', modeTube);
      expect(line.toObject()).toEqual(expected_result);
    });

  });
});
