import * as Stoppoint from '../StoppointFunctional';
import * as Line from '../LineFunctional';
import * as Mode from '../ModeFunctional';
import {validate as linevalidate} from '../LineFunctional';

describe ('Functional Stoppoint tests', () => {
  describe('singleton implementation', () => {
    test('stoppoint_1 should be equal to stoppoint_2', () => {
      const lines = [Line.getLine('bakerloo', Mode.getMode('tube')), Line.getLine('central', Mode.getMode('tube'))]
      const modes = [Mode.getMode('tube'), Mode.getMode('tube')]
      const stoppoint_1: Stoppoint.Stoppoint = Stoppoint.addStoppoint('1', 'name1', 'naptanId1', 51.1, 22.2, modes, lines);
      const stoppoint_2: Stoppoint.Stoppoint = Stoppoint.addStoppoint('1', 'name1', 'naptanId1', 51.1, 22.2, modes, lines);
      const stoppoint_3: Stoppoint.Stoppoint = Stoppoint.addStoppoint('2', 'name2', 'naptanId2', 51.1, 22.2, modes, lines);
  
      expect(stoppoint_1).toBe(stoppoint_2);
    })
    test('stoppoint_1 should not be equal to stoppoint_3', () => {
      const stoppoint_1: Stoppoint.Stoppoint = Stoppoint.addStoppoint('1', 'name1', 'naptanId1', 51.1, 22.2, [Mode.getMode('tube'), Mode.getMode('bus')], [Line.getLine('bakerloo', Mode.getMode('tube')), Line.getLine('central', Mode.getMode('tube'))]);
      const stoppoint_2: Stoppoint.Stoppoint = Stoppoint.addStoppoint('1', 'name1', 'naptanId1', 51.1, 22.2, [Mode.getMode('tube'), Mode.getMode('bus')], [Line.getLine('bakerloo', Mode.getMode('tube')), Line.getLine('central', Mode.getMode('tube'))]);
      const stoppoint_3: Stoppoint.Stoppoint = Stoppoint.addStoppoint('2', 'name2', 'naptanId2', 51.1, 22.2, [Mode.getMode('tube'), Mode.getMode('bus')], [Line.getLine('bakerloo', Mode.getMode('tube')), Line.getLine('central', Mode.getMode('tube'))]);
  
      expect(stoppoint_1).not.toBe(stoppoint_3);
    })
  })

})