import * as Line from '../LineFunctional';
import * as Mode from '../ModeFunctional';

describe('Functional Line tests', () => {
  describe('singleton implementation', () => {
    let line_bakerloo_1: Line.Line;
    let line_bakerloo_2: Line.Line;
    let line_central_1: Line.Line;
    const mode_tube = Mode.getMode('tube');
    beforeEach(() => {
      line_bakerloo_1 = Line.getLine('bakerloo', mode_tube);
      line_bakerloo_2 = Line.getLine('bakerloo', mode_tube);
      line_central_1 = Line.getLine('central', mode_tube);
    })
    test('line_bakerloo_1 should be equal to line_bakerloo_2', () => {
      expect(line_bakerloo_1).toBe(line_bakerloo_2);
    })
    test('line_bakerloo_1 should not be equal to line_central_1', () => {
      expect(line_bakerloo_1).not.toBe(line_central_1);
    })
    test('Will return the same line even if created without a mode', () => {
      const line_bakerloo_3 = Line.getLine('bakerloo');
      expect(line_bakerloo_1).toBe(line_bakerloo_3);
    })
  })
  describe('test validate', () => {
    const line_bakerloo_1 = Line.getLine('bakerloo', Mode.getMode('tube'));
    test('line_bakerloo_1 should be valid', () => {
      expect(Line.validate(line_bakerloo_1)).toBe(true);
    })
    test('removing linename property should return false', () => {

      let mutated_line: any = Object.assign({}, line_bakerloo_1);
      expect(mutated_line).not.toBe(line_bakerloo_1);
      delete mutated_line.lineName;
      expect(Line.validate(mutated_line)).toBe(false);
    })
    test('removing displayName property should return false', () => {
      let mutated_line: any = Object.assign({}, line_bakerloo_1);
      expect(mutated_line).not.toBe(line_bakerloo_1);
      delete mutated_line.displayName;
      expect(Line.validate(mutated_line)).toBe(false);
    })
    test('removing mode property should return true', () => {
      let mutated_line: any = Object.assign({}, line_bakerloo_1);
      expect(mutated_line).not.toBe(line_bakerloo_1);
      delete mutated_line.mode;
      expect(Line.validate(mutated_line)).toBe(true);
    })
    test('removing toString method should return false', () => {
      let mutated_line: any = Object.assign({}, line_bakerloo_1);
      expect(mutated_line).not.toBe(line_bakerloo_1);
      delete mutated_line.toString;
      expect(Line.validate(mutated_line)).toBe(false);
    })
  })
  describe('getLine', () => {
    test('getLine should create an object which conforms to Line interface', () => {
      const mode_tube = Mode.getMode('tube');
      const line = Line.getLine('bakerloo', mode_tube);
      expect(line.type).toBe('line');
      expect(line.lineName).toBe('bakerloo');
      expect(line.displayName).toBe('Bakerloo Line');
      expect(line.toString()).toBe('bakerloo');
      expect(line).toBeInstanceOf(Object);
    })
    test('getLine should throw an error if lineName is not in tfl_lines', () => {
      expect(() => {
        const mode_tube = Mode.getMode('tube');
        Line.getLine('not_in_tfl_lines', mode_tube)
      }).toThrowError('Line not found in tfl_lines: not_in_tfl_lines');
    })
    test('getLine should throw error if mode is not in Modes', () => {
      expect(() => {
        const mode_tube = Mode.getMode('not_in_modes');
        Line.getLine('bakerloo', mode_tube)
      }).toThrowError('Invalid mode: not_in_modes');
    })
    test('getLine should throw error if mode is not in a valid Mode object', () => {
      const mode_tube = Mode.getMode('tube');
      let mutated_mode: any = Object.assign({}, mode_tube);
      expect(mutated_mode).not.toBe(mode_tube);
      delete mutated_mode.id
      expect(() => {
        Line.getLine('bakerloo', mutated_mode)
      }).toThrowError('Invalid mode: tube');
    })
  })
  describe('all expected tfl_lines are supported', () => {
    describe('isValidLine returns true for all lines in tfl_lines', () => {
      test('isValidLine should return true for bakerloo', () => {
        expect(Line.isValidLine('bakerloo')).toBe(true);
      })
      test('isValidLine should return true for central', () => {
        expect(Line.isValidLine('central')).toBe(true);
      })
      test('isValidLine should return true for circle', () => {
        expect(Line.isValidLine('circle')).toBe(true);
      })
      test('isValidLine should return true for district', () => {
        expect(Line.isValidLine('district')).toBe(true);
      })
      test('isValidLine should return true for dlr', () => {
        expect(Line.isValidLine('dlr')).toBe(true);
      })
      test('isValidLine should return true for elizabeth-line', () => {
        expect(Line.isValidLine('elizabeth-line')).toBe(true);
      })
      test('isValidLine should return true for hammersmith-city', () => {
        expect(Line.isValidLine('hammersmith-city')).toBe(true);
      })
      test('isValidLine should return true for jubilee', () => {
        expect(Line.isValidLine('jubilee')).toBe(true);
      })
      test('isValidLine should return true for metropolitan', () => {
        expect(Line.isValidLine('metropolitan')).toBe(true);
      })
      test('isValidLine should return true for northern', () => {
        expect(Line.isValidLine('northern')).toBe(true);
      })
      test('isValidLine should return true for piccadilly', () => {
        expect(Line.isValidLine('piccadilly')).toBe(true);
      })
      test('isValidLine should return true for victoria', () => {
        expect(Line.isValidLine('victoria')).toBe(true);
      })
      test('isValidLine should return true for waterloo-city', () => {
        expect(Line.isValidLine('waterloo-city')).toBe(true);
      })
      test('isValidLine should return true for london-overground', () => {
        expect(Line.isValidLine('london-overground')).toBe(true);
      })
      test('isValidLine should return false for undefined', () => {
        expect(Line.isValidLine(undefined)).toBe(false);
      })
      test('isValidLine should return false for null', () => {
        expect(Line.isValidLine(<any>null)).toBe(false);
      })
      test('isValidLine should return false for empty string', () => {
        expect(Line.isValidLine('')).toBe(false);
      })
      test('isValidLine should return false for NaN', () => {
        expect(Line.isValidLine(<any>NaN)).toBe(false);
      })
      test('isValidLine should return false for numbers', () => {
        expect(Line.isValidLine(<any>1)).toBe(false);
      })
      test('isValidLine should return false for numbers in strings', () => {
        expect(Line.isValidLine('n14')).toBe(false);
      })
      test('isValidLine should return false forarrays of valid values', () => {
        expect(Line.isValidLine(<any>['bakerloo', 'victoria'])).toBe(false);
      })
    })
    const mode_tube = Mode.getMode('tube');
    test('returns valid item for bakerloo', () => {
      const line = Line.getLine('bakerloo', mode_tube);
      expect(line).toBeInstanceOf(Object);
      expect(line.lineName).toBe('bakerloo');
      expect(line.displayName).toBe('Bakerloo Line');
      expect(line.toString()).toBe('bakerloo');
    })
    test('returns valid item for central', () => {
      const line = Line.getLine('central', mode_tube);
      expect(line).toBeInstanceOf(Object);
      expect(line.lineName).toBe('central');
      expect(line.displayName).toBe('Central Line');
      expect(line.toString()).toBe('central');
    })
    test('returns valid item for circle', () => {
      const line = Line.getLine('circle', mode_tube);
      expect(line).toBeInstanceOf(Object);
      expect(line.lineName).toBe('circle');
      expect(line.displayName).toBe('Circle Line');
      expect(line.toString()).toBe('circle');
    })
    test('returns valid item for district', () => {
      const line = Line.getLine('district', mode_tube);
      expect(line).toBeInstanceOf(Object);
      expect(line.lineName).toBe('district');
      expect(line.displayName).toBe('District Line');
      expect(line.toString()).toBe('district');
    })
    test('returns valid item for dlr', () => {
      const line = Line.getLine('dlr', mode_tube);
      expect(line).toBeInstanceOf(Object);
      expect(line.lineName).toBe('dlr');
      expect(line.displayName).toBe('DLR');
      expect(line.toString()).toBe('dlr');
    })
    test('returns valid item for elizabeth-line', () => {
      const line = Line.getLine('elizabeth-line', mode_tube);
      expect(line).toBeInstanceOf(Object);
      expect(line.lineName).toBe('elizabeth-line');
      expect(line.displayName).toBe('Elizabeth Line');
      expect(line.toString()).toBe('elizabeth-line');
    })
    test('returns valid item for hammersmith-city', () => {
      const line = Line.getLine('hammersmith-city', mode_tube);
      expect(line).toBeInstanceOf(Object);
      expect(line.lineName).toBe('hammersmith-city');
      expect(line.displayName).toBe('Hammersmith & City Line');
      expect(line.toString()).toBe('hammersmith-city');
    })
    test('returns valid item for jubilee', () => {
      const line = Line.getLine('jubilee', mode_tube);
      expect(line).toBeInstanceOf(Object);
      expect(line.lineName).toBe('jubilee');
      expect(line.displayName).toBe('Jubilee Line');
      expect(line.toString()).toBe('jubilee');
    })
    test('returns valid item for metropolitan', () => {
      const line = Line.getLine('metropolitan', mode_tube);
      expect(line).toBeInstanceOf(Object);
      expect(line.lineName).toBe('metropolitan');
      expect(line.displayName).toBe('Metropolitan Line');
      expect(line.toString()).toBe('metropolitan');
    })
    test('returns valid item for northern', () => {
      const line = Line.getLine('northern', mode_tube);
      expect(line).toBeInstanceOf(Object);
      expect(line.lineName).toBe('northern');
      expect(line.displayName).toBe('Northern Line');
      expect(line.toString()).toBe('northern');
    })
    test('returns valid item for piccadilly', () => {
      const line = Line.getLine('piccadilly', mode_tube);
      expect(line).toBeInstanceOf(Object);
      expect(line.lineName).toBe('piccadilly');
      expect(line.displayName).toBe('Piccadilly Line');
      expect(line.toString()).toBe('piccadilly');
    })
    test('returns valid item for victoria', () => {
      const line = Line.getLine('victoria', mode_tube);
      expect(line).toBeInstanceOf(Object);
      expect(line.lineName).toBe('victoria');
      expect(line.displayName).toBe('Victoria Line');
      expect(line.toString()).toBe('victoria');
    })
    test('returns valid item for waterloo-city', () => {
      const line = Line.getLine('waterloo-city', mode_tube);
      expect(line).toBeInstanceOf(Object);
      expect(line.lineName).toBe('waterloo-city');
      expect(line.displayName).toBe('Waterloo & City Line');
      expect(line.toString()).toBe('waterloo-city');
    })
    test('returns valid item for london-overground', () => {
      const line = Line.getLine('london-overground', mode_tube);
      expect(line).toBeInstanceOf(Object);
      expect(line.lineName).toBe('london-overground');
      expect(line.displayName).toBe('London Overground');
      expect(line.toString()).toBe('london-overground');
    })
  })

})