import * as Mode from '../ModeFunctional';

describe('Functional Mode tests', () => {
  describe('test singleton', () => {
    let mode_bus: Mode.Mode;
    let mode_dlr: Mode.Mode;
    let mode_elizabeth_line: Mode.Mode;
    let mode_overground: Mode.Mode;
    let mode_tube: Mode.Mode;
    beforeEach(() => {
      mode_bus = Mode.getMode('bus');
      mode_dlr = Mode.getMode('dlr');
      mode_elizabeth_line = Mode.getMode('elizabeth-line');
      mode_overground = Mode.getMode('overground');
      mode_tube = Mode.getMode('tube');
    })
    test('mode_bus should be equal to mode_bus', () => {
      expect(mode_bus).toBe(mode_bus);
    })
    test('mode_dlr should be equal to mode_dlr', () => {
      expect(mode_dlr).toBe(mode_dlr);
    })
    test('mode_elizabeth_line should be equal to mode_elizabeth_line', () => {
      expect(mode_elizabeth_line).toBe(mode_elizabeth_line);
    })
    test('mode_overground should be equal to mode_overground', () => {
      expect(mode_overground).toBe(mode_overground);
    })
    test('mode_tube should be equal to mode_tube', () => {
      expect(mode_tube).toBe(mode_tube);
    })
    test('mode_bus should not be equal to mode_dlr', () => {
      expect(mode_bus).not.toBe(mode_dlr);
    })
    test('mode_bus should not be equal to mode_elizabeth_line', () => {
      expect(mode_bus).not.toBe(mode_elizabeth_line);
    })
    test('mode_bus should not be equal to mode_overground', () => {
      expect(mode_bus).not.toBe(mode_overground);
    })
    test('mode_bus should not be equal to mode_tube', () => {
      expect(mode_bus).not.toBe(mode_tube);
    })
    test('mode_dlr should not be equal to mode_elizabeth_line', () => {
      expect(mode_dlr).not.toBe(mode_elizabeth_line);
    })
    test('mode_dlr should not be equal to mode_overground', () => {
      expect(mode_dlr).not.toBe(mode_overground);
    })
    test('mode_dlr should not be equal to mode_tube', () => {
      expect(mode_dlr).not.toBe(mode_tube);
    })
    test('mode_elizabeth_line should not be equal to mode_overground', () => {
      expect(mode_elizabeth_line).not.toBe(mode_overground);
    })
    test('mode_elizabeth_line should not be equal to mode_tube', () => {
      expect(mode_elizabeth_line).not.toBe(mode_tube);
    })
    test('mode_overground should not be equal to mode_tube', () => {
      expect(mode_overground).not.toBe(mode_tube);
    })

  })
  describe('getMode', () => {
    test('getMode should create an object which confirms to Mode interface', () => {
      const mode = Mode.getMode('bus');
      expect(mode.type).toBe('mode');
      expect(mode.id).toBe('bus');
      expect(mode.name).toBe('Bus');
      expect(mode.toString()).toBe('bus');
      expect(mode).toBeInstanceOf(Object);
    })
    test('getMode should throw an error if modeName is not in Modes', () => {
      expect(() => {
        Mode.getMode('not_in_Modes')
      }).toThrowError('Invalid mode: not_in_Modes');
    })
  })
  describe('check validate', () => {
    const mode: any = Mode.getMode('bus'); // not Mode.mode or typescript wont let us delete properties
    beforeAll(() => {
      // quickly check we've got a valid item
      expect(mode.name).toBe('Bus');
      expect(mode.id).toBe('bus');
      expect(mode.type).toBe('mode');
    })
    test('validate should return true if mode is correctly formed object', () => {
      expect(Mode.validate(mode)).toBe(true);
    })
    test('validate should return false if type is dropped from object', () => {
      let modeClone = Object.assign({}, mode)
      delete modeClone.type;
      expect(Mode.validate(modeClone)).toBe(false);
    })
    test('validate should return false if id is dropped from object', () => {
      let modeClone = Object.assign({}, mode)
      delete modeClone.id;
      expect(Mode.validate(modeClone)).toBe(false);
    })
    test('validate should return false if name is dropped from object', () => {
      let modeClone = Object.assign({}, mode)
      delete modeClone.name;
      expect(Mode.validate(modeClone)).toBe(false);
    })
    test('validate should return false if non-object is passed in', () => {
      expect(Mode.validate(1)).toBe(false);
    })
    test('validate should return false if null is passed in', () => {
      expect(Mode.validate(null)).toBe(false);
    })
    test('validate should return false if undefined is passed in', () => {
      expect(Mode.validate(undefined)).toBe(false);
    })
  })
  describe('check toString', () => {
    test('toString should return the name of the mode (not [object Object])', () => {
      const mode = Mode.getMode('bus');
      expect(mode.toString()).toBe('bus');
    })
  })

})
