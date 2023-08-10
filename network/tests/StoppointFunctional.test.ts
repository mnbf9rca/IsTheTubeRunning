import * as Stoppoint from '../StoppointFunctional';
import * as Line from '../LineFunctional';
import * as Mode from '../ModeFunctional';
import { validate as linevalidate } from '../LineFunctional';

let currentLineId: number = 1

const nextLineId = () => {
  return ++currentLineId;
}

describe('Functional Stoppoint tests', () => {
  describe('singleton implementation', () => {
    test('stoppoint_1 should be equal to stoppoint_2', () => {
      const lines = [Line.getLine('bakerloo', Mode.getMode('tube')), Line.getLine('central', Mode.getMode('tube'))]
      const modes = [Mode.getMode('tube'), Mode.getMode('tube')]
      const id1 = nextLineId()
      const id2 = nextLineId()
      const stoppoint_1: Stoppoint.Stoppoint = Stoppoint.addStoppoint(id1.toString(), 'name1', 'naptanId1', 51.1, 22.2, modes, lines);
      const stoppoint_2: Stoppoint.Stoppoint = Stoppoint.addStoppoint(id1.toString(), 'name1', 'naptanId1', 51.1, 22.2, modes, lines);
      const stoppoint_3: Stoppoint.Stoppoint = Stoppoint.addStoppoint(id2.toString(), 'name2', 'naptanId2', 51.1, 22.2, modes, lines);

      expect(stoppoint_1).toBe(stoppoint_2);
    })
    test('stoppoint_1 should not be equal to stoppoint_3', () => {
      const id1 = nextLineId()
      const id2 = nextLineId()
      const stoppoint_1: Stoppoint.Stoppoint = Stoppoint.addStoppoint(id1.toString(), 'name1', 'naptanId1', 51.1, 22.2, [Mode.getMode('tube'), Mode.getMode('bus')], [Line.getLine('bakerloo', Mode.getMode('tube')), Line.getLine('central', Mode.getMode('tube'))]);
      const stoppoint_2: Stoppoint.Stoppoint = Stoppoint.addStoppoint(id1.toString(), 'name1', 'naptanId1', 51.1, 22.2, [Mode.getMode('tube'), Mode.getMode('bus')], [Line.getLine('bakerloo', Mode.getMode('tube')), Line.getLine('central', Mode.getMode('tube'))]);
      const stoppoint_3: Stoppoint.Stoppoint = Stoppoint.addStoppoint(id2.toString(), 'name2', 'naptanId2', 51.1, 22.2, [Mode.getMode('tube'), Mode.getMode('bus')], [Line.getLine('bakerloo', Mode.getMode('tube')), Line.getLine('central', Mode.getMode('tube'))]);
      expect(stoppoint_1).not.toBe(stoppoint_3);
    })
  })
  describe('addStoppoint', () => {
    test('adding stoppoint with missing id should throw error', () => {
      const modes = [Mode.getMode('tube')];
      const lines = [Line.getLine('bakerloo', Mode.getMode('tube'))];
      expect(() => {
        Stoppoint.addStoppoint('', 'name', 'naptanId', 51.1, 22.2, modes, lines)
      }
      ).toThrowError(new Error('Invalid id: '));
    })
    test('adding stoppoint with missing name should throw error', () => {
      const modes = [Mode.getMode('tube')];
      const lines = [Line.getLine('bakerloo', Mode.getMode('tube'))];
      expect(() => {
        Stoppoint.addStoppoint(nextLineId().toString(), '', 'naptanId', 51.1, 22.2, modes, lines)
      }
      ).toThrowError(new Error('Invalid name: '));
    })
    test('adding stoppoint with missing naptanId should throw error', () => {
      const modes = [Mode.getMode('tube')];
      const lines = [Line.getLine('bakerloo', Mode.getMode('tube'))];
      expect(() => {
        Stoppoint.addStoppoint(nextLineId().toString(), 'name', '', 51.1, 22.2, modes, lines)
      }
      ).toThrowError(new Error('Invalid naptanId: '));
    })
    test('adding stoppoint with missing modes should be ok', () => {
      const lines = [Line.getLine('bakerloo', Mode.getMode('tube'))];
      const line_id = nextLineId().toString()
      const actual_result = Stoppoint.addStoppoint(line_id, 'name', 'naptanId', 51.1, 22.2, [], lines)
      expect(actual_result.id).toBe(line_id);
      expect(actual_result.name).toBe('name');
      expect(actual_result.naptanId).toBe('naptanId');
      expect(actual_result.modes.length).toEqual(0);
      expect(actual_result.lines).toEqual(lines);

    })
    test('adding stoppoint with missing lines should be ok', () => {
      const modes = [Mode.getMode('tube')];
      const line_id = nextLineId().toString()
      const actual_result = Stoppoint.addStoppoint(line_id, 'name', 'naptanId', 51.1, 22.2, modes, [])
      expect(actual_result.id).toBe(line_id);
      expect(actual_result.name).toBe('name');
      expect(actual_result.naptanId).toBe('naptanId');
      expect(actual_result.modes).toEqual(modes);
      expect(actual_result.lines.length).toEqual(0);

    })
    test('adding stoppoint with invalid modes should throw an error', () => {
      const mode_tube = Mode.getMode('tube')
      const lines = [Line.getLine('bakerloo', mode_tube)];
      let mutated_mode_tube: any = Object.assign({},mode_tube)
      expect(mutated_mode_tube).not.toBe(mode_tube)
      delete mutated_mode_tube.id
      const modes: any[] = [mutated_mode_tube];
      expect(() => {
        Stoppoint.addStoppoint(nextLineId().toString(), 'name', 'naptanId', 51.1, 22.2, modes, lines)
      }).toThrowError(new Error('Invalid modes in modes or not array: tube'));
    })
    test('adding stoppoint with invalid lines should throw an error', () => {
      const mode_tube = Mode.getMode('tube')
      const modes = [mode_tube];
      const line_id = nextLineId().toString()
      const line = Line.getLine('bakerloo',mode_tube)
      let mutated_line: any = Object.assign({},line)
      expect(mutated_line).not.toBe(line)
      delete mutated_line.lineName
      const lines: Line.Line[] = [mutated_line];
      expect(() => {
        Stoppoint.addStoppoint(line_id, 'name', 'naptanId', 51.1, 22.2, modes, lines)
      }).toThrowError(new Error('Invalid lines in lines or not array: bakerloo'));
    })
  })
})