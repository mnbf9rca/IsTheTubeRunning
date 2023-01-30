export enum Modes {
  bus = 'bus',
  dlr = 'dlr',
  'elizabeth-line' = 'elizabeth-line',
  overground = 'overground',
  tube = 'tube'
}
export type Mode = keyof typeof Modes;
