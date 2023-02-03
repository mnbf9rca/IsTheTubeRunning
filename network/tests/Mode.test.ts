import Mode from "../Mode";

describe('Mode', () => {
  describe('test class methods for valid modes', () => {
    test('should return "bus" when toString() is called', () => {
      const mode = new Mode('bus');
      expect(mode.toString()).toBe('bus');
    });
    test('should return "Mode: bus" when [Symbol.toStringTag] is called', () => {
      const mode = new Mode('bus');
      expect(mode[Symbol.toStringTag]).toBe('Mode: bus');
    });
    test('should return "[object Mode: bus]" when Object.prototype.toString() is called', () => {
      const mode = new Mode('bus');
      expect(Object.prototype.toString.call(mode)).toBe('[object Mode: bus]');
    });
    test('should return "bus" when toObject() is called', () => {
      const expected_result = {
        id: "bus",
        name: "bus",
        type: "mode"
      }
      const mode = new Mode('bus');
      expect(mode.toObject()).toEqual(expected_result);
    });

  });
  describe('constructor', () => {
    test('throws an error when an invalid mode is passed', () => {
      expect(() => new Mode('nomode' as 'tube')).toThrowError('Invalid mode: nomode');
    });
    test('throws an error when an empty mode is passed', () => {
      expect(() => new Mode('' as 'tube')).toThrowError('Invalid mode: ');
    });
    test('throws an error when an undefined mode is passed', () => {
      expect(() => new Mode(undefined as any)).toThrowError('Invalid mode: undefined');
    });
    test('throws error when array is passed', () => {
      expect(() => new Mode(['tube'] as any)).toThrowError('Expected string, got array: tube');
    });
    test('throws error when array with multiple values is passed', () => {
      expect(() => new Mode(['tube', 'dlr'] as any)).toThrowError('Expected string, got array: tube,dlr');
    });
  });
  describe('test name values for valid modes', () => {
    test('should return "bus" when name is called', () => {
      const mode = new Mode('bus');
      expect(mode.name).toBe('bus');
      expect(mode.id).toBe('bus');
    });
    test('should return "DLR" when name is called', () => {
      const mode = new Mode('dlr');
      expect(mode.name).toBe('DLR');
    });
    test('should return "Elizabeth Line" when name is called', () => {
      const mode = new Mode('elizabeth-line');
      expect(mode.name).toBe('Elizabeth Line');
    });
    test('should return "Overground" when name is called', () => {
      const mode = new Mode('overground');
      expect(mode.name).toBe('Overground');
    });
    test('should return "Tube" when name is called', () => {
      const mode = new Mode('tube');
      expect(mode.name).toBe('Tube');
    });
  });
});


